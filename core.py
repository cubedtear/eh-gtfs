"""Core logic: agency registry, GTFS updater, GTFS-RT cache and real-time merging."""
import bisect
import json
import logging
import math
import os
import re
import threading
import time
import zlib
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import gtfsrt
import store
from store import TZ, AgencyDB, candidate_days, haversine, norm, service_midnight

log = logging.getLogger("moveuskadi")

INDEX_URL = "https://opendata.euskadi.eus/transport/moveuskadi/data-index.json"
GTFS_DIR = os.path.join(store.DATA_DIR, "gtfs")
UA = {"User-Agent": "euskadi-transit-board/1.0 (personal use)"}
RT_TTL = 15            # seconds a decoded RT feed stays cached
RT_MAX_AGE = 600       # a feed whose header timestamp is older than this is considered stale
# AlavaBus publishes timestamps as "local time encoded as UTC"
LOCAL_EPOCH = {"alavabus"}

AGENCIES = {}          # slug -> info dict
DBS = {}               # slug -> AgencyDB
_state_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=16)


def quote_url(u):
    return urllib.parse.quote(u, safe=":/?&=%")


def http_get(url, timeout=20):
    req = urllib.request.Request(quote_url(url), headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# --------------------------------------------------------------------------- registry

def slugify(name):
    return re.sub(r"[^a-z0-9]+", "_", norm(name)).strip("_")


def load_index():
    path = os.path.join(store.DATA_DIR, "data-index.json")
    try:
        raw = http_get(INDEX_URL)
        idx = json.loads(raw)
        with open(path, "wb") as f:
            f.write(raw)
    except Exception as e:  # network down: use cache
        log.warning("index fetch failed: %s", e)
        if not os.path.exists(path):
            return False
        idx = json.load(open(path, "rb"))
    new = {}
    for name, files in idx.get("data", {}).items():
        info = {"name": name, "gtfs": None, "gtfs_stamp": "", "rt": {}, "slug": None}
        for f in files:
            fmt, url, fn = f.get("format"), f.get("url", ""), f.get("name", "")
            low = fn.lower()
            if fmt == "GTFS":
                info["gtfs"] = url
                info["gtfs_stamp"] = f.get("last-update", "")
                m = re.match(r"gtfs_(.+)\.zip$", fn)
                info["slug"] = m.group(1) if m else slugify(name)
            elif fmt == "GTFS-RT":
                if "alert" in low:
                    kind = "alerts"
                elif "trip" in low:
                    kind = "trips"
                elif "position" in low or "vehicle" in low:
                    kind = "vehicles"
                else:
                    continue
                info["rt"][kind] = url
        if info["gtfs"] and info["slug"]:
            new[info["slug"]] = info
    with _state_lock:
        for slug, info in new.items():
            old = AGENCIES.get(slug)
            info["ready"] = old["ready"] if old else False
            info["error"] = old.get("error") if old else None
            info["importing"] = old.get("importing", False) if old else False
            info["imported_stamp"] = old.get("imported_stamp", "") if old else ""
            AGENCIES[slug] = info
            DBS.setdefault(slug, AgencyDB(slug))
    return True


def _db_stamp(slug):
    p = os.path.join(store.DB_DIR, slug + ".sqlite")
    if not os.path.exists(p):
        return None
    try:
        import sqlite3
        c = sqlite3.connect("file:%s?mode=ro" % p, uri=True)
        meta = dict(c.execute("SELECT k, v FROM meta").fetchall())
        c.close()
        if meta.get("schema") != str(store.SCHEMA_VERSION):
            return None
        return meta.get("stamp", "")
    except Exception:
        return None


def update_agency(slug):
    info = AGENCIES[slug]
    if info.get("importing"):
        return
    stamp = _db_stamp(slug)
    if stamp is not None and not info["ready"]:
        info["ready"] = True
        info["imported_stamp"] = stamp
    if stamp is not None and stamp == info["gtfs_stamp"]:
        return
    info["importing"] = True
    try:
        os.makedirs(GTFS_DIR, exist_ok=True)
        zp = os.path.join(GTFS_DIR, slug + ".zip")
        log.info("downloading GTFS %s", slug)
        req = urllib.request.Request(quote_url(info["gtfs"]), headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r, open(zp + ".part", "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        os.replace(zp + ".part", zp)
        log.info("importing GTFS %s", slug)
        t0 = time.time()
        ok = store.import_gtfs(zp, os.path.join(store.DB_DIR, slug + ".sqlite"), slug, info["gtfs_stamp"])
        if ok:
            DBS[slug].reload()
            info["ready"] = True
            info["imported_stamp"] = info["gtfs_stamp"]
            info["error"] = None
            log.info("imported %s in %.1fs", slug, time.time() - t0)
        else:
            info["error"] = "no stops inside Euskadi"
        os.remove(zp)
    except Exception as e:
        log.exception("update of %s failed", slug)
        info["error"] = str(e)
    finally:
        info["importing"] = False


def updater_loop():
    os.makedirs(store.DB_DIR, exist_ok=True)
    first = True
    while True:
        try:
            if load_index():
                slugs = sorted(AGENCIES, key=lambda s: (_db_stamp(s) is not None, s))
                # mark already-imported ones ready right away so the UI works while others download
                for s in slugs:
                    st = _db_stamp(s)
                    if st is not None and not AGENCIES[s]["ready"]:
                        AGENCIES[s]["ready"] = True
                        AGENCIES[s]["imported_stamp"] = st
                with ThreadPoolExecutor(max_workers=3) as ex:
                    list(ex.map(update_agency, slugs))
        except Exception:
            log.exception("updater loop")
        first = False
        time.sleep(1800)


# --------------------------------------------------------------------------- RT feeds

class Feed:
    def __init__(self, url):
        self.url = url
        self.lock = threading.Lock()
        self.fetched = 0
        self.data = None
        self.error = None


_feeds = {}


def get_feed(url, ttl=RT_TTL):
    f = _feeds.get(url)
    if f is None:
        f = _feeds.setdefault(url, Feed(url))
    if time.time() - f.fetched < ttl:
        return f
    with f.lock:
        if time.time() - f.fetched < ttl:
            return f
        try:
            raw = http_get(url, timeout=10)
            f.data = gtfsrt.decode(raw) if len(raw) > 20 else {"timestamp": 0, "trip_updates": [], "vehicles": [], "alerts": []}
            f.error = None
        except Exception as e:
            f.error = str(e)[:120]
            if f.data is None:
                f.data = {"timestamp": 0, "trip_updates": [], "vehicles": [], "alerts": []}
        f.fetched = time.time()
    return f


def fix_ts(slug, t):
    if t and slug in LOCAL_EPOCH:
        off = datetime.fromtimestamp(t, TZ).utcoffset().total_seconds()
        return int(t - off)
    return t


def feed_for(slug, kind, ttl=RT_TTL):
    url = AGENCIES[slug]["rt"].get(kind)
    return get_feed(url, ttl) if url else None


def refresh(slugs, kinds):
    jobs = [(s, k) for s in slugs for k in kinds if s in AGENCIES and AGENCIES[s]["rt"].get(k)]
    list(_pool.map(lambda a: feed_for(*a), jobs))


def feed_stats(slug, kind):
    """Return dict(n, age, status) for an agency feed (already cached)."""
    url = AGENCIES[slug]["rt"].get(kind)
    if not url:
        return {"status": "none", "n": 0}
    f = _feeds.get(url)
    if not f or not f.data:
        return {"status": "unknown", "n": 0}
    key = {"vehicles": "vehicles", "trips": "trip_updates", "alerts": "alerts"}[kind]
    n = len(f.data[key])
    ts = f.data["timestamp"]  # header timestamps are true UTC even for skewed feeds
    age = int(time.time() - ts) if ts else None
    if f.error and n == 0:
        st = "error"
    elif n == 0:
        st = "empty"
    elif kind != "alerts" and age is not None and age > RT_MAX_AGE:
        st = "stale"
    else:
        st = "live"
    return {"status": st, "n": n, "age": age}


# --------------------------------------------------------------------------- real-time merge

def nid(s):
    return s[:-2] if s and s.endswith(".0") else s


def tu_index(slug):
    """trip_id -> list of trip updates (fresh feed only)."""
    f = feed_for(slug, "trips")
    if not f or not f.data:
        return {}
    ts = f.data["timestamp"]
    if ts and time.time() - ts > RT_MAX_AGE * 3:
        return {}
    idx = _tu_cache.get(slug)
    if idx and idx[0] is f.data:
        return idx[1]
    out = {}
    for tu in f.data["trip_updates"]:
        tid = (tu.get("trip") or {}).get("trip_id")
        if tid:
            out.setdefault(tid, []).append(tu)
    _tu_cache[slug] = (f.data, out)
    return out


_tu_cache = {}


def pick_tu(tus, sdate):
    if not tus:
        return None
    key = sdate.strftime("%Y%m%d")
    for tu in tus:
        sd = tu["trip"].get("start_date")
        if sd and sd == key:
            return tu
    for tu in tus:
        if not tu["trip"].get("start_date"):
            return tu
    return None


def effective_times(slug, rows, sdate, tu):
    """Merge scheduled stop_times rows with a trip update.

    Returns list of dicts with scheduled and expected epoch times and the source:
    'rt' (reported by feed), 'est' (delay propagated), 'sched' (no real-time data).
    """
    mid = service_midnight(sdate)
    out = []
    by_seq, by_stop = {}, {}
    cancelled = False
    if tu:
        cancelled = tu["trip"].get("rel") == 3
        for s in tu["stus"]:
            if s.get("seq") is not None:
                by_seq[s["seq"]] = s
            if s.get("stop_id"):
                by_stop.setdefault(nid(s["stop_id"]), s)
    cur = None
    first_delay = None
    # first pass to find the initial delay (used for stops before the first update)
    def ev_time(ev, sched):
        if not ev:
            return None
        if ev.get("time"):
            return fix_ts(slug, ev["time"])
        if ev.get("delay") is not None:
            return sched + ev["delay"]
        return None

    for r in rows:
        sa, sd = mid + r["arr"], mid + r["dep"]
        stu = None
        if tu:
            stu = by_seq.get(r["seq"])
            if stu is None:
                cand = by_stop.get(nid(r["stop_id"]))
                if cand is not None and cand.get("seq") in (None, r["seq"]):
                    stu = cand
        item = {"seq": r["seq"], "stop_id": r["stop_id"], "name": r["name"], "lat": r["lat"], "lon": r["lon"],
                "station_id": r["station_id"], "sched_arr": sa, "sched_dep": sd, "arr": sa, "dep": sd,
                "src": "sched", "skipped": False}
        if stu is not None:
            if stu.get("rel") == 1:
                item["skipped"] = True
            a = ev_time(stu.get("arr"), sa)
            d = ev_time(stu.get("dep"), sd)
            if a is None and d is None:
                stu = None
            else:
                if a is None:
                    a = d if d >= sa else sa + (d - sd)
                if d is None:
                    d = a if a >= sd else sd + (a - sa)
                if abs(a - sa) > 4 * 3600 and abs(d - sd) > 4 * 3600:
                    return [dict(i, arr=i["sched_arr"], dep=i["sched_dep"], src="sched") for i in
                            _plain(rows, mid)], cancelled
                item.update(arr=a, dep=max(d, a), src="rt")
                cur = d - sd if stu.get("dep") else a - sa
                if first_delay is None:
                    first_delay = cur
        if stu is None and cur is not None and tu:
            item.update(arr=sa + cur, dep=sd + cur, src="est")
        out.append(item)
    if tu and first_delay is not None:
        # stops before the first update: assume the same delay
        for it in out:
            if it["src"] != "sched":
                break
            it.update(arr=it["sched_arr"] + first_delay, dep=it["sched_dep"] + first_delay, src="est")
    return out, cancelled


def _plain(rows, mid):
    return [{"seq": r["seq"], "stop_id": r["stop_id"], "name": r["name"], "lat": r["lat"], "lon": r["lon"],
             "station_id": r["station_id"], "sched_arr": mid + r["arr"], "sched_dep": mid + r["dep"],
             "skipped": False} for r in rows]


def resolve_service_date(db, trip, rows, now, start_date=None):
    """Pick the service day on which this trip is currently running (or runs next)."""
    from datetime import datetime as dt
    if start_date:
        try:
            return dt.strptime(start_date, "%Y%m%d").date()
        except ValueError:
            pass
    if not rows:
        return candidate_days(now)[1]
    first, last = rows[0]["dep"], rows[-1]["arr"]
    best = None
    for d in candidate_days(now)[:2]:
        if trip["service_id"] not in db.active_services(d):
            continue
        mid = service_midnight(d)
        if mid + first - 3600 <= now <= mid + last + 4 * 3600:
            return d
        best = best or d
    return best or candidate_days(now)[1]


_WHITES = {"", "FFFFFF", "F2F5F5", "000000"}
_color_policy = {}


def _official_colors_usable(db):
    """Do this operator's route colours actually tell lines apart? (several distinct non-white colours,
    or a single-line operator). Many feeds use one colour (or white) for every line."""
    key = (db.slug, db.version)
    if key not in _color_policy:
        routes = db.routes().values()
        distinct = {r["color"].upper() for r in routes if r["color"].upper() not in _WHITES}
        _color_policy[key] = len(distinct) >= 3 or (len(distinct) >= 1 and len(routes) <= 2)
    return _color_policy[key]


def auto_color(label):
    """Stable, readable colour derived from the line label (used when the operator publishes none)."""
    h = zlib.crc32((label or "").encode()) % 360
    # HSL(h, 62%, 40%) -> hex
    sat, lig = 0.62, 0.40
    c = (1 - abs(2 * lig - 1)) * sat
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = lig - c / 2
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(h // 60) % 6]
    return "%02X%02X%02X" % tuple(round((v + m) * 255) for v in (r, g, b))


def route_style(db, r):
    """(color, text_color, is_auto) for a route row."""
    col = r["color"].upper()
    if _official_colors_usable(db) and col not in ("", "FFFFFF", "F2F5F5"):
        return r["color"], r["text_color"], False
    label = r["short"] or r["long"] or r["route_id"]
    return auto_color(label), "FFFFFF", True


def line_info(db, route_id):
    r = db.routes().get(route_id)
    if not r:
        return {"line": route_id or "", "color": "", "text_color": "", "mode": "bus", "long": ""}
    color, text, _ = route_style(db, r)
    return {"line": r["short"] or r["long"] or r["route_id"], "color": color, "text_color": text,
            "mode": r["mode"], "long": r["long"]}


# --------------------------------------------------------------------------- departures

def departures(slug, station_id, kind="dep", limit=15, now=None):
    now = int(now or time.time())
    db = DBS[slug]
    stops = db.station_stops(station_id)
    if not stops:
        return None
    refresh([slug], ["trips"])
    tus = tu_index(slug)
    col = "dep" if kind == "dep" else "arr"
    cmp_ = "s2.seq>st.seq" if kind == "dep" else "s2.seq<st.seq"
    ph = ",".join("?" * len(stops))
    results = []
    seen = set()
    for window_h in (4, 12, 30):
        results = []
        for d in candidate_days(now):
            active = db.active_services(d)
            if not active:
                continue
            mid = service_midnight(d)
            lo, hi = now - mid - 2400, now - mid + window_h * 3600
            sql = ("SELECT st.tix, st.seq, st.stop_id, st.arr, st.dep, t.trip_id, t.route_id, t.service_id, t.headsign "
                   "FROM stop_times st JOIN trips t ON t.tix=st.tix "
                   "WHERE st.stop_id IN (%s) AND st.%s BETWEEN ? AND ? "
                   "AND EXISTS (SELECT 1 FROM stop_times s2 WHERE s2.tix=st.tix AND %s)" % (ph, col, cmp_))
            for r in db.q(sql, (*stops, lo, hi)):
                if r["service_id"] not in active:
                    continue
                sched = mid + r[col]
                tu = pick_tu(tus.get(r["trip_id"]), d) if tus else None
                exp, src, cancelled, skipped = sched, "sched", False, False
                if tu:
                    rows = db.trip_stop_times(r["tix"])
                    eff, cancelled = effective_times(slug, rows, d, tu)
                    for e in eff:
                        if e["seq"] == r["seq"]:
                            exp = e[col]
                            src = e["src"]
                            skipped = e.get("skipped", False)
                            break
                if exp < now - 45:
                    continue
                # a zero-delay update for a trip that is far away is just the timetable echoed back
                if src != "sched" and exp - now > 1200 and abs(exp - sched) < 60:
                    src = "sched"
                li = line_info(db, r["route_id"])
                hs = r["headsign"] or li["long"]
                results.append({
                    "trip_id": r["trip_id"], "route_id": r["route_id"], "line": li["line"], "color": li["color"],
                    "text_color": li["text_color"], "mode": li["mode"], "headsign": hs, "sched": sched,
                    "expected": exp, "delay": exp - sched, "rt": src if src != "sched" else None,
                    "cancelled": cancelled or skipped, "date": d.strftime("%Y%m%d"), "stop_id": r["stop_id"]})
        if len(results) >= limit:
            break
    results.sort(key=lambda x: x["expected"])
    return results[:limit]


# --------------------------------------------------------------------------- vehicles

_veh_cache = {"t": 0, "data": None}
_veh_lock = threading.Lock()
_trip_cache = {}


def _trip(db, slug, trip_id):
    k = (slug, db.version, trip_id)
    if k not in _trip_cache:
        if len(_trip_cache) > 20000:
            _trip_cache.clear()
        _trip_cache[k] = db.trip_by_id(trip_id)
    return _trip_cache[k]


def _stop_name(db, stop_id):
    r = db.q("SELECT name FROM stops WHERE stop_id=?", (stop_id,))
    if not r and stop_id and not stop_id.endswith(".0"):
        r = db.q("SELECT name FROM stops WHERE stop_id=?", (stop_id + ".0",))
    return r[0][0] if r else None


# ---- geometry helpers: follow the real track (GTFS shape) instead of a straight line

_shape_cache = {}
_dist_cache = {}
MAX_SNAP_M = 250      # a stop further than this from the shape is not snapped


def shape_geom(db, shape_id):
    """Planar (metre) version of a shape: (xs, ys, cumulative_length, lat0, cos0) or None."""
    key = (db.slug, db.version, shape_id)
    if key in _shape_cache:
        return _shape_cache[key]
    geom = None
    pts = db.shape(shape_id) if shape_id else None
    if pts and len(pts) >= 2:
        lat0 = pts[0][0]
        cos0 = math.cos(math.radians(lat0))
        xs = [p[1] * cos0 * 111320.0 for p in pts]
        ys = [p[0] * 110540.0 for p in pts]
        cum = [0.0]
        for i in range(1, len(xs)):
            cum.append(cum[-1] + math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]))
        geom = (xs, ys, cum, pts, cos0)
    if len(_shape_cache) > 400:
        _shape_cache.clear()
    _shape_cache[key] = geom
    return geom


def _project(geom, lat, lon, dmin, dmax):
    """Closest point of the shape to (lat, lon) searching only between along-track distances dmin..dmax."""
    xs, ys, cum, _, cos0 = geom
    px, py = lon * cos0 * 111320.0, lat * 110540.0
    n = len(xs)
    lo = max(bisect.bisect_right(cum, dmin) - 1, 0)
    hi = min(bisect.bisect_left(cum, dmax), n - 2)
    best = None
    for i in range(lo, hi + 1):
        ax, ay, bx, by = xs[i], ys[i], xs[i + 1], ys[i + 1]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
        ex, ey = ax + t * dx, ay + t * dy
        d2 = (px - ex) ** 2 + (py - ey) ** 2
        if best is None or d2 < best[0]:
            best = (d2, cum[i] + t * math.sqrt(l2))
    return (best[1], math.sqrt(best[0])) if best else None


def stop_distances(db, trip, rows):
    """Along-shape distance (m) of every stop of a trip, in stop order (None when it cannot be snapped)."""
    key = (db.slug, db.version, trip["tix"])
    if key in _dist_cache:
        return _dist_cache[key]
    geom = shape_geom(db, trip.get("shape_id"))
    out = [None] * len(rows)
    if geom:
        total = geom[2][-1]
        prev, prev_ll = 0.0, None
        for i, r in enumerate(rows):
            if not r["lat"] or not r["lon"]:
                continue
            # search window: forward from the previous stop, within a generous multiple of the straight distance
            if prev_ll is None:
                lo, hi = 0.0, total
            else:
                straight = haversine(prev_ll[0], prev_ll[1], r["lat"], r["lon"])
                lo, hi = max(prev - 30, 0.0), prev + max(4 * straight, 1500.0)
            res = _project(geom, r["lat"], r["lon"], lo, hi)
            if res and res[1] <= MAX_SNAP_M:
                out[i] = res[0]
                prev, prev_ll = res[0], (r["lat"], r["lon"])
        # stops that could not be snapped (e.g. in tunnels): place them between their snapped neighbours
        known = [i for i, v in enumerate(out) if v is not None]
        for i0, i1 in zip(known, known[1:]):
            gap = [i for i in range(i0 + 1, i1) if rows[i]["lat"] and rows[i]["lon"]]
            if not gap or out[i1] < out[i0]:
                continue
            chain = [i0] + gap + [i1]
            seg = [haversine(rows[a]["lat"], rows[a]["lon"], rows[b]["lat"], rows[b]["lon"]) for a, b in zip(chain, chain[1:])]
            tot = sum(seg) or 1.0
            acc = 0.0
            for k, i in enumerate(gap):
                acc += seg[k]
                out[i] = out[i0] + (out[i1] - out[i0]) * acc / tot
    if len(_dist_cache) > 20000:
        _dist_cache.clear()
    _dist_cache[key] = out
    return out


def _point_at(geom, d):
    """(lat, lon, bearing) at along-track distance d."""
    xs, ys, cum, pts, _ = geom
    i = min(max(bisect.bisect_right(cum, d) - 1, 0), len(xs) - 2)
    seg = cum[i + 1] - cum[i]
    f = 0.0 if seg <= 0 else min(max((d - cum[i]) / seg, 0.0), 1.0)
    la = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f
    lo = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f
    brg = math.degrees(math.atan2(xs[i + 1] - xs[i], ys[i + 1] - ys[i])) % 360
    return la, lo, brg


def _interp(eff, now, dists=None, geom=None):
    """Estimate a position from effective times.

    Follows the shape when stops could be snapped to it, otherwise a straight line.
    Returns (lat, lon, next_stop_name, status, bearing, on_track) or None.
    """
    pts = [(e, (dists[i] if dists else None)) for i, e in enumerate(eff) if e["lat"] and e["lon"]]
    if len(pts) < 2:
        return None
    if now < pts[0][0]["dep"] or now > pts[-1][0]["arr"]:
        return None
    for (a, da), (b, db) in zip(pts, pts[1:]):
        if a["arr"] <= now <= a["dep"]:
            return a["lat"], a["lon"], a["name"], "stopped", None, False
        if a["dep"] < now < b["arr"]:
            f = (now - a["dep"]) / max(b["arr"] - a["dep"], 1)
            if geom and da is not None and db is not None and db > da:
                la, lo, brg = _point_at(geom, da + f * (db - da))
                return la, lo, b["name"], "moving", brg, True
            brg = math.degrees(math.atan2((b["lon"] - a["lon"]) * math.cos(math.radians(a["lat"])), b["lat"] - a["lat"])) % 360
            return (a["lat"] + (b["lat"] - a["lat"]) * f, a["lon"] + (b["lon"] - a["lon"]) * f,
                    b["name"], "moving", brg, False)
    return None


def vehicles(max_age=10):
    with _veh_lock:
        if _veh_cache["data"] is not None and time.time() - _veh_cache["t"] < max_age:
            return _veh_cache["data"]
        data = _build_vehicles()
        _veh_cache.update(t=time.time(), data=data)
        return data


def _build_vehicles():
    now = int(time.time())
    slugs = [s for s, i in AGENCIES.items() if i["ready"] and (i["rt"].get("vehicles") or i["rt"].get("trips"))]
    refresh(slugs, ["vehicles", "trips"])
    out = []
    feeds = {}
    for slug in slugs:
        info = AGENCIES[slug]
        db = DBS[slug]
        vs, ts = feed_stats(slug, "vehicles"), feed_stats(slug, "trips")
        feeds[slug] = {"name": info["name"], "vehicles": vs, "trips": ts}
        tus = tu_index(slug) if ts["status"] in ("live", "stale") else {}
        vf = feed_for(slug, "vehicles")
        vlist = vf.data["vehicles"] if vf and vf.data and vs["status"] in ("live", "stale") else []
        try:
            for v in vlist:
                if not v.get("lat") or not v.get("lon") or abs(v["lat"]) < 1:
                    continue
                tinfo = v.get("trip") or {}
                trip = _trip(db, slug, tinfo.get("trip_id")) if tinfo.get("trip_id") else None
                route_id = tinfo.get("route_id") or (trip or {}).get("route_id")
                li = line_info(db, route_id)
                delay, hs = None, (trip or {}).get("headsign") or ""
                if trip and tus.get(trip["trip_id"]):
                    rows = db.trip_stop_times(trip["tix"])
                    d = resolve_service_date(db, trip, rows, now, tinfo.get("start_date"))
                    tu = pick_tu(tus[trip["trip_id"]], d)
                    if tu:
                        eff, canc = effective_times(slug, rows, d, tu)
                        nxt = next((e for e in eff if e["src"] == "rt" and e["dep"] >= now - 120), None) \
                            or next((e for e in eff if e["src"] == "rt"), None)
                        if nxt:
                            delay = nxt["dep"] - nxt["sched_dep"]
                vid = (v.get("vehicle") or {})
                out.append({
                    "id": "%s:%s" % (slug, vid.get("id") or v["id"]), "agency": slug, "agency_name": info["name"],
                    "label": vid.get("label") or vid.get("id") or "", "lat": round(v["lat"], 6),
                    "lon": round(v["lon"], 6), "bearing": v.get("bearing"),
                    "speed": round(v["speed"] * 3.6) if v.get("speed") is not None else None,
                    "route_id": route_id, "line": li["line"], "color": li["color"], "text_color": li["text_color"],
                    "mode": li["mode"], "headsign": hs or li["long"], "trip_id": tinfo.get("trip_id"),
                    "date": tinfo.get("start_date"),
                    "stop": _stop_name(db, v.get("stop_id")) if v.get("stop_id") else None,
                    "status": v.get("status"), "ts": fix_ts(slug, v.get("timestamp")), "delay": delay, "est": False,
                })
            if not vlist and tus:
                out.extend(_estimated_vehicles(slug, info, db, tus, now))
        except Exception:
            log.exception("vehicle build failed for %s", slug)
    data = {"time": now, "vehicles": out, "feeds": feeds}
    return data


def _estimated_vehicles(slug, info, db, tus, now):
    out = []
    for tid, lst in tus.items():
        trip = _trip(db, slug, tid)
        if not trip:
            continue
        tu = lst[0]
        if tu["trip"].get("rel") == 3:
            continue
        # quick reject: trips whose first reported stop is in the future and seq==1 are not running yet
        rows = db.trip_stop_times(trip["tix"])
        if len(rows) < 2:
            continue
        for tu in lst:
            d = resolve_service_date(db, trip, rows, now, tu["trip"].get("start_date"))
            eff, canc = effective_times(slug, rows, d, tu)
            if not any(e["src"] == "rt" for e in eff):
                continue
            geom = shape_geom(db, trip.get("shape_id"))
            pos = _interp(eff, now, stop_distances(db, trip, rows) if geom else None, geom)
            if not pos:
                continue
            li = line_info(db, trip["route_id"])
            rt = next((e for e in eff if e["src"] == "rt"), None)
            delay = (rt["dep"] - rt["sched_dep"]) if rt else None
            vid = (tu.get("vehicle") or {}).get("id") or tid
            out.append({
                "id": "%s:%s" % (slug, vid), "agency": slug, "agency_name": info["name"],
                "label": (tu.get("vehicle") or {}).get("label") or "", "lat": round(pos[0], 6),
                "lon": round(pos[1], 6), "bearing": round(pos[4]) if pos[4] is not None else None, "on_track": pos[5],
                "speed": None, "route_id": trip["route_id"],
                "line": li["line"], "color": li["color"], "text_color": li["text_color"], "mode": li["mode"],
                "headsign": trip["headsign"] or li["long"], "trip_id": tid, "date": d.strftime("%Y%m%d"),
                "stop": pos[2], "status": 1 if pos[3] == "stopped" else 2, "ts": fix_ts(slug, tu.get("timestamp")),
                "delay": delay, "est": True})
            break
    return out


# --------------------------------------------------------------------------- trip / route / stations

def trip_detail(slug, trip_id, date_str=None, now=None):
    now = int(now or time.time())
    db = DBS[slug]
    trip = db.trip_by_id(trip_id)
    if not trip:
        return None
    rows = db.trip_stop_times(trip["tix"])
    d = resolve_service_date(db, trip, rows, now, date_str)
    refresh([slug], ["trips"])
    tus = tu_index(slug)
    tu = pick_tu(tus.get(trip_id), d) if tus else None
    eff, canc = effective_times(slug, rows, d, tu)
    li = line_info(db, trip["route_id"])
    stops = [{"seq": e["seq"], "stop_id": e["stop_id"], "station_id": e["station_id"], "name": e["name"],
              "lat": e["lat"], "lon": e["lon"], "sched": e["sched_dep"], "sched_arr": e["sched_arr"],
              "expected": e["dep"], "expected_arr": e["arr"], "rt": e["src"] if e["src"] != "sched" else None,
              "skipped": e.get("skipped", False)} for e in eff]
    return {"trip_id": trip_id, "agency": slug, "route_id": trip["route_id"], "line": li["line"], "color": li["color"],
            "text_color": li["text_color"], "mode": li["mode"], "headsign": trip["headsign"] or li["long"],
            "cancelled": canc, "has_rt": tu is not None, "date": d.strftime("%Y%m%d"), "stops": stops,
            "shape": db.shape(trip["shape_id"])}


def route_detail(slug, route_id):
    db = DBS[slug]
    li = line_info(db, route_id)
    shapes, stops = [], []
    seen_dirs = set()
    for r in db.q("SELECT shape_id, direction, headsign, COUNT(*) c, MIN(tix) tix FROM trips WHERE route_id=? "
                  "GROUP BY shape_id, direction ORDER BY c DESC", (route_id,)):
        key = r["direction"]
        if key in seen_dirs and len(seen_dirs) >= 2:
            continue
        if key in seen_dirs:
            continue
        seen_dirs.add(key)
        rows = db.trip_stop_times(r["tix"])
        st = [{"station_id": x["station_id"], "name": x["name"], "lat": x["lat"], "lon": x["lon"]} for x in rows]
        shapes.append({"direction": r["direction"], "headsign": r["headsign"], "pts": db.shape(r["shape_id"]),
                       "stops": st})
        if len(seen_dirs) >= 2:
            break
    return dict(li, route_id=route_id, agency=slug, shapes=shapes)


def routes_of(slug):
    db = DBS[slug]
    out = []
    for r in db.routes().values():
        color, text, _ = route_style(db, r)
        out.append({"route_id": r["route_id"], "line": r["short"] or r["long"] or r["route_id"], "long": r["long"],
                    "color": color, "text_color": text, "mode": r["mode"]})
    return sorted(out, key=lambda r: _natkey(r["line"]))


def _natkey(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s or "")]


def _like(q):
    return "%" + q.replace("%", "").replace("_", "") + "%"


def search_stations(q, limit=40, lat=None, lon=None):
    qn = norm(q)
    if len(qn) < 2:
        return []
    res = []
    for slug, info in AGENCIES.items():
        if not info["ready"]:
            continue
        try:
            for r in DBS[slug].q("SELECT station_id, name, lat, lon, modes FROM stations WHERE name_norm LIKE ? LIMIT 60",
                                 (_like(qn),)):
                n = norm(r["name"])
                rank = 0 if n == qn else 1 if n.startswith(qn) else 2
                res.append({"agency": slug, "agency_name": info["name"], "station_id": r["station_id"],
                            "name": r["name"], "lat": r["lat"], "lon": r["lon"], "modes": r["modes"], "_r": rank})
        except Exception:
            log.exception("search failed in %s", slug)
    mode_rank = {"train": 0, "metro": 0, "tram": 1, "funicular": 1}
    res.sort(key=lambda r: (r["_r"], mode_rank.get((r["modes"] or "").split(",")[0], 2), len(r["name"]), r["name"]))
    for r in res:
        r.pop("_r")
    return res[:limit]


def stations_in_bbox(s, w, n, e, limit=600, rail_only=False):
    res = []
    for slug, info in AGENCIES.items():
        if not info["ready"]:
            continue
        for r in DBS[slug].q("SELECT station_id, name, lat, lon, modes FROM stations WHERE lat BETWEEN ? AND ? "
                             "AND lon BETWEEN ? AND ?", (s, n, w, e)):
            if rail_only and not (set((r["modes"] or "").split(",")) - {"bus", ""}):
                continue
            res.append({"agency": slug, "station_id": r["station_id"], "name": r["name"], "lat": r["lat"],
                        "lon": r["lon"], "modes": r["modes"]})
    return res[:limit * 3]


def nearby(lat, lon, radius=600, limit=15):
    dlat = radius / 111000.0
    dlon = radius / (111000.0 * max(0.2, abs(__import__("math").cos(__import__("math").radians(lat)))))
    out = []
    for r in stations_in_bbox(lat - dlat, lon - dlon, lat + dlat, lon + dlon, 5000):
        r["dist"] = int(haversine(lat, lon, r["lat"], r["lon"]))
        if r["dist"] <= radius:
            r["agency_name"] = AGENCIES[r["agency"]]["name"]
            out.append(r)
    out.sort(key=lambda r: r["dist"])
    return out[:limit]


# --------------------------------------------------------------------------- alerts

def alerts(slug_filter=None):
    now = time.time()
    slugs = [s for s, i in AGENCIES.items() if i["rt"].get("alerts") and i["ready"] and (not slug_filter or s == slug_filter)]
    refresh(slugs, ["alerts"])
    out = []
    for slug in slugs:
        f = feed_for(slug, "alerts")
        if not f or not f.data:
            continue
        for a in f.data["alerts"]:
            per = a.get("periods") or []
            if per:
                ok = any((not p.get("start") or fix_ts(slug, p["start"]) <= now) and
                         (not p.get("end") or now <= fix_ts(slug, p["end"])) for p in per)
                if not ok:
                    continue
            routes = DBS[slug].routes()
            rids = [e["route_id"] for e in (a.get("entities") or []) if e.get("route_id")]
            modes = sorted({routes[r]["mode"] for r in rids if r in routes})
            lines = sorted({(routes[r]["short"] or routes[r]["long"]) for r in rids if r in routes})
            out.append({"agency": slug, "agency_name": AGENCIES[slug]["name"], "id": a["id"],
                        "route_ids": rids, "modes": modes, "lines": lines,
                        "header": a.get("header") or {}, "description": a.get("description") or {},
                        "url": a.get("url") or {}, "effect": a.get("effect"), "cause": a.get("cause"),
                        "entities": a.get("entities") or [],
                        "end": fix_ts(slug, per[0]["end"]) if per and per[0].get("end") else None})
    return out


def agencies_summary():
    out = []
    for slug, info in sorted(AGENCIES.items(), key=lambda kv: kv[1]["name"].lower()):
        rt = {}
        for k in ("vehicles", "trips", "alerts"):
            if info["rt"].get(k):
                rt[k] = feed_stats(slug, k)
        modes = []
        if info["ready"]:
            try:
                modes = sorted({r["mode"] for r in DBS[slug].routes().values()})
            except Exception:
                pass
        out.append({"id": slug, "name": info["name"], "ready": info["ready"], "importing": info.get("importing"),
                    "error": info.get("error"), "modes": modes, "rt": rt, "gtfs_updated": info["gtfs_stamp"]})
    return out


def search_all(q, limit=25):
    """Stations + lines + operators matching q (accent/case-insensitive)."""
    qn = norm(q)
    res = {"stations": search_stations(q, limit), "routes": [], "operators": []}
    if len(qn) < 1:
        return res
    for slug, info in AGENCIES.items():
        if not info["ready"]:
            continue
        if len(qn) >= 3 and qn in norm(info["name"]):
            res["operators"].append({"agency": slug, "name": info["name"]})
        try:
            db = DBS[slug]
            for r in db.routes().values():
                short, long_ = norm(r["short"]), norm(r["long"])
                rank = 0 if short == qn else 1 if short.startswith(qn) else 2 if (len(qn) >= 3 and qn in long_) else None
                if rank is None:
                    continue
                color, text, _ = route_style(db, r)
                res["routes"].append({"agency": slug, "agency_name": info["name"], "route_id": r["route_id"],
                                      "line": r["short"] or r["long"] or r["route_id"], "long": r["long"],
                                      "color": color, "text_color": text, "mode": r["mode"], "_r": rank})
        except Exception:
            log.exception("route search failed in %s", slug)
    res["routes"].sort(key=lambda r: (r["_r"], _natkey(r["line"])))
    for r in res["routes"]:
        r.pop("_r")
    res["routes"] = res["routes"][:limit]
    return res
