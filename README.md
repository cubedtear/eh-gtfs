# Euskadi Transit

Live map + next departures/arrivals for buses, trains, metro and trams in Euskadi, built on the
Open Data Euskadi (MovEuskadi) GTFS and GTFS-RT feeds.

## Run

    python3 server.py            # http://127.0.0.1:8000  (use --host 0.0.0.0 --port N to change)

Python 3.9+ standard library only, no pip install needed. On first start the server downloads every
operator's GTFS zip and builds SQLite databases in `data/db/` (about 40 s). It refreshes them when the
index (`data-index.json`) reports a newer timetable. Real-time `.pb` feeds are fetched on demand
(15 s cache) and decoded by a built-in protobuf reader (`gtfsrt.py`).

## Notes

- A backend is required: the opendata hosts send no CORS headers and the `.pb` files need decoding.
- Many operators publish empty feeds (15-byte files). The UI shows "scheduled" for those.
- Euskotren publishes trip updates but no vehicle positions: train positions are estimated from
  the trip updates and shown with a dashed outline.
- AlavaBus encodes entity timestamps as local time; `LOCAL_EPOCH` in `core.py` corrects this.
- Renfe feeds cover all of Spain and are cropped to Euskadi.

## Docker

The image is built by GitHub Actions (`.github/workflows/docker.yml`) on every push to `master` and published to
the GitHub Container Registry as `ghcr.io/josuloo99/eh-gtfs` for `linux/amd64` and `linux/arm64`
(so it runs on a Raspberry Pi too). Tags: `latest` (master), `sha-<commit>` (every push) and `1.2.3` / `1.2`
for git tags like `v1.2.3`.

Run it anywhere, without cloning the code or building anything, from `docker-compose.yml` and an optional `.env`
(copy `.env.example`):

    docker compose up -d             # pulls the image, http://localhost:8000
    docker compose pull && docker compose up -d    # update to the latest image

The first start imports all timetables (about a minute); they are kept in the `transit-data` volume.
The container needs outbound HTTPS access to opendata.euskadi.eus and, in the browser, the map tile servers.
Put a reverse proxy (Caddy, nginx, Traefik) in front for HTTPS if you expose it publicly; installing the
app on a phone requires HTTPS.

First publish: GitHub keeps a new package private. After the first workflow run open the repository's
Packages, then eh-gtfs, then Package settings and set the visibility to Public (or run `docker login ghcr.io`
with a token that has `read:packages` on the machine that pulls). In the repository settings, Actions must be
allowed to write packages (Settings, Actions, General, Workflow permissions).

To build from your own checkout instead (for example while changing the code):

    docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build

## Install as an app (phone)

The UI is a Progressive Web App: it has a manifest (`static/manifest.webmanifest`), icons and a service
worker (`static/sw.js`) that keeps the app shell available offline. Live data and map tiles still need a connection.

- Android / Chrome: open the site, then use the "Install app" button in the Info tab (or the browser menu, "Install app").
- iPhone / Safari: Share, then "Add to Home Screen".

It opens full screen with the Euskadi Transit name and icon. Installing and the service worker require HTTPS
(or `localhost`), so put a reverse proxy with a certificate in front when you expose it publicly.
The icon sources are `static/icon.svg` (rounded) and `static/icon-maskable.svg`; the PNGs were rendered from them
with `rsvg-convert -w <size> -h <size>`.
