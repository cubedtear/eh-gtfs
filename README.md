# Mugitu

Live map + next departures/arrivals for buses, trains, metro and trams across Euskal Herria (Euskadi, Nafarroa and
Ipar Euskal Herria), built on open GTFS and GTFS-RT feeds. The three areas are handled the same way: every operator
has a region (`eus`, `nav`, `ipar`) and the UI lists them side by side.

## Data sources

| Area | Source | Operators |
|---|---|---|
| Euskadi | Open Data Euskadi / MovEuskadi (`data-index.json`, read by `core.py`) | all of them (Euskotren, Bizkaibus, Lurraldebus, ...) |
| Ipar Euskal Herria | transport.data.gouv.fr (configured in `sources.py`) | Txik Txak |
| Nafarroa | no regional operator added yet (only the Renfe stations inside the crop, e.g. Tudela) | - |

Adding an operator outside the MovEuskadi index is one entry in `sources.py` (dataset id, resource ids, region and
optional quirks). Everything after that (import, real time, UI) is shared.

### API keys (Txik Txak)

The Txik Txak feeds are hosted by Mecatran and need `?apiKey=...`, which may change. No key is stored in the code.
`sources.py` resolves the URLs from the portal at run time: it asks the dataset API of transport.data.gouv.fr for the
resources, follows the permanent data.gouv.fr link (a 302 that always points to the publisher's current keyed URL),
and falls back to the dataset's `original_url` and then to the last URLs that worked (`data/sources.json`).
They are resolved again every 30 minutes and immediately after a 401/403 from a feed or from the GTFS download
(at most once every 5 minutes per operator), so a rotated key heals itself.

### Txik Txak real-time quality

The portal's validator reports thousands of errors on this GTFS-RT feed; checked against the live feed:

- The validator's "times must increase" error (E022) and the missing `vehicle_id` are harmless here.
- The feed publishes an update for every trip of the day, tracked or not. A bus that is really followed has a delay
  that is never exactly 0 s and stays constant along the trip; about half of the trips have exactly 0 s on every
  stop, which is just the timetable. Those are not shown as "live" and draw no vehicle; only their SKIPPED stops are
  kept.
- SKIPPED stops are mostly real: they match the roadworks/detours of the alerts feed (same stops skipped by every
  trip of the line). They are shown as "Stop not served", not as a cancelled trip.
- An arrival/departure pair where one event is hours off and the other is sane (seen: -3.8 h) uses the sane one.
- There is no vehicle-position feed, so buses are placed from the trip updates and drawn dashed, like Euskotren.

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
- Renfe feeds cover all of Spain and are cropped to Euskal Herria (a rectangle, so a few stations of neighbouring
  provinces come with it).

## Timetable for another date

The station and line views have a date bar at the top. In a station, today means live data; picking
another date shows that day's theoretical timetable (no real-time data is merged). The line view
always shows the timetable of its date (today by default); trips opened from it show the same date.
The selectable range is today minus `SCHEDULE_PAST_DAYS` (default 7) to today plus `SCHEDULE_FUTURE_DAYS`
(default 60), narrowed to the period each operator's published GTFS covers (calendar and calendar_dates),
so it is often shorter, e.g. Euskotren publishes about 6 weeks.
API: `/api/departures?...&date=YYYYMMDD`, `/api/route_schedule?agency&route&date`, `/api/trip?...&sched=1`.

## Lurraldebus live arrivals

The seven "(Lurraldebus)" operators in Gipuzkoa publish empty GTFS-RT feeds, but lurraldebus.eus has a
real-time page per stop (`https://lurraldebus.eus/real/result/0/<stop_id>`, same stop ids as the GTFS). It lists
the next bus of every line with minutes left and the occupancy reported by the vehicle. `lurraldebus.py` reads it
(`core.py`, section "Lurraldebus live arrivals", does the rest):

- Each prediction is matched to the scheduled trip it most likely belongs to (same line, closest scheduled time,
  same direction) and stored as a synthetic trip update. Station departures then show live times, trip pages show
  the delay carried to the other stops, and buses appear on the map as estimated (dashed) vehicles, like Euskotren.
- The page has no trip id, so the match is an inference. On lines with a long headway a very late bus can be
  attributed to the wrong trip (its position stays right, its "late/early" label may not).
- Occupancy is the number of passengers on board, as published by the site.
- Destinations use the site's wording (learned per line and direction), not the lowercase GTFS route name.
- "Drop-off only" / "Pick-up only" stops are flagged.
- A stop with no information, or the site being down, simply falls back to the timetable.

Keeping the load on lurraldebus.eus low (the page is ~400 kB, ~60 kB gzipped, and the only way to get one stop):

- One shared cache and one request per stop at a time, whatever the number of users: 30 s for a stop somebody
  opened, 100 s for the map tracker, 2 min for "no information" answers.
- A stop view only calls the site when the timetable has a bus there in the next ~75 minutes.
- The map tracker runs only while a client shows buses (zoom >= 11, or a line/operator filter) and only covers
  trips that reach the visible area. It picks the fewest stops that see every active trip (greedy set cover),
  e.g. roughly 20 stops for a city view and 58 for the whole province, refreshed every 2 minutes at most.
- Token bucket (default 1 request/s, 2 parallel connections) with part of the budget reserved for users, so the
  tracker never delays someone opening a stop. Circuit breaker with exponential back-off (and `Retry-After`)
  when the site fails; data up to 5 min old is served meanwhile. A page layout change is detected and treated as
  a failure instead of "no buses".

Settings (optional environment variables, e.g. under `environment:` in `docker-compose.yml`):
`LURRALDEBUS_LIVE=0` disables everything, `LURRALDEBUS_TRACK=0` disables only the map tracker,
`LURRALDEBUS_RATE` (requests/s, default 1.0) and `LURRALDEBUS_MAX_STOPS` (default 60) tune the limits. The Info tab shows the source status per
operator.

## Docker

The image is built by GitHub Actions (`.github/workflows/docker.yml`) on every push to `master` and published to
the GitHub Container Registry as `ghcr.io/josuloo99/mugitu` (the name is fixed, whatever the repository is called)
for `linux/amd64` and `linux/arm64` (so it runs on a Raspberry Pi too). Tags: `latest` (master), `sha-<commit>`
(every push) and `1.2.3` / `1.2` for git tags like `v1.2.3`.

Run it anywhere, without cloning the code or building anything, with just `docker-compose.yml` (no `.env`
needed):

    docker compose up -d             # pulls the image, http://localhost:8000
    docker compose pull && docker compose up -d    # update to the latest image

The first start imports all timetables (about a minute); they are kept in the `mugitu-data` volume.
To use another port, change the left number in `ports:`. The container runs as `APP_UID:APP_GID` (default
1000:1000); only if you replace the `mugitu-data` volume with a host folder, set them in a `.env` next to the
compose file to your own ids (the output of `id -u` and `id -g`, e.g. `APP_UID=1000`, `APP_GID=1000`) and make the folder writable by them.
The container needs outbound HTTPS access to
opendata.euskadi.eus, transport.data.gouv.fr, app.mecatran.com and, in the browser, the map tile servers. Put a reverse proxy (Caddy, nginx, Traefik) in
front for HTTPS if you expose it publicly; installing the app on a phone requires HTTPS.

First publish: GitHub keeps a new package private. After the first workflow run open the repository's
Packages, then mugitu, then Package settings and set the visibility to Public (or run `docker login ghcr.io`
with a token that has `read:packages` on the machine that pulls). In the repository settings, Actions must be
allowed to write packages (Settings, Actions, General, Workflow permissions).

To build from your own checkout instead (for example while changing the code):

    docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build

## Install as an app (phone)

The UI is a Progressive Web App: it has a manifest (`static/manifest.webmanifest`), icons and a service
worker (`static/sw.js`) that keeps the app shell available offline. Live data and map tiles still need a connection.

- Android / Chrome: open the site, then use the "Install app" button in the Info tab (or the browser menu, "Install app").
- iPhone / Safari: Share, then "Add to Home Screen".

It opens full screen with the Mugitu name and icon. Installing and the service worker require HTTPS
(or `localhost`), so put a reverse proxy with a certificate in front when you expose it publicly.
The icon sources are `static/icon.svg` (rounded) and `static/icon-maskable.svg`; the PNGs were rendered from them
with `rsvg-convert -w <size> -h <size>`.
