"""Operators that publish no GTFS: timetables transcribed by hand into feeds/<name>.json.

Some small operators only publish PDFs. For those, the timetable is typed once into feeds/<name>.json (tables that
repeat the printed ones cell by cell, so they can be checked against the PDF by eye), and this module turns it into a
standard GTFS zip at import time. From there it goes through the same importer, real-time pipeline and UI as any
other operator (see sources.py, entry with "static_feed").

Optional feeds/<name>_shapes.json holds the road geometry of each pattern (made once by
tools/make_shapes.py with a routing engine); without it the line is drawn stop to stop.

File format: see feeds/labaztanesa.json. The essentials:
  stops      code -> name, lat, lon (+ osm / confidence / note, for humans)
  patterns   name -> ordered stops a bus passes (also those a trip skips); a trip's stops are a subsequence
  tables     one per printed table: columns (stop codes, as printed), rows (times, null = grey cell),
             route, direction, service, headsign, pattern; "emit" cuts a row ("until:CODE" / "from:CODE") when the
             rest of it is the same bus as another table's row; a row may be {"times": [...], "emit": ..., ...}
             to override the table's settings.
Only the Python standard library is used.
"""
import csv
import hashlib
import io
import json
import os
import zipfile
from datetime import date, datetime, timedelta

FEEDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feeds")
BUILDER_VERSION = 1          # bump when the way a feed is turned into GTFS changes: the operator is re-imported

_WEEK = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
SERVICE_DAYS = {"LS": (1, 1, 1, 1, 1, 1, 0), "SU": (0, 0, 0, 0, 0, 0, 1)}   # Mon-Sat / Sun (+ the holidays listed)


def _path(name, suffix=".json"):
    if not name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("bad feed name %r" % name)
    return os.path.join(FEEDS_DIR, name + suffix)


def load(name):
    with open(_path(name), encoding="utf-8") as f:
        return json.load(f)


def load_shapes(name):
    try:
        with open(_path(name, "_shapes.json"), encoding="utf-8") as f:
            return json.load(f).get("shapes", {})
    except OSError:
        return {}


def stamp(name):
    """Changes whenever the timetable, its shapes or the builder change: the importer re-imports on change."""
    h = hashlib.sha1(str(BUILDER_VERSION).encode())
    for suffix in (".json", "_shapes.json"):
        try:
            with open(_path(name, suffix), "rb") as f:
                h.update(f.read())
        except OSError:
            pass
    return h.hexdigest()[:16]


def _secs(s):
    h, m = s.split(":")
    return int(h) * 3600 + int(m) * 60


