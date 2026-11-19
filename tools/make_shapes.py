#!/usr/bin/env python3
"""Draw the road geometry of the patterns of a hand-transcribed feed (see staticfeeds.py).

    python3 tools/make_shapes.py labaztanesa            # writes feeds/labaztanesa_shapes.json

Each pattern (ordered stops a bus passes) is sent to a routing engine as waypoints and the road it answers with is
simplified (Douglas-Peucker, 8 m) and stored. Run it again only when the stops or patterns change; the result is
committed, so the app never calls the router. The default router is the public OSRM demo server: it is meant for
light use (this makes about ten requests, one per second) and its road data is OpenStreetMap's (ODbL).

Checks, because a stop placed on the wrong road makes the router take a huge detour: every leg is compared with the
straight line between its stops and the tool stops with an error when a leg is more than 3 times longer (+2 km).
"""
import json
import math
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import staticfeeds  # noqa: E402

ROUTER = os.environ.get("ROUTER_URL", "https://router.project-osrm.org/route/v1/driving/")
TOLERANCE_M = 8.0
UA = {"User-Agent": "mugitu/1.0 (personal use; one-off shape generation for a static timetable)"}


def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


def simplify(pts, tol):
    """Douglas-Peucker on (lat, lon) points; tol in metres."""
    if len(pts) < 3:
        return pts
    lat0 = pts[0][0]
    k = math.cos(math.radians(lat0))
    xy = [(p[1] * 111320.0 * k, p[0] * 110540.0) for p in pts]
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        ax, ay = xy[i]
        bx, by = xy[j]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        best, at = -1.0, None
        for m in range(i + 1, j):
            px, py = xy[m]
            t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
            d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d > best:
                best, at = d, m
        if best > tol:
            keep[at] = True
            stack += [(i, at), (at, j)]
    return [p for p, kp in zip(pts, keep) if kp]


def route(coords):
    """Road through the waypoints [(lat, lon)...]: (points, [leg distance in m])."""
    path = ";".join("%.6f,%.6f" % (lon, lat) for lat, lon in coords)
    url = ROUTER + path + "?overview=full&geometries=geojson&steps=false&continue_straight=false"
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                d = json.loads(r.read())
            if d.get("code") != "Ok":
                raise RuntimeError("router said %s" % d.get("code"))
            rt = d["routes"][0]
            return [(lat, lon) for lon, lat in rt["geometry"]["coordinates"]], [leg["distance"] for leg in rt["legs"]]
        except Exception as e:
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("router failed: %s" % last)


def main(name):
    feed = staticfeeds.load(name)
    staticfeeds.validate(feed)
    stops = feed["stops"]
    out, problems = {}, []
    for pat, codes in feed["patterns"].items():
        if pat.startswith("_"):
            continue
        coords = [(stops[c]["lat"], stops[c]["lon"]) for c in codes]
        pts, legs = route(coords)
        for (a, b), m in zip(zip(codes, codes[1:]), legs):
            straight = hav((stops[a]["lat"], stops[a]["lon"]), (stops[b]["lat"], stops[b]["lon"]))
            if m > 3 * straight + 2000:
                problems.append("%s: %s->%s road %.1f km for %.1f km in a straight line" % (pat, a, b, m / 1000, straight / 1000))
        simple = simplify(pts, TOLERANCE_M)
        out[pat] = [[round(lat, 5), round(lon, 5)] for lat, lon in simple]
        print("%-12s %2d stops  %5.1f km  %5d -> %4d points" % (pat, len(codes), sum(legs) / 1000, len(pts), len(simple)), flush=True)
        time.sleep(1.1)
    if problems:
        print("\nPROBLEMS (fix the stop coordinates, then run again):")
        print("\n".join("  " + p for p in problems))
        sys.exit(1)
    dest = os.path.join(staticfeeds.FEEDS_DIR, name + "_shapes.json")
    with open(dest, "w", encoding="utf-8") as f:
        f.write('{"router": "%s", "tolerance_m": %s, "generated": "%s", "shapes": {\n' % (ROUTER, TOLERANCE_M, time.strftime("%Y-%m-%d")))
        f.write(",\n".join('"%s": %s' % (k, json.dumps(v, separators=(",", ":"))) for k, v in out.items()))
        f.write("\n}}\n")
    print("wrote", dest)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
