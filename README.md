# UNAM Guitar Prep — curated private RSS feed

This repository is preconfigured for:

- GitHub user: `jaharris`
- Repository: `unam-guitar-prep`
- Site: `https://jaharris.github.io/unam-guitar-prep/`
- RSS: `https://jaharris.github.io/unam-guitar-prep/feed.xml`

## What changed in this version

The feed still contains the verified Radio UAA/iVoox and IMER audio enclosures. It now also includes an automatic builder for the **Guitarras del Mundo** episodes used in the three-week course and listed on Apple Podcasts.

Apple Podcasts is a catalog, not the audio host. The builder therefore uses Apple's public Lookup API to discover the publisher's public RSS feed, then copies the selected episode `<enclosure>` URLs from that publisher feed into this private course feed. **The audio files are not copied or re-hosted.**

Selected Guitarras del Mundo items:

- Day 1 — Francisco Tárrega: El Rey de la Guitarra
- Day 4 — Lauro interpreta sus propias obras
- Day 4 alternative — Antonio Lauro interview
- Day 10 — Toru Takemitsu: La poesía del silencio
- Day 17 — Sharon/Sharin Isbin interview / Guitar Passions
- Day 18 — Reflexiones en torno a la guitarra
- Day 21 — Laura Mazón Franqui: la guitarra y su historia

## Upload / update instructions

1. Extract this ZIP on your computer.
2. Upload **all** of these files/folders to the root of the public GitHub repository `jaharris/unam-guitar-prep`.
3. If GitHub asks whether to replace the existing `feed.xml`, choose **replace/overwrite**.
4. Make sure the hidden folder `.github/workflows/` is uploaded too. It contains `build-feed.yml`.
5. Open the repository's **Actions** tab. You should see **Build curated podcast feed** run automatically after the upload. You can also open it and choose **Run workflow** manually.
6. When the action finishes, open `feed_build_report.txt`. It tells you which Guitarras del Mundo episodes were added and which publisher RSS feed was resolved.
7. Keep GitHub Pages set to **Settings → Pages → Deploy from a branch → main → /(root)**.
8. In Apple Podcasts use **Follow a Show by URL** and enter:
   `https://jaharris.github.io/unam-guitar-prep/feed.xml`

## Privacy / hosting note

GitHub Pages hosts only this small XML feed and its index page. Playback is requested directly from the original publisher's audio server. This avoids opening the iVoox/Spotify/Apple webpages and their cookie banners, but the audio host will still receive a normal media request (for example, IP address and player user-agent), as with any podcast app.

## If the Apple merge does not work

Open `feed_build_report.txt`. If Apple does not expose a `feedUrl`, the builder leaves the original Apple links in `feed.template.xml` as supplementary metadata and preserves all existing playable iVoox/IMER items. Nothing is deleted.

The generated `feed.xml` should normally be edited only by the builder. Make hand edits in `feed.template.xml`, then run the workflow again.
