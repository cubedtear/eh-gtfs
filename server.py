#!/usr/bin/env python3
"""Euskadi Transit Board - local web server (static UI + JSON API over GTFS / GTFS-RT).

Run:  python3 server.py [--port 8000] [--host 127.0.0.1]
Only the Python 3.9+ standard library is required.
"""
import argparse
import gzip
import json
import logging
import mimetypes
import os
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import core

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(ROOT, "static")


def _f(q, k, default=None):
    try:
        return float(q[k][0])
    except (KeyError, ValueError, IndexError):
        return default


def _s(q, k, default=""):
    return q.get(k, [default])[0]


def api(path, q):
    if path == "/api/agencies":
        core.refresh(list(core.AGENCIES), ["vehicles", "trips", "alerts"]) if _s(q, "probe") else None
        return {"time": int(time.time()), "agencies": core.agencies_summary()}
    if path == "/api/vehicles":
        return core.vehicles()
    if path == "/api/search":
        r = core.search_all(_s(q, "q"))
        return {"results": r["stations"], "routes": r["routes"], "operators": r["operators"]}
    if path == "/api/nearby":
        lat, lon = _f(q, "lat"), _f(q, "lon")
        if lat is None or lon is None:
            return {"results": []}
        return {"results": core.nearby(lat, lon, _f(q, "radius", 600))}
    if path == "/api/stations":
        s, w, n, e = (_f(q, k) for k in ("s", "w", "n", "e"))
        if None in (s, w, n, e):
            return {"stations": []}
        return {"stations": core.stations_in_bbox(s, w, n, e, rail_only=_s(q, "rail") == "1")}
    if path == "/api/departures":
        slug, sid = _s(q, "agency"), _s(q, "station")
        if slug not in core.DBS or not core.AGENCIES[slug]["ready"]:
            return {"error": "unknown agency"}
        st = core.DBS[slug].station(sid)
        if not st:
            return {"error": "unknown station"}
        kind = "arr" if _s(q, "kind") == "arr" else "dep"
        res = core.departures(slug, sid, kind, int(_f(q, "limit", 15)))
        info = core.AGENCIES[slug]
        trips_stat = core.feed_stats(slug, "trips") if info["rt"].get("trips") else {"status": "none"}
        return {"station": dict(st, agency=slug, agency_name=info["name"]), "kind": kind,
                "time": int(time.time()), "items": res or [], "rt_status": trips_stat["status"],
                "alerts": [a for a in core.alerts(slug) if _alert_applies(a, slug, sid, res or [])]}
    if path == "/api/trip":
        slug = _s(q, "agency")
        if slug not in core.DBS:
            return {"error": "unknown agency"}
        res = core.trip_detail(slug, _s(q, "trip"), _s(q, "date") or None)
        return res or {"error": "unknown trip"}
    if path == "/api/route":
        slug = _s(q, "agency")
        if slug not in core.DBS:
            return {"error": "unknown agency"}
        return core.route_detail(slug, _s(q, "route"))
    if path == "/api/routes":
        slug = _s(q, "agency")
        if slug not in core.DBS:
            return {"error": "unknown agency"}
        return {"routes": core.routes_of(slug)}
    if path == "/api/alerts":
        return {"alerts": core.alerts(_s(q, "agency") or None)}
    return None


def _alert_applies(a, slug, station_id, items):
    routes = {i["route_id"] for i in items}
    stops = set(core.DBS[slug].station_stops(station_id))
    for e in a["entities"]:
        if e.get("route_id") in routes or (e.get("stop_id") and e["stop_id"] in stops):
            return True
    return False


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "EuskadiTransit/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("DEBUG_HTTP"):
            super().log_message(fmt, *args)

    def _send(self, code, body, ctype, extra=None):
        accept = self.headers.get("Accept-Encoding", "")
        if len(body) > 1024 and "gzip" in accept:
            body = gzip.compress(body, 5)
            enc = True
        else:
            enc = False
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if enc:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Vary", "Accept-Encoding")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/api/"):
            try:
                res = api(u.path, parse_qs(u.query))
            except Exception as e:
                logging.getLogger("moveuskadi").error("API error %s: %s", self.path, traceback.format_exc())
                return self._send(500, json.dumps({"error": str(e)}).encode(), "application/json",
                                  {"Cache-Control": "no-store"})
            if res is None:
                return self._send(404, b'{"error":"not found"}', "application/json")
            return self._send(200, json.dumps(res, separators=(",", ":")).encode(), "application/json",
                              {"Cache-Control": "no-store"})
        rel = "index.html" if u.path in ("", "/") else u.path.lstrip("/")
        fp = os.path.normpath(os.path.join(STATIC, rel))
        if not fp.startswith(STATIC + os.sep) or not os.path.isfile(fp):
            return self._send(404, b"not found", "text/plain")
        ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
        if fp.endswith(".webmanifest"):
            ctype = "application/manifest+json"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "application/manifest+json"):
            ctype += "; charset=utf-8"
        with open(fp, "rb") as f:
            self._send(200, f.read(), ctype, {"Cache-Control": "no-cache"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    threading.Thread(target=core.updater_loop, daemon=True).start()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    srv.daemon_threads = True
    print("Serving on http://%s:%d" % (a.host, a.port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
