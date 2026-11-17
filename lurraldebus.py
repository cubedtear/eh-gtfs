"""Lurraldebus live arrivals (scraped from the public "real time" stop page).

    https://lurraldebus.eus/real/result/0/<stop_id>

The stop_id is the GTFS stop_id of the Lurraldebus operators. The page is server-rendered HTML (about 400 kB,
60 kB gzipped) listing the next bus of every line that will call at the stop, with the minutes left and the
occupancy reported by the vehicle. There is no JSON API, so this module is deliberately defensive:

* every response is parsed structurally; a page that is neither a result table nor the "no information"
  page counts as a failure (the site layout changed) and is never cached as "empty";
* all callers share one cache, concurrent requests for the same stop collapse into one (single flight);
* a token bucket caps the request rate, with part of the budget reserved for interactive requests so the
  background tracker can never starve a user who just opened a stop;
* a circuit breaker with exponential back-off stops all requests while the site is failing; stale data
  (a few minutes old) is served meanwhile.

Only the Python standard library is used.
"""
import gzip
import html
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime

from store import TZ

log = logging.getLogger("moveuskadi.lurraldebus")

URL = "https://lurraldebus.eus/real/result/0/%s"
UA = "mugitu/1.0 (personal use; low-rate, cached)"
ENABLED = os.environ.get("LURRALDEBUS_LIVE", "1") != "0"


def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


RATE = _env_float("LURRALDEBUS_RATE", 1.0)   # sustained requests per second, all callers together
BURST = 4                    # short bursts allowed (opening a few favourites at once)
BG_RESERVE = 2               # tokens that background requests must leave for interactive ones
MAX_PARALLEL = 2             # simultaneous connections to lurraldebus.eus
TIMEOUT = 10                 # seconds
TTL_OK = 30                  # a result with arrivals is reused for this long
TTL_EMPTY = 120              # a stop without information is not asked again for this long
STALE_MAX = 300              # while the site is failing, results up to this old are still served
MAX_BYTES = 3 << 20
_STOP_RE = re.compile(r"^[A-Za-z0-9_.-]{1,16}$")

# --------------------------------------------------------------------------- parsing

_ROW_SPLIT = '<td class="live-line-left">'
_LINE = re.compile(r'class="line-number">\s*(.*?)\s*<', re.S)
_NAME = re.compile(r'class="line-name">\s*(.*?)\s*</p>', re.S)
_FLAG = re.compile(r"lb-badge--(\w+)")
_OCC = re.compile(r"ocupacion.*?<span[^>]*>\s*(.*?)\s*</span>", re.S)
_DEST = re.compile(r'<td class="line-direction">\s*(.*?)\s*</td>', re.S)
_TIME = re.compile(r'class="live-line-time">.*?<span>\s*(.*?)\s*</span>', re.S)
_NO_INFO = 'class="no-result-content"'

# the badge next to the line number, as published by the site ("bajada" = alight only)
FLAG_NAMES = {"bajada": "drop_off_only", "subida": "pick_up_only"}


def parse_eta(text, now=None):
    """Minutes until arrival from the site's text ("03 min", "1 h 05 min", "12:40", "") or None."""
    s = (text or "").strip().lower()
    if not s:
        return None
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", s)
    if m:   # absolute clock time
        now = now or time.time()
        n = datetime.fromtimestamp(now, TZ)
        mins = (int(m.group(1)) * 60 + int(m.group(2))) - (n.hour * 60 + n.minute)
        return mins + 1440 if mins < -120 else mins
    h = re.search(r"(\d+)\s*(?:h|ord)", s)
    mi = re.search(r"(\d+)\s*min", s)
    if h or mi:
        return (int(h.group(1)) * 60 if h else 0) + (int(mi.group(1)) if mi else 0)
    if not re.search(r"\d", s):   # words such as "orain" / "ahora" (now)
        return 0
    return None


def parse(page, now=None):
    """Parse a result page -> (status, arrivals).

    status: 'ok' (>= 1 arrival), 'empty' (the site says there is no information) or 'unparsed'.
    Each arrival: {line, name, headsign, minutes, occupancy, flags}.
    """
    if _ROW_SPLIT not in page:
        return ("empty" if _NO_INFO in page else "unparsed"), []
    chunks = page.split(_ROW_SPLIT)[1:]
    chunks[-1] = chunks[-1].split("</table>")[0]
    out = []
    for c in chunks:
        ln, tm = _LINE.search(c), _TIME.search(c)
        minutes = parse_eta(html.unescape(tm.group(1)), now) if tm else None
        if not ln or minutes is None:
            continue
        occ = _OCC.search(c)
        occ_txt = html.unescape(occ.group(1)).strip() if occ else ""
        name, dest = _NAME.search(c), _DEST.search(c)
        out.append({
            "line": html.unescape(ln.group(1)).strip(),
            "name": html.unescape(name.group(1)).strip() if name else "",
            "headsign": html.unescape(dest.group(1)).strip() if dest else "",
            "minutes": minutes,
            "occupancy": int(occ_txt) if occ_txt.isdigit() else None,
            "flags": sorted({FLAG_NAMES.get(f, f) for f in _FLAG.findall(c)}),
        })
    return ("ok" if out else "unparsed"), out