def _hms(sec):
    return "%02d:%02d:00" % (sec // 3600, sec % 3600 // 60)


def trips(feed):
    """Every trip of the feed: dicts with id, route, direction, service, headsign, pattern, table, stops=[(code, sec)]."""
    out = []
    for table in feed["tables"]:
        cols = table["columns"]
        for n, row in enumerate(table["rows"]):
            spec = row if isinstance(row, dict) else {"times": row}
            times = spec["times"]
            if len(times) != len(cols):
                raise ValueError("%s row %d: %d times for %d columns" % (table["id"], n, len(times), len(cols)))
            called = [(c, _secs(t)) for c, t in zip(cols, times) if t]
            emit = spec.get("emit", table.get("emit", "full"))
            if emit.startswith("until:"):
                at = emit[6:]
                called = called[:[c for c, _ in called].index(at) + 1]
            elif emit.startswith("from:"):
                at = emit[5:]
                called = called[[c for c, _ in called].index(at):]
            elif emit != "full":
                raise ValueError("%s: unknown emit %r" % (table["id"], emit))
            out.append({
                "id": "%s-%04d" % (table["id"], called[0][1] // 60 // 60 * 100 + called[0][1] // 60 % 60),
                "table": table["id"], "route": table["route"], "direction": table["direction"],
                "service": table["service"], "headsign": spec.get("headsign", table["headsign"]),
                "pattern": spec.get("pattern", table["pattern"]), "stops": called})
    return out


def validate(feed):
    """Hard errors (ValueError): anything that would make a wrong or unreadable GTFS."""
    stops, patterns, routes = feed["stops"], feed["patterns"], feed["routes"]
    for code, s in stops.items():
        if not (42.0 < s["lat"] < 43.6 and -3.5 < s["lon"] < -0.7):
            raise ValueError("stop %s is outside Euskal Herria" % code)
    for name, pat in patterns.items():
        if name.startswith("_"):
            continue
        for c in pat:
            if c not in stops:
                raise ValueError("pattern %s: unknown stop %s" % (name, c))
    seen = set()
    for t in trips(feed):
        if t["id"] in seen:
            raise ValueError("duplicate trip id %s" % t["id"])
        seen.add(t["id"])
        if t["route"] not in routes or t["service"] not in feed["services"]:
            raise ValueError("%s: unknown route or service" % t["id"])
        codes = [c for c, _ in t["stops"]]
        if len(codes) < 2:
            raise ValueError("%s: fewer than two stops" % t["id"])
        if any(c not in stops for c in codes):
            raise ValueError("%s: unknown stop" % t["id"])
        pat = iter(patterns[t["pattern"]])
        if not all(c in pat for c in codes):        # 'in' on an iterator consumes it: a subsequence test
            raise ValueError("%s: stops %s are not a subsequence of pattern %s" % (t["id"], codes, t["pattern"]))
        secs = [s for _, s in t["stops"]]
        if any(b < a for a, b in zip(secs, secs[1:])):
            raise ValueError("%s: times go backwards: %s" % (t["id"], t["stops"]))


def _csv(rows, header):
    b = io.StringIO()
    w = csv.writer(b, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return b.getvalue()


def _dates(a, b):
    d = date.fromisoformat(a)
    while d <= date.fromisoformat(b):
        yield d
        d += timedelta(days=1)


def build_zip(name, dest):
    """Write feeds/<name>.json as a GTFS zip at `dest` (deterministic: same input, same bytes)."""
    feed = load(name)
    validate(feed)
    shapes = load_shapes(name)
    ag = feed["agency"]
    aid = feed["slug"].upper()
    v = feed["validity"]
    ymd = lambda s: s.replace("-", "")
    files = {}
    files["agency.txt"] = _csv([[aid, ag["name"], ag["url"], "Europe/Madrid", ag.get("lang", "es"), ag.get("phone", "")]],
                               ["agency_id", "agency_name", "agency_url", "agency_timezone", "agency_lang", "agency_phone"])
    files["feed_info.txt"] = _csv([["Mugitu (transcribed from %s)" % feed["source"]["page"], feed["source"]["page"], ag.get("lang", "es"),
                                    ymd(v["from"]), ymd(v["to"]), stamp(name)]],
                                  ["feed_publisher_name", "feed_publisher_url", "feed_lang", "feed_start_date", "feed_end_date", "feed_version"])
    files["stops.txt"] = _csv([[c, s["name"], "%.6f" % s["lat"], "%.6f" % s["lon"]] for c, s in feed["stops"].items()],
                              ["stop_id", "stop_name", "stop_lat", "stop_lon"])
    files["routes.txt"] = _csv([[rid, aid, rid, r["long"], 3, r["color"], r.get("text_color", "FFFFFF")] for rid, r in feed["routes"].items()],
                               ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type", "route_color", "route_text_color"])
    all_trips = trips(feed)
    used_shapes = sorted({t["pattern"] for t in all_trips if t["pattern"] in shapes})
    files["trips.txt"] = _csv([[t["route"], t["service"], t["id"], t["headsign"], t["direction"],
                                t["pattern"] if t["pattern"] in shapes else ""] for t in all_trips],
                              ["route_id", "service_id", "trip_id", "trip_headsign", "direction_id", "shape_id"])
    files["stop_times.txt"] = _csv([[t["id"], _hms(sec), _hms(sec), code, i + 1]
                                    for t in all_trips for i, (code, sec) in enumerate(t["stops"])],
                                   ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"])
    files["calendar.txt"] = _csv([[sid, *SERVICE_DAYS[sid], ymd(v["from"]), ymd(v["to"])] for sid in feed["services"]],
                                 ["service_id", *_WEEK, "start_date", "end_date"])
    cal = feed["calendar"]
    ex = []
    for d in cal["sunday_timetable_on"]:
        ex += [["LS", ymd(d), 2], ["SU", ymd(d), 1]]
    for d in cal["no_service_on"]:
        ex += [["LS", ymd(d), 2], ["SU", ymd(d), 2]]
    files["calendar_dates.txt"] = _csv(sorted(ex, key=lambda r: (r[1], r[0])), ["service_id", "date", "exception_type"])
    if used_shapes:
        files["shapes.txt"] = _csv([[p, "%.5f" % lat, "%.5f" % lon, i + 1] for p in used_shapes for i, (lat, lon) in enumerate(shapes[p])],
                                   ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"])
    tmp = dest + ".part"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for fn, text in files.items():
            zi = zipfile.ZipInfo(fn, (2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, text)
    os.replace(tmp, dest)
    return len(all_trips)
