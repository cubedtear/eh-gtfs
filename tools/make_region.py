#!/usr/bin/env python3
"""Rebuild region.py: the Euskal Herria outline, simplified from OpenStreetMap relation 11107464.

    python3 tools/make_region.py [tolerance_degrees]      # default 0.002 (about 200 m)

Downloads the exact multipolygon from polygons.openstreetmap.fr, drops specks smaller than ~1 km2 and
simplifies the rings with Douglas-Peucker. The result is a few hundred points instead of 28 000, which is
plenty to decide whether a bus stop is inside the territory.
"""
import json
import math
import os
import ssl
import sys
import urllib.request

RELATION = 11107464
URL = "https://polygons.openstreetmap.fr/get_geojson.py?id=%d&params=0" % RELATION
MIN_AREA = 0.0001          # square degrees (~1 km2)


def douglas_peucker(pts, eps):
    n = len(pts)
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        far, dist = -1, 0.0
        for i in range(a + 1, b):
            px, py = pts[i]
            if l2 == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
                d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d > dist:
                far, dist = i, d
        if dist > eps:
            keep[far] = True
            stack += [(a, far), (far, b)]
    return [p for p, k in zip(pts, keep) if k]


def area(r):
    return abs(sum(r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1] for i in range(len(r)))) / 2


def main():
    eps = float(sys.argv[1]) if len(sys.argv) > 1 else 0.002
    req = urllib.request.Request(URL, headers={"User-Agent": "mugitu-region-builder/1.0"})
    ctx = ssl.create_default_context()      # Python 3.13's strict X.509 check rejects some hosts' certificates
    ctx.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)
    geo = json.load(urllib.request.urlopen(req, timeout=120, context=ctx))
    rings = []
    for poly in geo["coordinates"]:
        ring = poly[0][:-1]
        if area(ring) < MIN_AREA:
            continue
        s = douglas_peucker(ring + [ring[0]], eps)[:-1]
        if len(s) >= 3:
            rings.append([[round(x, 4), round(y, 4)] for x, y in s])
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "region.py")
    template = open(out, encoding="utf-8").read()
    i = template.index("RINGS = ")
    head, tail = template[:i], template[template.index("\n", i) + 1:]      # keep the code around the data line
    with open(out, "w", encoding="utf-8") as f:
        f.write(head + "RINGS = " + json.dumps(rings, separators=(",", ":")) + "\n" + tail)
    print("%d rings, %d points -> %s" % (len(rings), sum(len(r) for r in rings), out))


if __name__ == "__main__":
    main()