# --------------------------------------------------------------------------- rate limiting

class _Bucket:
    """Token bucket. Background callers must leave `reserve` tokens for interactive ones."""

    def __init__(self, rate, burst):
        self.rate, self.burst = max(rate, 0.05), burst
        self.tokens = float(burst)
        self.t = time.monotonic()
        self.lock = threading.Lock()

    def take(self, wait=0.0, reserve=0.0):
        deadline = time.monotonic() + wait
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.burst, self.tokens + (now - self.t) * self.rate)
                self.t = now
                if self.tokens - 1 >= reserve:
                    self.tokens -= 1
                    return True
                need = (1 + reserve - self.tokens) / self.rate
            if time.monotonic() + need > deadline:
                return False
            time.sleep(min(need, 0.25))


# --------------------------------------------------------------------------- client

class Client:
    def __init__(self, rate=None, fetch=None):
        self.bucket = _Bucket(RATE if rate is None else rate, BURST)
        self.slots = threading.BoundedSemaphore(MAX_PARALLEL)
        self.cache = {}                      # stop_id -> result dict
        self.locks = {}                      # stop_id -> Lock (single flight)
        self.meta = threading.Lock()
        self.fail = 0                        # consecutive failures
        self.open_until = 0.0                # circuit breaker
        self.last_ok = 0.0
        self.last_error = ""
        self.sent = deque(maxlen=4000)       # request timestamps (for the stats)
        self.errors = deque(maxlen=200)
        self._fetch = fetch or self._http

    # ---- low level
    def _http(self, stop_id):
        req = urllib.request.Request(URL % stop_id, headers={
            "User-Agent": UA, "Accept-Encoding": "gzip", "Accept-Language": "eu,es;q=0.8,en;q=0.5"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(MAX_BYTES)
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
        return raw.decode("utf-8", "replace")

    def _failed(self, why, retry_after=0):
        with self.meta:
            self.fail += 1
            self.last_error = why[:120]
            self.errors.append(time.time())
            if self.fail >= 3 or retry_after:
                delay = max(retry_after, min(30 * 2 ** (self.fail - 3), 600))
                self.open_until = time.time() + delay
                log.warning("lurraldebus.eus failing (%s); pausing requests for %ds", why, delay)

    def _succeeded(self):
        with self.meta:
            self.fail, self.open_until, self.last_ok = 0, 0.0, time.time()

    def _lock(self, stop_id):
        with self.meta:
            return self.locks.setdefault(stop_id, threading.Lock())

    # ---- public
    def peek(self, stop_id):
        return self.cache.get(stop_id)

    def get(self, stop_id, max_age=TTL_OK, background=False, wait=4.0):
        """Live arrivals for a stop: result dict {status, arrivals, fetched, stale} or None.

        Returns a cached result when it is fresh enough, otherwise fetches (one request per stop at a time,
        rate limited). None means "no data and could not ask" (disabled, invalid id, paused or throttled).
        """
        if not ENABLED or not stop_id or not _STOP_RE.match(stop_id):
            return None
        now = time.time()
        hit = self.cache.get(stop_id)
        if hit and now - hit["fetched"] <= (max(max_age, TTL_EMPTY) if hit["status"] == "empty" else max_age):
            return hit
        with self._lock(stop_id):
            hit = self.cache.get(stop_id)    # somebody else may have just fetched it
            now = time.time()
            if hit and now - hit["fetched"] <= (max(max_age, TTL_EMPTY) if hit["status"] == "empty" else max_age):
                return hit
            stale = hit if hit and now - hit["fetched"] <= STALE_MAX else None
            if now < self.open_until:
                return dict(stale, stale=True) if stale else None
            if not self.bucket.take(0 if background else wait, BG_RESERVE if background else 0):
                return dict(stale, stale=True) if stale else None
            with self.slots:
                t0 = time.time()
                self.sent.append(t0)
                try:
                    page = self._fetch(stop_id)
                except urllib.error.HTTPError as e:
                    ra = e.headers.get("Retry-After", "") if e.headers else ""
                    self._failed("HTTP %s" % e.code, int(ra) if ra.isdigit() and e.code in (429, 503) else 0)
                    return dict(stale, stale=True) if stale else None
                except Exception as e:
                    self._failed(type(e).__name__)
                    return dict(stale, stale=True) if stale else None
            fetched = time.time()
            status, arrivals = parse(page, fetched)
            if status == "unparsed":
                self._failed("unrecognised page layout")
                return dict(stale, stale=True) if stale else None
            self._succeeded()
            res = {"stop_id": stop_id, "status": status, "arrivals": arrivals, "fetched": fetched,
                   "stale": False, "ms": int((fetched - t0) * 1000)}
            self.cache[stop_id] = res
            return res

    def stats(self):
        now = time.time()
        hour = sum(1 for t in self.sent if now - t < 3600)
        state = "off" if not ENABLED else "paused" if now < self.open_until else \
            "live" if self.last_ok and now - self.last_ok < 600 else "idle"
        return {"state": state, "requests_hour": hour, "errors_hour": sum(1 for t in self.errors if now - t < 3600),
                "cached": len(self.cache), "last_ok": int(self.last_ok) or None, "last_error": self.last_error,
                "paused_for": max(0, int(self.open_until - now))}


client = Client()
