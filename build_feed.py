#!/usr/bin/env python3
"""Build the curated UNAM Guitar Prep RSS feed.

The base feed contains the verified iVoox/Radio UAA and IMER enclosures.
This builder resolves the public RSS feed behind the Apple Podcasts show
"Guitarras del Mundo" using Apple's public iTunes Lookup API, then copies
selected publisher-hosted enclosures into the curated feed.

No Apple/Spotify audio is re-hosted. The resulting feed points directly to
publisher audio URLs from the source RSS feed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

APPLE_SHOW_ID = "1787567076"
APPLE_SHOW_URL = "https://podcasts.apple.com/us/podcast/guitarras-del-mundo/id1787567076"
APPLE_LOOKUP_URL = (
    "https://itunes.apple.com/lookup?id=" + APPLE_SHOW_ID + "&entity=podcast&country=us"
)

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM = "http://www.w3.org/2005/Atom"
CONTENT = "http://purl.org/rss/1.0/modules/content/"
STUDY = "https://example.invalid/unam-guitar-study/1.0"

ET.register_namespace("itunes", ITUNES)
ET.register_namespace("atom", ATOM)
ET.register_namespace("content", CONTENT)
ET.register_namespace("study", STUDY)

# Course items from Guitarras del Mundo that were already used as Apple
# alternatives in the three-week program. Title matching is deliberately
# redundant because the publisher occasionally changes punctuation/prefixes.
SELECTIONS = [
    {
        "day": 1,
        "rank": 0,
        "label": "Day 1 — Guitarras del Mundo — Francisco Tárrega: El Rey de la Guitarra",
        "variants": ["francisco tarrega", "el rey de la guitarra"],
        "apple_url": "https://podcasts.apple.com/us/podcast/guitarras-del-mundo/id1787567076?i=1000705864843",
        "note": "Core listening; Apple transcript is available where supported.",
    },
    {
        "day": 4,
        "rank": 0,
        "label": "Day 4 — Guitarras del Mundo — Lauro interpreta sus propias obras",
        "variants": ["lauro interpreta sus propias obras", "lauro interpreta a lauro"],
        "apple_url": APPLE_SHOW_URL,
        "note": "Original Day 4 Guitarras del Mundo selection; performance-centered.",
    },
    {
        "day": 4,
        "rank": 1,
        "label": "Day 4 — alternative — Antonio Lauro in interview",
        "variants": ["escuchemos la voz de antonio lauro", "antonio lauro en entrevista"],
        "apple_url": APPLE_SHOW_URL,
        "note": "Speech-heavier alternative for listening comprehension.",
    },
    {
        "day": 10,
        "rank": 0,
        "label": "Day 10 — Guitarras del Mundo — Toru Takemitsu: La poesía del silencio",
        "variants": ["toru takemitsu", "poesia del silencio"],
        "apple_url": "https://podcasts.apple.com/us/podcast/tp2-ep-16-toru-takemitsu-la-poes%C3%ADa-del-silencio-guitarrista/id1787567076?i=1000710344888",
        "note": "Apple transcript-friendly source.",
    },
    {
        "day": 17,
        "rank": 0,
        "label": "Day 17 — Guitarras del Mundo — Sharon Isbin interview / Guitar Passions",
        "variants": ["sharin isbin", "sharon isbin", "guitar passions"],
        "apple_url": "https://podcasts.apple.com/us/podcast/t2-ep20-sharin-isbin-entrevista-exclusiva-y-su-album/id1787567076?i=1000724802295",
        "note": "Interview and repertoire discussion.",
    },
    {
        "day": 18,
        "rank": 0,
        "label": "Day 18 — Guitarras del Mundo — Reflexiones en torno a la guitarra",
        "variants": ["reflexiones en torno a la guitarra"],
        "apple_url": "https://podcasts.apple.com/us/podcast/t2-ep-15-reflexiones-en-torno-a-la-guitarra/id1787567076?i=1000706621172",
        "note": "Reflective spoken Spanish about the musician's career and artistic development.",
    },
    {
        "day": 21,
        "rank": 0,
        "label": "Day 21 — Guitarras del Mundo — Laura Mazón Franqui: la guitarra y su historia",
        "variants": ["laura mazon franqui", "la guitarra y su historia"],
        "apple_url": "https://podcasts.apple.com/es/podcast/hablamos-con-laura-maz%C3%B3n-franqui-la-guitarra-y-su-historia/id1787567076?i=1000772705781",
        "note": "Final synthesis interview; Apple transcript-friendly source.",
    },
]

UA = "Mozilla/5.0 (compatible; UNAM-Guitar-Prep-RSS/1.1; +https://jaharris.github.io/unam-guitar-prep/)"


def fetch_bytes(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def resolve_gdm_feed() -> str:
    data = json.loads(fetch_bytes(APPLE_LOOKUP_URL).decode("utf-8"))
    for result in data.get("results", []):
        if str(result.get("collectionId", "")) == APPLE_SHOW_ID:
            feed = result.get("feedUrl")
            if feed:
                return feed
    # Some responses have only one podcast result but omit collectionId in edge cases.
    for result in data.get("results", []):
        feed = result.get("feedUrl")
        if feed and "Guitarras del Mundo".lower() in str(result.get("collectionName", "")).lower():
            return feed
    raise RuntimeError("Apple Lookup did not expose a public feedUrl for Guitarras del Mundo.")


def norm(text: str | None) -> str:
    text = text or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def child_text(el: ET.Element, tag: str) -> str:
    child = el.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


def find_source_item(source_channel: ET.Element, variants: list[str]) -> ET.Element | None:
    nvars = [norm(v) for v in variants]
    best = None
    best_score = -1
    for item in source_channel.findall("item"):
        title = child_text(item, "title")
        nt = norm(title)
        score = max((len(v) for v in nvars if v and v in nt), default=-1)
        if score > best_score:
            best_score = score
            best = item
    return best if best_score >= 0 else None


def clone_text(source_item: ET.Element, tag: str) -> str:
    el = source_item.find(tag)
    return (el.text or "").strip() if el is not None and el.text else ""


def make_gdm_item(selection: dict, source_item: ET.Element, source_feed: str) -> ET.Element:
    enclosure = source_item.find("enclosure")
    if enclosure is None or not enclosure.get("url"):
        raise RuntimeError("Matched source item has no enclosure URL")

    item = ET.Element("item")
    ET.SubElement(item, "title").text = selection["label"]
    ET.SubElement(item, "link").text = selection["apple_url"]
    guid = ET.SubElement(item, "guid", {"isPermaLink": "false"})
    guid.text = "unam-guitar-prep-gdm-" + str(selection["day"]) + "-" + str(selection["rank"])

    source_title = clone_text(source_item, "title")
    source_link = clone_text(source_item, "link") or APPLE_SHOW_URL
    description_html = (
        f"<p><strong>{selection['label'].split(' — ')[0]}</strong></p>"
        f"<p>{selection['note']}</p>"
        f"<p>Publisher episode: {source_title}</p>"
        f"<p><a href=\"{selection['apple_url']}\">Apple Podcasts episode/show page</a></p>"
        f"<p><a href=\"{source_link}\">Publisher episode webpage</a></p>"
        f"<p>Audio enclosure copied from the publisher's public RSS feed resolved through Apple's catalog; the audio itself is not re-hosted here.</p>"
        f"<p>Source RSS: {source_feed}</p>"
        f"<p>Study method: first listen for gist without transcript; second listen for structure; third listen with transcript/captions when available, then shadow and give a short Spanish summary.</p>"
    )
    ET.SubElement(item, "description").text = description_html
    ET.SubElement(item, f"{{{CONTENT}}}encoded").text = description_html

    attrs = {
        "url": enclosure.get("url", ""),
        "length": enclosure.get("length", "0") or "0",
        "type": enclosure.get("type", "audio/mpeg") or "audio/mpeg",
    }
    ET.SubElement(item, "enclosure", attrs)
    ET.SubElement(item, f"{{{ITUNES}}}explicit").text = "false"
    duration = source_item.find(f"{{{ITUNES}}}duration")
    if duration is not None and duration.text:
        ET.SubElement(item, f"{{{ITUNES}}}duration").text = duration.text.strip()
    ET.SubElement(item, f"{{{STUDY}}}sourceFeed").text = source_feed
    ET.SubElement(item, f"{{{STUDY}}}sourceTitle").text = source_title
    ET.SubElement(item, f"{{{STUDY}}}courseDay").text = str(selection["day"])
    ET.SubElement(item, f"{{{STUDY}}}courseRank").text = str(selection["rank"])
    return item


def day_rank_from_title(title: str) -> tuple[int, int, str]:
    nt = norm(title)
    m = re.search(r"\bdays?\s+(\d+)", nt)
    day = int(m.group(1)) if m else 999
    optional = 1 if "optional" in nt or "alternative" in nt else 0
    # Keep core before optional; tie-break deterministically by title.
    return day, optional, nt


def course_week_for_day(day: int) -> int:
    """Map course days to Apple Podcast seasons: Week 1/2/3 -> Season 1/2/3."""
    if 1 <= day <= 7:
        return 1
    if 8 <= day <= 14:
        return 2
    if 15 <= day <= 21:
        return 3
    # Keep any future/out-of-range extras in a final catch-all season rather than
    # silently folding them into Week 1.
    return 4


def normalize_course_order(channel: ET.Element) -> None:
    items = list(channel.findall("item"))
    items.sort(key=lambda el: day_rank_from_title(child_text(el, "title")))
    for item in items:
        channel.remove(item)

    # Apple displays these as Season 1, Season 2, Season 3. In this study feed
    # those correspond exactly to Week 1 (Days 1-7), Week 2 (Days 8-14), and
    # Week 3 (Days 15-21). Episode numbering restarts within each season.
    season_episode_counts: dict[int, int] = {}
    base_dt = datetime(2026, 9, 29, 12, 30, tzinfo=timezone.utc)

    for global_idx, item in enumerate(items, start=1):
        title = child_text(item, "title")
        day, _, _ = day_rank_from_title(title)
        week = course_week_for_day(day)
        season_episode_counts[week] = season_episode_counts.get(week, 0) + 1
        episode_in_week = season_episode_counts[week]

        pub = item.find("pubDate")
        if pub is None:
            pub = ET.SubElement(item, "pubDate")
        dt = base_dt - timedelta(minutes=global_idx - 1)
        pub.text = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")

        season = item.find(f"{{{ITUNES}}}season")
        if season is None:
            season = ET.SubElement(item, f"{{{ITUNES}}}season")
        season.text = str(week)

        ep = item.find(f"{{{ITUNES}}}episode")
        if ep is None:
            ep = ET.SubElement(item, f"{{{ITUNES}}}episode")
        ep.text = str(episode_in_week)

        ep_type = item.find(f"{{{ITUNES}}}episodeType")
        if ep_type is None:
            ep_type = ET.SubElement(item, f"{{{ITUNES}}}episodeType")
        ep_type.text = "full"

        week_el = item.find(f"{{{STUDY}}}week")
        if week_el is None:
            week_el = ET.SubElement(item, f"{{{STUDY}}}week")
        week_el.text = f"Week {week}"

        channel.append(item)


def remove_resolved_gdm_supplements(channel: ET.Element, resolved_days: set[int]) -> None:
    for sup in list(channel.findall(f"{{{STUDY}}}supplement")):
        title = norm(sup.get("title"))
        day_text = sup.get("day", "")
        m = re.search(r"(\d+)", day_text)
        day = int(m.group(1)) if m else None
        if day in resolved_days and "guitarras del mundo" in title:
            channel.remove(sup)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", default="feed.template.xml")
    parser.add_argument("--output", default="feed.xml")
    parser.add_argument("--report", default="feed_build_report.txt")
    parser.add_argument(
        "--source-feed",
        help="Optional direct source RSS URL/path for testing; otherwise resolve through Apple Lookup.",
    )
    args = parser.parse_args()

    template_path = Path(args.template)
    tree = ET.parse(template_path)
    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        raise SystemExit("Template has no channel element")

    report = []
    source_feed = ""
    source_xml = None
    try:
        if args.source_feed:
            source_feed = args.source_feed
            if re.match(r"^https?://", source_feed):
                source_xml = fetch_bytes(source_feed)
            else:
                source_xml = Path(source_feed).read_bytes()
        else:
            source_feed = resolve_gdm_feed()
            source_xml = fetch_bytes(source_feed)
        report.append(f"Resolved Guitarras del Mundo source feed: {source_feed}")
    except Exception as exc:
        report.append(f"WARNING: Could not resolve/fetch Guitarras del Mundo RSS feed: {exc}")
        report.append("The base iVoox/IMER items remain playable; Apple links remain as study:supplement metadata.")
        Path(args.report).write_text("\n".join(report) + "\n", encoding="utf-8")
        tree.write(args.output, encoding="utf-8", xml_declaration=True)
        return 0

    source_root = ET.fromstring(source_xml)
    source_channel = source_root.find("channel")
    if source_channel is None:
        raise SystemExit("Resolved source feed has no channel")

    added = []
    resolved_days = set()
    existing_guids = {child_text(it, "guid") for it in channel.findall("item")}
    for selection in SELECTIONS:
        guid = "unam-guitar-prep-gdm-" + str(selection["day"]) + "-" + str(selection["rank"])
        if guid in existing_guids:
            continue
        source_item = find_source_item(source_channel, selection["variants"])
        if source_item is None:
            report.append(f"NOT FOUND: {selection['label']}")
            continue
        try:
            new_item = make_gdm_item(selection, source_item, source_feed)
        except Exception as exc:
            report.append(f"SKIPPED: {selection['label']} — {exc}")
            continue
        channel.append(new_item)
        added.append((selection["label"], clone_text(source_item, "title")))
        resolved_days.add(selection["day"])

    remove_resolved_gdm_supplements(channel, resolved_days)

    # Update summary metadata only when we actually added something.
    if added:
        desc = channel.find("description")
        if desc is not None:
            desc.text = (
                "Private, curated listening feed for the three-week UNAM classical-guitar preparation program. "
                "Playable items combine verified Radio UAA/iVoox and IMER audio with selected Guitarras del Mundo "
                "episodes whose publisher enclosures are copied from the show's public RSS feed resolved through Apple's catalog."
            )
        summary = channel.find(f"{{{ITUNES}}}summary")
        if summary is not None:
            summary.text = (
                "Three-week Spanish listening-comprehension sequence for 20th- and 21st-century classical guitar history, "
                "repertoire, pedagogy, and performance, including selected Guitarras del Mundo episodes listed on Apple Podcasts."
            )

    normalize_course_order(channel)
    ET.indent(tree, space="  ")
    tree.write(args.output, encoding="utf-8", xml_declaration=True)

    # Parse once more as a basic well-formedness check.
    ET.parse(args.output)

    report.append(f"Added {len(added)} Guitarras del Mundo item(s).")
    for curated, source in added:
        report.append(f"ADDED: {curated} <= {source}")
    missing = len(SELECTIONS) - len(added)
    if missing:
        report.append(f"Unresolved selections: {missing}; their Apple links remain in the template as supplements unless their day was resolved by another GDM item.")
    report.append(f"Total playable item count in output: {len(channel.findall('item'))}")
    Path(args.report).write_text("\n".join(report) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
