"""Minimal, dependency-free GTFS-Realtime (protobuf) decoder.

Only the fields this app needs are decoded. Returns plain dicts.
"""
import struct


def _varint(b, i):
    r = 0
    s = 0
    while True:
        c = b[i]
        i += 1
        r |= (c & 0x7F) << s
        if not c & 0x80:
            return r, i
        s += 7


def _fields(b):
    """Yield (field_number, wire_type, value) for a message buffer."""
    i, n = 0, len(b)
    while i < n:
        k, i = _varint(b, i)
        f, w = k >> 3, k & 7
        if w == 0:
            v, i = _varint(b, i)
        elif w == 1:
            v = b[i:i + 8]
            i += 8
        elif w == 2:
            ln, i = _varint(b, i)
            v = b[i:i + ln]
            i += ln
        elif w == 5:
            v = b[i:i + 4]
            i += 4
        else:
            raise ValueError("unsupported wire type %d" % w)
        yield f, w, v


def _s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def _s64(v):
    return v - (1 << 64) if v & (1 << 63) else v


def _str(v):
    return v.decode("utf-8", "replace")


def _f32(v):
    return struct.unpack("<f", v)[0]


def _trip(b):
    d = {}
    for f, w, v in _fields(b):
        if f == 1: d["trip_id"] = _str(v)
        elif f == 2: d["start_time"] = _str(v)
        elif f == 3: d["start_date"] = _str(v)
        elif f == 4: d["rel"] = v
        elif f == 5: d["route_id"] = _str(v)
        elif f == 6: d["direction_id"] = v
    return d


def _vehicle_desc(b):
    d = {}
    for f, w, v in _fields(b):
        if f == 1: d["id"] = _str(v)
        elif f == 2: d["label"] = _str(v)
        elif f == 3: d["plate"] = _str(v)
    return d


def _event(b):
    d = {}
    for f, w, v in _fields(b):
        if f == 1: d["delay"] = _s32(v)
        elif f == 2: d["time"] = _s64(v)
    return d


def _stu(b):
    d = {}
    for f, w, v in _fields(b):
        if f == 1: d["seq"] = v
        elif f == 2: d["arr"] = _event(v)
        elif f == 3: d["dep"] = _event(v)
        elif f == 4: d["stop_id"] = _str(v)
        elif f == 5: d["rel"] = v  # 0 scheduled, 1 skipped, 2 no_data
    return d


def _trip_update(b):
    d = {"stus": []}
    for f, w, v in _fields(b):
        if f == 1: d["trip"] = _trip(v)
        elif f == 2: d["stus"].append(_stu(v))
        elif f == 3: d["vehicle"] = _vehicle_desc(v)
        elif f == 4: d["timestamp"] = v
        elif f == 5: d["delay"] = _s32(v)
    return d


def _position(b):
    d = {}
    for f, w, v in _fields(b):
        if f == 1: d["lat"] = _f32(v)
        elif f == 2: d["lon"] = _f32(v)
        elif f == 3: d["bearing"] = _f32(v)
        elif f == 5: d["speed"] = _f32(v)
    return d


def _vehicle(b):
    d = {}
    for f, w, v in _fields(b):
        if f == 1: d["trip"] = _trip(v)
        elif f == 2: d.update(_position(v))
        elif f == 3: d["seq"] = v
        elif f == 4: d["status"] = v  # 0 incoming, 1 stopped, 2 in transit
        elif f == 5: d["timestamp"] = v
        elif f == 7: d["stop_id"] = _str(v)
        elif f == 8: d["vehicle"] = _vehicle_desc(v)
        elif f == 9: d["occupancy"] = v
    return d


def _translated(b):
    out = {}
    for f, w, v in _fields(b):
        if f == 1:
            t, lang = "", ""
            for f2, w2, v2 in _fields(v):
                if f2 == 1: t = _str(v2)
                elif f2 == 2: lang = _str(v2)
            out[lang or "und"] = t
    return out


def _entity_sel(b):
    d = {}
    for f, w, v in _fields(b):
        if f == 1: d["agency_id"] = _str(v)
        elif f == 2: d["route_id"] = _str(v)
        elif f == 3: d["route_type"] = v
        elif f == 4: d["trip_id"] = _trip(v).get("trip_id")
        elif f == 5: d["stop_id"] = _str(v)
    return d


def _alert(b):
    d = {"periods": [], "entities": []}
    for f, w, v in _fields(b):
        if f == 1:
            p = {}
            for f2, w2, v2 in _fields(v):
                if f2 == 1: p["start"] = v2
                elif f2 == 2: p["end"] = v2
            d["periods"].append(p)
        elif f == 5: d["entities"].append(_entity_sel(v))
        elif f == 6: d["cause"] = v
        elif f == 7: d["effect"] = v
        elif f == 8: d["url"] = _translated(v)
        elif f == 10: d["header"] = _translated(v)
        elif f == 11: d["description"] = _translated(v)
    return d


def decode(data):
    """Decode a FeedMessage. Returns {'timestamp', 'trip_updates', 'vehicles', 'alerts'}."""
    out = {"timestamp": 0, "trip_updates": [], "vehicles": [], "alerts": []}
    for f, w, v in _fields(data):
        if f == 1:
            for f2, w2, v2 in _fields(v):
                if f2 == 3:
                    out["timestamp"] = v2
        elif f == 2:
            eid = ""
            for f2, w2, v2 in _fields(v):
                if f2 == 1: eid = _str(v2)
                elif f2 == 3:
                    t = _trip_update(v2); t["id"] = eid
                    out["trip_updates"].append(t)
                elif f2 == 4:
                    t = _vehicle(v2); t["id"] = eid
                    out["vehicles"].append(t)
                elif f2 == 5:
                    t = _alert(v2); t["id"] = eid
                    out["alerts"].append(t)
    return out
