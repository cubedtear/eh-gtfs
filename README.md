# Euskadi Transit

Live map + next departures/arrivals for buses, trains, metro and trams in Euskadi, built on the
Open Data Euskadi (MoveUskadi) GTFS and GTFS-RT feeds.

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

    docker compose up -d --build     # http://localhost:8000

The first start imports all timetables (about a minute); they are kept in the `transit-data` volume.
The container needs outbound HTTPS access to opendata.euskadi.eus and tile.openstreetmap.org (browser).
Put a reverse proxy (Caddy, nginx, Traefik) in front for HTTPS if you expose it publicly.
