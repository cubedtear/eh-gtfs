'use strict';
/* Euskadi Transit – front-end. Talks to the local server's /api/* endpoints. */

// ───────────────────────────────────────────────────────────── icons (inline SVG, Material-style)
const P = d => `<path d="${d}"/>`;
const STROKE = d => `<path d="${d}" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>`;
const ICONS = {
  bus: P('M4 16c0 .88.39 1.67 1 2.22V20c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h8v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1.78c.61-.55 1-1.34 1-2.22V6c0-3.5-3.58-4-8-4s-8 .5-8 4v10zm3.5 1c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zm9 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm1.5-6H6V6h12v5z'),
  train: P('M12 2c-4 0-8 .5-8 4v9.5C4 17.43 5.57 19 7.5 19L6 20.5v.5h2.23l2-2H14l2 2h2v-.5L16.5 19c1.93 0 3.5-1.57 3.5-3.5V6c0-3.5-3.58-4-8-4zM7.5 17c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zm3.5-7H6V6h5v4zm2 0V6h5v4h-5zm3.5 7c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z'),
  metro: P('M12 2c-4.42 0-8 .5-8 4v9.5C4 17.43 5.57 19 7.5 19L6 20.5v.5h12v-.5L16.5 19c1.93 0 3.5-1.57 3.5-3.5V6c0-3.5-3.58-4-8-4zM7.5 17c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zm3.5-6H6V6h5v5zm5.5 6c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM18 11h-5V6h5v5z'),
  tram: P('M19 16.94V8.5c0-2.79-2.61-3.4-6.01-3.49l.76-1.51H17V2H7v1.5h4.75l-.76 1.52C7.86 5.11 5 5.73 5 8.5v8.44c0 1.45 1.19 2.66 2.59 2.97L6 21.5v.5h2.23l2-2H14l2 2h2v-.5L16.5 20h-.08c1.69 0 2.58-1.37 2.58-3.06zm-7 1.56c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm5-4.5H7V9h10v5z'),
  funicular: '<path fill-rule="evenodd" d="M2.5 6.2l19-3.4.35 2L13 6.9V9h4.5a2.5 2.5 0 0 1 2.5 2.5v7a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 18.5v-7A2.5 2.5 0 0 1 6.5 9H11V7.3L2.15 8.2zM7 12v4h10v-4z"/>',
  ferry: P('M20 21c-1.39 0-2.78-.47-4-1.32-2.44 1.71-5.56 1.71-8 0C6.78 20.53 5.39 21 4 21H2v2h2c1.38 0 2.74-.35 4-.99 2.52 1.29 5.48 1.29 8 0 1.26.65 2.62.99 4 .99h2v-2h-2zM3.95 19H4c1.6 0 3.02-.88 4-2 .98 1.12 2.4 2 4 2s3.02-.88 4-2c.98 1.12 2.4 2 4 2h.05l1.89-6.68c.08-.26.06-.54-.06-.78s-.34-.42-.6-.5L20 10.62V6c0-1.1-.9-2-2-2h-3V1H9v3H6c-1.1 0-2 .9-2 2v4.62l-1.29.42c-.26.08-.48.26-.6.5s-.15.52-.06.78L3.95 19zM6 6h12v3.97L12 8 6 9.97V6z'),
  target: P('M12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm8.94 3c-.46-4.17-3.77-7.48-7.94-7.94V1h-2v2.06C6.83 3.52 3.52 6.83 3.06 11H1v2h2.06c.46 4.17 3.77 7.48 7.94 7.94V23h2v-2.06c4.17-.46 7.48-3.77 7.94-7.94H23v-2h-2.06zM12 19c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z'),
  star: P('M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z'),
  starO: P('M22 9.24l-7.19-.62L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.63-7.03L22 9.24zM12 15.4l-3.76 2.27 1-4.28-3.32-2.88 4.38-.38L12 6.1l1.71 4.04 4.38.38-3.32 2.88 1 4.28L12 15.4z'),
  warn: P('M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z'),
  back: P('M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z'),
  refresh: P('M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z'),
  chev: P('M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z'),
  close: P('M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z'),
  route: STROKE('M4 19c4 0 3-7 8-7s4-7 8-7'),
  pin: P('M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z'),
  link: P('M19 19H5V5h7V3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z'),
  car: P('M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 4a2 2 0 1 1 0 4 2 2 0 0 1 0-4zm0 12.2c-2.1 0-3.9-1.1-5-2.7.03-1.65 3.3-2.55 5-2.55s4.97.9 5 2.55c-1.1 1.6-2.9 2.7-5 2.7z'),
};
const ic = (name, cls = '') => `<svg class="ic ${cls}" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">${ICONS[name] || ''}</svg>`;

// ───────────────────────────────────────────────────────────── state & helpers
const MODES = ['bus', 'train', 'metro', 'tram', 'funicular', 'ferry'];
const MODE_COLOR = { bus: '#2d6cdf', train: '#c0392b', metro: '#e8590c', tram: '#12926f', funicular: '#8e44ad', ferry: '#0b7285' };
const POLL_VEHICLES_MS = 15000;
const POLL_VIEW_MS = 20000;
const BUS_MIN_ZOOM = 11;      // buses are hidden below this zoom unless a scope filter is active
const STOP_MIN_ZOOM = 14;     // bus stops appear from this zoom; rail stations from 11

const S = {
  lang: localStorage.getItem('lang') || (navigator.language || 'en').slice(0, 2),
  tab: 'stops',
  view: { name: 'home' },
  hist: [],
  agencies: {},          // id -> summary
  vehicles: [],
  feeds: {},
  skew: 0,               // server time - client time (s)
  filters: { modes: new Set(MODES), agencies: null, est: true, showStops: true, line: null },
  focus: null,           // {agency, route_id?, trip_id?} while a trip / route view is open
  selVeh: null,          // selected vehicle id
  favs: JSON.parse(localStorage.getItem('favs') || '[]'),
  nearby: null,
  me: null,
  alerts: [],
  linesAgency: localStorage.getItem('linesAgency') || '',
  routesCache: {},
};
if (!I18N[S.lang]) S.lang = 'en';
try {
  const f = JSON.parse(localStorage.getItem('filters2') || 'null');
  if (f) {
    S.filters.modes = new Set(f.modes); S.filters.agencies = f.agencies ? new Set(f.agencies) : null;
    S.filters.est = f.est !== false; S.filters.showStops = f.showStops !== false; S.filters.line = f.line || null;
  }
} catch (e) { /* ignore */ }
function saveFilters() {
  const f = S.filters;
  localStorage.setItem('filters2', JSON.stringify({ modes: [...f.modes], agencies: f.agencies ? [...f.agencies] : null, est: f.est, showStops: f.showStops, line: f.line }));
  updateAlertBadge();
}

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const t = k => (I18N[S.lang] && I18N[S.lang][k]) || I18N.en[k] || k;
const fold = s => String(s == null ? '' : s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const nowTs = () => Date.now() / 1000 + S.skew;
const pad = n => String(n).padStart(2, '0');
const clock = ts => { const d = new Date(ts * 1000); return pad(d.getHours()) + ':' + pad(d.getMinutes()); };
const clockS = ts => { const d = new Date(ts * 1000); return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds()); };
const saveFavs = () => localStorage.setItem('favs', JSON.stringify(S.favs));
const isFav = (a, id) => S.favs.some(f => f.agency === a && f.station_id === id);
const agName = id => (S.agencies[id] && S.agencies[id].name) || id;
const modeLabel = m => t('mode_' + m);
const modeSvg = (m, cls = '') => `<span class="mi ${cls}" style="color:${MODE_COLOR[m] || MODE_COLOR.bus}">${ic(m in ICONS ? m : 'bus')}</span>`;
const modeIcons = modes => (modes || '').split(',').filter(Boolean).map(m => modeSvg(m)).join('');
const stationModes = s => (s.modes || 'bus').split(',').filter(Boolean);

async function api(path, params) {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  const ctl = new AbortController();
  const to = setTimeout(() => ctl.abort(), 25000);
  try {
    const r = await fetch('/api/' + path + qs, { signal: ctl.signal, cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } finally { clearTimeout(to); }
}

/** "Updated 30 s ago" in the current language (word order differs, e.g. Basque). */
function updatedAgo(ts) {
  const sec = Math.max(0, Math.round(nowTs() - ts));
  const long = sec >= 90;
  const n = long ? Math.round(sec / 60) : sec;
  return t('upd_ago').replace('{n}', n).replace('{u}', t(long ? 'unit_min' : 'unit_s'));
}

function fmtDelay(sec) {
  if (sec == null) return '';
  const m = Math.round(sec / 60);
  if (Math.abs(sec) < 60) return t('on_time');
  return (m > 0 ? '+' : '−') + Math.abs(m) + ' ' + t('min') + ' ' + (m > 0 ? t('late') : t('early'));
}

function lum(hex) {
  const n = parseInt(hex, 16); const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); };
  return .2126 * f((n >> 16) & 255) + .7152 * f((n >> 8) & 255) + .0722 * f(n & 255);
}
const isHex = c => /^[0-9a-fA-F]{6}$/.test(c || '');
function contrast(a, b) { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); }

/** Resolve badge colours for a line {color,text_color,mode}. */
function colors(o) {
  let bg = isHex(o.color) ? o.color : null;
  if (!bg || lum(bg) > .8) bg = MODE_COLOR[o.mode] ? MODE_COLOR[o.mode].slice(1) : '2d6cdf';
  const fg = isHex(o.text_color) && contrast(bg, o.text_color) >= 3.5 ? o.text_color : (lum(bg) > .45 ? '111111' : 'ffffff');
  return { bg: '#' + bg, fg: '#' + fg };
}
function badge(o) {
  const c = colors(o);
  const l = o.line || '';
  const inner = l.length > 9 ? ic(o.mode in ICONS ? o.mode : 'bus') : esc(l);
  return `<span class="lb" style="background:${c.bg};color:${c.fg}">${inner}</span>`;
}

// ───────────────────────────────────────────────────────────── i18n
function applyI18n() {
  document.documentElement.lang = S.lang;
  $$('[data-i18n]').forEach(el => {
    const badgeEl = $('.badge', el);
    el.firstChild && el.firstChild.nodeType === 3 ? (el.firstChild.nodeValue = t(el.dataset.i18n) + ' ') : (el.textContent = t(el.dataset.i18n));
    if (badgeEl && !el.contains(badgeEl)) el.appendChild(badgeEl);
  });
  $$('[data-i18n-ph]').forEach(el => el.placeholder = t(el.dataset.i18nPh));
  $$('[data-i18n-title]').forEach(el => { el.title = t(el.dataset.i18nTitle); el.setAttribute('aria-label', el.title); });
}

// ───────────────────────────────────────────────────────────── map
const map = L.map('map', { zoomControl: true, renderer: L.canvas({ tolerance: 10 }), tap: true }).setView([43.05, -2.55], 9);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · Data: <a href="https://opendata.euskadi.eus/">Open Data Euskadi</a>',
}).addTo(map);
const vehLayer = L.layerGroup().addTo(map);
const stnLayer = L.layerGroup().addTo(map);
const routeLayer = L.layerGroup().addTo(map);
const meLayer = L.layerGroup().addTo(map);
const selLayer = L.layerGroup().addTo(map);
const selVehLayer = L.layerGroup().addTo(map);
const markers = new Map();   // vehicle id -> {m, v, key}
map.on('zoomstart', () => $('#map').classList.add('noanim'));
map.on('zoomend', () => setTimeout(() => $('#map').classList.remove('noanim'), 50));
function zoomClass() { const z = map.getZoom(); const m = $('#map'); m.classList.toggle('tiny', z <= 10); m.classList.toggle('compact', z > 10 && z <= 12); }
map.on('zoomend', zoomClass); zoomClass();

function toast(msg, ms = 2500) {
  const el = $('#map-toast'); el.textContent = msg; el.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => el.hidden = true, ms);
}
const isMobile = () => window.innerWidth <= 800;
/** Pan so that a point is visible next to the side panel / above the bottom sheet. */
function showPoint(lat, lon, zoom) {
  const pad = isMobile() ? { paddingBottomRight: [0, window.innerHeight * .5] } : {};
  if (zoom && map.getZoom() < zoom) map.flyTo([lat, lon], zoom, { duration: .5 });
  else map.panInside([lat, lon], Object.assign({ padding: [60, 60] }, pad));
}

// ───────────────────────────────────────────────────────────── vehicles
function hasScope() { const a = S.filters.agencies; return !!S.filters.line || (a && a.size > 0 && a.size <= 3); }
function busesHidden() { return map.getZoom() < BUS_MIN_ZOOM && !hasScope(); }
function vehicleVisible(v) {
  const f = S.filters;
  if (!f.modes.has(v.mode)) return false;
  if (f.agencies && !f.agencies.has(v.agency)) return false;
  if (f.line && !(v.agency === f.line.agency && v.route_id === f.line.route_id)) return false;
  if (v.est && !f.est) return false;
  if (v.mode === 'bus' && busesHidden()) return false;
  const fo = S.focus;
  if (fo && S.selVeh !== v.id) {
    if (fo.trip_id) return v.agency === fo.agency && v.trip_id === fo.trip_id;
    if (fo.route_id) return v.agency === fo.agency && v.route_id === fo.route_id;
  }
  return true;
}
function vehicleIcon(v) {
  const c = colors(v);
  const txt = v.mode === 'metro' && (v.line || '').length > 5 ? 'M' : (v.line || '');
  const size = txt.length > 4 ? 9 : txt.length > 3 ? 10 : 12;
  const late = v.delay != null && v.delay >= 300;
  const arrow = v.bearing != null ? `<span class="arrow" style="transform:rotate(${Math.round(v.bearing)}deg);--ac:${c.bg}"></span>` : '';
  const html = `<div class="v${v.est ? ' est' : ''}${late ? ' late' : ''}${v.mode === 'train' || v.mode === 'metro' || v.mode === 'tram' ? ' sq' : ''}" style="background:${c.bg};color:${c.fg};font-size:${size}px">${arrow}${esc(txt)}</div>`;
  return L.divIcon({ className: 'veh', html, iconSize: [0, 0] });
}
function vehKey(v) { return [v.line, v.color, v.mode, v.est, v.delay != null && v.delay >= 300, v.bearing != null ? Math.round(v.bearing / 5) : '-'].join('|'); }

function drawVehicles() {
  const seen = new Set();
  for (const v of S.vehicles) {
    if (!vehicleVisible(v)) continue;
    seen.add(v.id);
    let e = markers.get(v.id);
    if (!e) {
      const m = L.marker([v.lat, v.lon], { icon: vehicleIcon(v), riseOnHover: true, keyboard: false });
      m.on('click', () => openVehicle(v.id));
      m.addTo(vehLayer);
      e = { m, v, key: vehKey(v) };
      markers.set(v.id, e);
    } else {
      e.v = v;
      e.m.setLatLng([v.lat, v.lon]);
      const k = vehKey(v);
      if (k !== e.key) { e.m.setIcon(vehicleIcon(v)); e.key = k; }
    }
    e.m.setZIndexOffset(v.id === S.selVeh ? 2000 : 0);
  }
  for (const [id, e] of markers) if (!seen.has(id)) { vehLayer.removeLayer(e.m); markers.delete(id); }
  selVehLayer.clearLayers();
  const sel = S.selVeh && markers.get(S.selVeh);
  if (sel) L.circleMarker(sel.m.getLatLng(), { radius: 22, color: '#0b5cab', weight: 3, fillColor: '#4a9df0', fillOpacity: .15, interactive: false }).addTo(selVehLayer);
  const el = $('#veh-count'); if (el) el.textContent = seen.size;
}

// ───────────────────────────────────────────────────────────── vehicle in the sidebar
function findVehicle(view) {
  if (view.vid) return S.vehicles.find(v => v.id === view.vid);
  return S.vehicles.find(v => v.agency === view.agency && v.trip_id === view.trip);
}
function vehCardInner(v) {
  const stat = v.status === 1 ? t('at_stop') : v.status === 0 ? t('incoming') : t('next_stop');
  const late = v.delay != null && v.delay >= 300;
  return `<div class="row"><span class="mi" style="color:${colors(v).bg}">${ic(v.mode in ICONS ? v.mode : 'bus', 'lg')}</span>
      <div class="grow"><b>${t('vehicle')}${v.label ? ' ' + esc(v.label) : ''}</b> <span class="muted small">${esc(v.agency_name)}</span></div>
      ${v.delay != null ? `<span class="tag ${late ? 'late' : v.delay < 60 ? 'live' : ''}"><b>${esc(fmtDelay(v.delay))}</b></span>` : ''}</div>
    ${v.stop ? `<div class="kv"><span class="muted">${stat}</span><b>${esc(v.stop)}</b></div>` : ''}
    ${v.speed != null ? `<div class="kv"><span class="muted">${t('speed')}</span><b>${v.speed} km/h</b></div>` : ''}
    ${v.ts ? `<div class="muted small" style="margin-top:4px">${updatedAgo(v.ts)}</div>` : ''}
    <div class="muted small" style="margin-top:4px">${v.est ? t('position_est') : t('position_gps')}</div>`;
}
function vehCard(view) {
  const v = findVehicle(view);
  return `<div class="card" id="veh-card"${v ? '' : ' hidden'}>${v ? vehCardInner(v) : ''}</div>`;
}
function refreshVehCard() {
  const el = $('#veh-card'); if (!el) return;
  const v = findVehicle(S.view);
  el.hidden = !v; if (v) el.innerHTML = vehCardInner(v);
}
function openVehicle(id) {
  const e = markers.get(id); if (!e) return;
  const v = e.v;
  S.selVeh = id;
  showPoint(v.lat, v.lon);
  if (v.trip_id) go({ name: 'trip', agency: v.agency, trip: v.trip_id, date: v.date || '', vid: id, data: null }, S.tab === 'lines' ? 'lines' : 'stops');
  else go({ name: 'vehicle', vid: id }, S.tab === 'lines' ? 'lines' : 'stops');
}
function renderVehicle(body) {
  const v = findVehicle(S.view);
  if (!v) { body.innerHTML = `<div class="row" style="margin-bottom:8px"><button class="btn small" data-act="back">${ic('back')}${t('back')}</button></div><div class="empty">${t('no_results')}</div>`; return; }
  body.innerHTML = `<div class="row" style="margin-bottom:8px"><button class="btn small" data-act="back">${ic('back')}${t('back')}</button></div>
    <div class="row" style="margin-bottom:8px">${badge(v)}<div class="grow"><div style="font-size:18px;font-weight:700">${esc(v.headsign || v.line)}</div><div class="muted small">${esc(v.agency_name)}</div></div></div>
    ${vehCard(S.view)}${vehActions(v)}`;
}
function vehActions(v) {
  return `<div class="row wrap" style="margin:8px 0">
    ${v.route_id ? `<button class="btn small" data-act="route" data-agency="${esc(v.agency)}" data-route="${esc(v.route_id)}">${ic('route')}${t('route_on_map')}</button>` : ''}
    ${v.route_id ? `<button class="btn small" data-act="only-line" data-agency="${esc(v.agency)}" data-route="${esc(v.route_id)}" data-line="${esc(v.line)}">${t('only_line')}</button>` : ''}</div>`;
}

let vehBusy = false;
async function pollVehicles() {
  if (vehBusy || document.hidden) return;
  vehBusy = true;
  try {
    const d = await api('vehicles');
    S.skew = d.time - Date.now() / 1000;
    S.vehicles = d.vehicles; S.feeds = d.feeds;
    drawVehicles();
    refreshVehCard();
    if (S.view.name === 'vehicle') renderVehicle($('#panel-body'));
    if (S.tab === 'live') renderLive(true);
  } catch (e) { console.warn(e); } finally { vehBusy = false; }
}

// ───────────────────────────────────────────────────────────── quick filter overlay (modes + active filters)
function renderMapFilter() {
  const f = S.filters;
  let h = `<div class="chips">` + MODES.filter(m => m !== 'ferry').map(m =>
    `<button class="chip mode${f.modes.has(m) ? ' on' : ''}" data-act="mode" data-mode="${m}" title="${modeLabel(m)}" aria-label="${modeLabel(m)}" aria-pressed="${f.modes.has(m)}">${ic(m)}</button>`).join('') + '</div>';
  const act = [];
  if (f.line) act.push(`<button class="chip on" data-act="clear-line" title="${t('clear_filter')}">${esc(f.line.line)} · ${esc(agName(f.line.agency))}${ic('close', 'xs')}</button>`);
  if (f.agencies && f.agencies.size && f.agencies.size <= 3) f.agencies.forEach(a => act.push(`<button class="chip on" data-act="clear-agency" data-id="${esc(a)}" title="${t('clear_filter')}">${esc(agName(a))}${ic('close', 'xs')}</button>`));
  if (act.length) h += `<div class="chips">${act.join('')}</div>`;
  if (busesHidden() && f.modes.has('bus')) h += `<div class="small muted">${t('zoom_buses')}</div>`;
  $('#mapfilter').innerHTML = h;
}
map.on('zoomend', () => { drawVehicles(); renderMapFilter(); });
L.DomEvent.disableClickPropagation($('#mapfilter'));
function filtersChanged() { saveFilters(); drawVehicles(); renderMapFilter(); loadStations(); if (S.view.name === 'alerts') drawAlerts(); if (S.tab === 'live') renderLive(); }

// ───────────────────────────────────────────────────────────── stations layer
let stnReq = 0;
async function loadStations() {
  stnLayer.clearLayers();
  if (!S.filters.showStops) return;
  const z = map.getZoom(); if (z < 11) return;
  const b = map.getBounds(); const id = ++stnReq;
  try {
    const d = await api('stations', { s: b.getSouth(), w: b.getWest(), n: b.getNorth(), e: b.getEast(), rail: z < STOP_MIN_ZOOM ? 1 : 0 });
    if (id !== stnReq) return;
    stnLayer.clearLayers();
    const f = S.filters;
    for (const s of d.stations) {
      const ms = stationModes(s);
      if (!ms.some(m => f.modes.has(m))) continue;
      if (f.agencies && !f.agencies.has(s.agency)) continue;
      const railMode = ms.find(x => x !== 'bus');
      const mk = L.circleMarker([s.lat, s.lon], {
        radius: railMode ? (z >= 14 ? 8 : 6) : (z >= 16 ? 6.5 : 4.5), bubblingMouseEvents: false, weight: 1.5, color: '#fff',
        fillColor: MODE_COLOR[railMode || ms[0]] || '#2d6cdf', fillOpacity: 1,
      });
      mk.bindTooltip(esc(s.name), { direction: 'top', offset: [0, -4] });
      mk.on('click', () => openStation(s.agency, s.station_id));
      mk.addTo(stnLayer);
    }
  } catch (e) { console.warn(e); }
}
let stnTimer;
map.on('moveend', () => { clearTimeout(stnTimer); stnTimer = setTimeout(loadStations, 250); });

// ───────────────────────────────────────────────────────────── navigation
function expandSheet() {
  const p = $('#panel'); if (isMobile() && p.classList.contains('collapsed')) p.classList.remove('collapsed');
}
function resetOverlays() { clearRouteLayer(); selLayer.clearLayers(); S.selVeh = null; setFocus(null); }
function setTab(tab) {
  S.tab = tab; S.hist = []; S.view = { name: tab === 'stops' ? 'home' : tab === 'lines' ? 'lines' : tab };
  resetOverlays();
  render();
}
/** Push the current view on the history stack and switch to `view` (inside `tab`). */
function go(view, tab) {
  S.hist.push({ view: S.view, tab: S.tab });
  S.view = view; S.tab = tab || S.tab;
  expandSheet(); render();
}
function back() {
  const h = S.hist.pop();
  if (!h) { setTab(S.tab === 'lines' ? 'lines' : 'stops'); return; }
  S.view = h.view; S.tab = h.tab;
  resetOverlays();
  if (S.view.name === 'station' || S.view.name === 'trip') S.view.data = null;
  if (S.view.vid) S.selVeh = S.view.vid;
  render();
}
function setFocus(f) { S.focus = f; drawVehicles(); }
function clearRouteLayer() { routeLayer.clearLayers(); }

function render() {
  $$('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === S.tab));
  const body = $('#panel-body');
  const v = S.view.name;
  if (v === 'home') renderHome(body);
  else if (v === 'station') renderStation(body);
  else if (v === 'trip') renderTrip(body);
  else if (v === 'vehicle') renderVehicle(body);
  else if (v === 'live') renderLive();
  else if (v === 'lines') renderLines(body);
  else if (v === 'route') renderRoute(body);
  else if (v === 'alerts') renderAlerts(body);
  else if (v === 'info') renderInfo(body);
  setHash();
}
function setHash() {
  const v = S.view;
  let h = '';
  if (v.name === 'station') h = '#s=' + encodeURIComponent(v.agency + '|' + v.id);
  else if (v.name === 'trip') h = '#t=' + encodeURIComponent(v.agency + '|' + v.trip);
  history.replaceState(null, '', h || location.pathname);
}
const backBtn = () => `<button class="btn small" data-act="back">${ic('back')}${t('back')}</button>`;
const refreshRow = txt => `<div class="row muted small" style="margin-top:8px"><span>${txt}</span><div class="grow"></div><button class="btn small" data-act="reload">${ic('refresh')}${t('refresh')}</button></div>`;

// ───────────────────────────────────────────────────────────── home (favourites / nearby)
function stationRow(s, extra = '') {
  return `<div class="list-item" data-act="station" data-agency="${esc(s.agency)}" data-id="${esc(s.station_id)}" data-lat="${s.lat}" data-lon="${s.lon}">
    <span class="mode-ic">${modeIcons(s.modes)}</span>
    <div class="grow"><div class="ellipsis"><b>${esc(s.name)}</b></div><div class="muted small ellipsis">${esc(s.agency_name || agName(s.agency))}${extra}</div></div>
    <span class="muted">${ic('chev')}</span></div>`;
}
function renderHome(body) {
  let h = '';
  const imp = Object.values(S.agencies).filter(a => !a.ready).length;
  if (imp) h += `<div class="notice small">${t('importing')} (${imp})</div>`;
  h += `<div class="row" style="margin-bottom:10px"><button class="btn primary" data-act="locate">${ic('target')}${t('nearby')}</button></div>`;
  if (S.nearby) {
    h += `<h2>${t('nearby_title')}</h2>`;
    h += S.nearby.length ? S.nearby.map(s => stationRow(s, ` · ${s.dist} m`)).join('') : `<div class="empty">${t('no_nearby')}</div>`;
  }
  h += `<h2>${t('favorites')}</h2>`;
  if (!S.favs.length) h += `<div class="empty">${t('no_favorites')}</div>`;
  else h += S.favs.map((f, i) => `<div class="card fav" data-act="station" data-agency="${esc(f.agency)}" data-id="${esc(f.station_id)}" style="cursor:pointer">
      <div class="row"><span class="mode-ic">${modeIcons(f.modes)}</span><div class="grow ellipsis"><b>${esc(f.name)}</b> <span class="muted small">${esc(agName(f.agency))}</span></div>
      <button class="star" data-act="unfav" data-i="${i}" title="${t('remove_fav')}" aria-label="${t('remove_fav')}">${ic('star')}</button></div>
      <div class="fav-next muted small" id="fav-${i}">…</div></div>`).join('');
  body.innerHTML = h;
  loadFavNext();
}
async function loadFavNext() {
  await Promise.all(S.favs.map(async (f, i) => {
    try {
      const d = await api('departures', { agency: f.agency, station: f.station_id, limit: 3 });
      const el = $('#fav-' + i); if (!el || S.view.name !== 'home') return;
      el.innerHTML = d.items && d.items.length ? d.items.map(it => {
        const min = Math.round((it.expected - nowTs()) / 60);
        return `<div class="row" style="margin-top:4px">${badge(it)}<span class="grow ellipsis">${esc(it.headsign)}</span><b style="color:var(--text)">${min < 1 ? t('now') : min < 60 ? min + ' ' + t('min') : clock(it.expected)}</b>${it.rt ? '<span class="tag live"><span class="d"></span></span>' : ''}</div>`;
      }).join('') : t('no_deps');
    } catch (e) { /* ignore */ }
  }));
}

// ───────────────────────────────────────────────────────────── station view
function openStation(agency, id) {
  const cur = S.view;
  if (cur.name === 'station' && cur.agency === agency && cur.id === id) return;
  resetOverlays();
  const view = { name: 'station', agency, id, data: null };
  if (cur.name === 'station') { S.view = view; S.tab = S.tab === 'lines' ? 'lines' : 'stops'; expandSheet(); render(); }
  else go(view, S.tab === 'lines' ? 'lines' : 'stops');
}
let depReq = 0;
async function renderStation(body) {
  const v = S.view;
  const my = ++depReq;
  if (!v.data) body.innerHTML = `<div class="empty">${t('loading')}</div>`;
  try {
    const d = await api('departures', { agency: v.agency, station: v.id, kind: 'dep', limit: 20 });
    if (my !== depReq || S.view !== v) return;
    if (d.error) { body.innerHTML = `<div class="empty">${esc(d.error)}</div>`; return; }
    v.data = d; S.skew = d.time - Date.now() / 1000;
    drawStationHeader(body);
    const st = d.station;
    selLayer.clearLayers();
    L.circleMarker([st.lat, st.lon], { radius: 13, color: '#0b5cab', weight: 3, fillOpacity: .1, interactive: false }).addTo(selLayer);
    if (v.fresh !== true) { v.fresh = true; if (isMobile()) { map.setView([st.lat, st.lon], Math.max(map.getZoom(), 15)); showPoint(st.lat, st.lon); } else map.flyTo([st.lat, st.lon], Math.max(map.getZoom(), 15), { duration: .6 }); }
  } catch (e) {
    if (!v.data) body.innerHTML = `<div class="empty">${t('error')}</div>`;
  }
}
function drawStationHeader(body) {
  const d = S.view.data; const st = d.station;
  const fav = isFav(st.agency, st.station_id);
  let h = `<div class="row" style="margin-bottom:8px">${backBtn()}<div class="grow"></div>
    <button class="btn small" data-act="focus-stn">${ic('target')}${t('on_map')}</button>
    <button class="star" data-act="fav" title="${fav ? t('remove_fav') : t('add_fav')}" aria-label="${fav ? t('remove_fav') : t('add_fav')}">${ic(fav ? 'star' : 'starO')}</button></div>
    <div class="row" style="margin-bottom:8px"><span class="mode-ic lg">${modeIcons(st.modes)}</span>
      <div class="grow"><div style="font-size:19px;font-weight:700">${esc(st.name)}</div><div class="muted small">${esc(st.agency_name)}</div></div></div>`;
  h += rtNotice(d.rt_status, d.items);
  for (const a of d.alerts || []) h += alertCard(a, true);
  h += `<div id="dep-list">${depList(d)}</div>`;
  h += refreshRow(`${t('updated_lbl')} ${clockS(d.time)}`);
  const keep = body.scrollTop;
  body.innerHTML = h; body.scrollTop = keep;
}
function rtNotice(status, items) {
  const anyRt = (items || []).some(i => i.rt);
  if (status === 'live' && anyRt) return `<div class="notice ok small"><span class="tag live"><span class="d"></span>${t('rt_live')}</span></div>`;
  if (status === 'live') return '';
  const key = { none: 'rt_none', empty: 'rt_empty', stale: 'rt_stale', error: 'rt_error', unknown: 'rt_empty' }[status] || 'rt_none';
  return `<div class="notice small">${t(key)}</div>`;
}
function depList(d) {
  if (!d.items.length) return `<div class="empty">${t('no_deps')}</div>`;
  const now = nowTs();
  return d.items.map(it => {
    const mins = Math.round((it.expected - now) / 60);
    const big = mins < 1 ? t('now') : mins < 60 ? mins + ' ' + t('min') : clock(it.expected);
    const late = it.delay >= 300;
    let tag;
    if (it.cancelled) tag = `<span class="tag late">${ic('close', 'xs')}${t('cancelled')}</span>`;
    else if (it.rt === 'rt') tag = `<span class="tag live"><span class="d"></span>${t('live')}${Math.abs(it.delay) >= 60 ? ' · <span class="' + (late ? 'late' : '') + '">' + esc(fmtDelay(it.delay)) + '</span>' : ''}</span>`;
    else if (it.rt === 'est') tag = `<span class="tag est"><span class="d"></span>${t('estimated')}${Math.abs(it.delay) >= 60 ? ' · ' + esc(fmtDelay(it.delay)) : ''}</span>`;
    else tag = `<span class="tag"><span class="d"></span>${t('scheduled')}</span>`;
    const second = mins < 60 && mins >= 1 ? `<div class="muted small">${clock(it.expected)}</div>` : (Math.abs(it.delay) >= 60 ? `<div class="muted small">${t('sched_short')} ${clock(it.sched)}</div>` : '');
    return `<div class="dep${it.cancelled ? ' cancelled' : ''}" data-act="trip" data-agency="${esc(S.view.agency)}" data-trip="${esc(it.trip_id)}" data-date="${esc(it.date)}">
      ${badge(it)}<div class="grow"><div class="dest ellipsis">${esc(it.headsign || it.line)}</div><div>${tag}</div></div>
      <div class="when"><div class="big${mins < 3 && !it.cancelled ? ' soon' : ''}">${big}</div>${second}</div></div>`;
  }).join('');
}

// ───────────────────────────────────────────────────────────── alerts
function alertText(o) {
  if (!o) return '';
  return o[S.lang] || o['es'] || o['es-ES'] || o['eu'] || o['en'] || Object.values(o).find(Boolean) || '';
}
function alertVisible(a) {
  const f = S.filters;
  if (f.agencies && !f.agencies.has(a.agency)) return false;
  if (a.modes && a.modes.length && !a.modes.some(m => f.modes.has(m))) return false;
  if (f.line) {
    if (a.agency !== f.line.agency) return false;
    if (a.route_ids && a.route_ids.length && !a.route_ids.includes(f.line.route_id)) return false;
  }
  return true;
}
function alertCard(a, compact) {
  const url = alertText(a.url), head = alertText(a.header), desc = alertText(a.description);
  return `<div class="alert-card small">
    <div class="alert-top">${ic('warn')}<b>${esc(a.agency_name)}</b>${(a.lines || []).length ? `<span class="muted">· ${esc(a.lines.slice(0, 6).join(', '))}${a.lines.length > 6 ? '…' : ''}</span>` : ''}</div>
    ${head ? `<div>${esc(head)}</div>` : ''}
    ${desc ? `<div class="muted" style="margin-top:3px">${esc(desc).slice(0, compact ? 240 : 600)}</div>` : ''}
    ${a.end ? `<div class="muted">${t('until')} ${new Date(a.end * 1000).toLocaleString()}</div>` : ''}
    ${url ? `<div><a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${t('more')}${ic('link', 'xs')}</a></div>` : ''}</div>`;
}
function updateAlertBadge() {
  const c = $('#alert-count'); if (!c) return;
  const n = S.alerts.filter(alertVisible).length;
  c.hidden = !n; c.textContent = n;
}
async function loadAlerts() {
  try { S.alerts = (await api('alerts')).alerts; } catch (e) { return; }
  updateAlertBadge();
  if (S.view.name === 'alerts') drawAlerts();
}
function renderAlerts(body) {
  body.innerHTML = `<input type="text" id="alerts-q" placeholder="${t('alerts_filter')}" style="margin-bottom:8px"><div id="alerts-list"></div>`;
  $('#alerts-q').oninput = drawAlerts; drawAlerts();
}
function drawAlerts() {
  const el = $('#alerts-list'); if (!el) return;
  const q = fold($('#alerts-q').value);
  const vis = S.alerts.filter(alertVisible);
  const rows = vis.filter(a => !q || fold(alertText(a.header) + ' ' + alertText(a.description) + ' ' + a.agency_name + ' ' + (a.lines || []).join(' ')).includes(q));
  const hidden = S.alerts.length - vis.length;
  el.innerHTML = (hidden > 0 ? `<div class="small muted" style="margin-bottom:8px">${t('alerts_hidden').replace('{n}', hidden)}</div>` : '') +
    (rows.length ? rows.slice(0, 200).map(a => alertCard(a, false)).join('') : `<div class="empty">${t('no_alerts')}</div>`);
}

// ───────────────────────────────────────────────────────────── trip view
function openTrip(agency, trip, date) {
  go({ name: 'trip', agency, trip, date, data: null }, S.tab === 'lines' ? 'lines' : 'stops');
}
let tripReq = 0;
async function renderTrip(body) {
  const v = S.view; const my = ++tripReq;
  if (!v.data) body.innerHTML = `<div class="empty">${t('loading')}</div>`;
  try {
    const d = await api('trip', { agency: v.agency, trip: v.trip, date: v.date || '' });
    if (my !== tripReq || S.view !== v) return;
    if (d.error) { body.innerHTML = `<div class="empty">${esc(d.error)}</div>`; return; }
    v.data = d;
    const veh = findVehicle(v);
    if (veh && S.selVeh !== veh.id) S.selVeh = veh.id;
    const now = nowTs();
    const c = colors(d);
    const idx = d.stops.findIndex(s => s.expected >= now - 30);
    let h = `<div class="row" style="margin-bottom:8px">${backBtn()}<div class="grow"></div>
      <button class="btn small" data-act="route" data-agency="${esc(d.agency)}" data-route="${esc(d.route_id)}">${ic('route')}${t('route_on_map')}</button></div>
      <div class="row" style="margin-bottom:6px">${badge(d)}<div class="grow"><div style="font-size:18px;font-weight:700">${esc(d.headsign)}</div><div class="muted small">${esc(agName(d.agency))}</div></div></div>
      ${vehCard(v)}`;
    if (d.cancelled) h += `<div class="notice bad small">${ic('close', 'xs')}${t('cancelled')}</div>`;
    else if (!d.has_rt) h += `<div class="notice small">${t('rt_none')}</div>`;
    h += `<ul class="tl" style="--c:${c.bg}">` + d.stops.map((s, i) => {
      const dl = s.expected - s.sched;
      const cls = (i < idx || idx < 0 ? 'past' : '') + (i === idx ? ' here' : '') + (s.skipped ? ' skipped' : '');
      return `<li class="${cls}" data-act="station" data-agency="${esc(d.agency)}" data-id="${esc(s.station_id)}" data-lat="${s.lat}" data-lon="${s.lon}">
        <div class="grow nm">${esc(s.name)}</div>
        <div class="tm"><b>${clock(s.expected)}</b>${Math.abs(dl) >= 60 ? `<div class="small ${dl >= 300 ? 'tag late' : 'muted'}">${t('sched_short')} ${clock(s.sched)}</div>` : ''}
        ${s.rt === 'rt' ? '<div class="tag live small"><span class="d"></span></div>' : ''}</div></li>`;
    }).join('') + '</ul>';
    h += refreshRow(`${t('updated_lbl')} ${clockS(now)}`);
    const keep = body.scrollTop;
    body.innerHTML = h; body.scrollTop = keep;
    drawTripOnMap(d, idx, !v.fitted); v.fitted = true;
    setFocus({ agency: d.agency, trip_id: d.trip_id });
  } catch (e) { if (!v.data) body.innerHTML = `<div class="empty">${t('error')}</div>`; }
}
function drawTripOnMap(d, idx, fit) {
  clearRouteLayer(); selLayer.clearLayers();
  const c = colors(d).bg;
  const pts = d.shape && d.shape.length ? d.shape : d.stops.filter(s => s.lat).map(s => [s.lat, s.lon]);
  const pl = L.polyline(pts, { color: c, weight: 5, opacity: .8 }).addTo(routeLayer);
  d.stops.forEach((s, i) => {
    if (!s.lat) return;
    L.circleMarker([s.lat, s.lon], { radius: i === idx ? 8 : 5, weight: 2, color: '#fff', fillColor: i === idx ? '#111' : c, fillOpacity: 1, bubblingMouseEvents: false })
      .bindTooltip(`${esc(s.name)} · ${clock(s.expected)}`).on('click', () => openStation(d.agency, s.station_id)).addTo(routeLayer);
  });
  if (fit) map.fitBounds(pl.getBounds(), isMobile() ? { paddingBottomRight: [20, window.innerHeight * .5], padding: [20, 20] } : { padding: [30, 30] });
}

// ───────────────────────────────────────────────────────────── live map tab (filters)
function renderLive(soft) {
  const body = $('#panel-body');
  if (soft && $('#live-root')) { updateLiveCounts(); return; }
  const f = S.filters;
  body.innerHTML = `<div id="live-root"><div class="card"><b id="veh-count">0</b> ${t('vehicles_shown')}</div>
    <h2>${t('filter_modes')}</h2><div class="chips">${MODES.filter(m => m !== 'ferry').map(m => `<button class="chip mode wide${f.modes.has(m) ? ' on' : ''}" data-act="mode" data-mode="${m}">${ic(m)}${modeLabel(m)}</button>`).join('')}</div>
    ${f.line ? `<h2>${t('filter_line')}</h2><div class="chips"><button class="chip on" data-act="clear-line">${esc(f.line.line)} · ${esc(agName(f.line.agency))}${ic('close', 'xs')}</button></div>` : ''}
    <h2>${t('filter_agencies')}</h2>
    <div class="row small" style="margin-bottom:6px"><button class="btn small" data-act="ag-all">${t('all')}</button><button class="btn small" data-act="ag-none">${t('none')}</button></div>
    <div class="checks" id="ag-checks"></div>
    <h2></h2><div class="checks">
      <label><input type="checkbox" data-act="opt" data-opt="showStops" ${f.showStops ? 'checked' : ''}> ${t('show_stops')}</label>
      <label><input type="checkbox" data-act="opt" data-opt="est" ${f.est ? 'checked' : ''}> ${t('show_est')} <span class="muted small">(Euskotren…)</span></label></div></div>`;
  updateLiveCounts();
}
function updateLiveCounts() {
  const el = $('#ag-checks'); if (!el) return;
  const counts = {};
  S.vehicles.forEach(v => counts[v.agency] = (counts[v.agency] || 0) + 1);
  const list = Object.values(S.agencies).filter(a => a.ready && (a.rt.vehicles || a.rt.trips));
  const withData = list.filter(a => counts[a.id]).sort((a, b) => a.name.localeCompare(b.name));
  const without = list.filter(a => !counts[a.id]).sort((a, b) => a.name.localeCompare(b.name));
  const row = (a, n) => `<label><input type="checkbox" data-act="ag" data-id="${esc(a.id)}" ${!S.filters.agencies || S.filters.agencies.has(a.id) ? 'checked' : ''}>
    <span class="dotc ${n ? 'live' : ''}"></span><span class="grow">${esc(a.name)}</span><span class="muted small">${n ? n + ' ' + t('live_vehicles') : t('no_rt')}</span></label>`;
  el.innerHTML = withData.map(a => row(a, counts[a.id])).join('') + without.map(a => row(a, 0)).join('');
  const vc = $('#veh-count'); if (vc) vc.textContent = markers.size;
}

// ───────────────────────────────────────────────────────────── lines tab
async function renderLines(body) {
  const ags = Object.values(S.agencies).filter(a => a.ready).sort((a, b) => a.name.localeCompare(b.name));
  if (!S.linesAgency || !S.agencies[S.linesAgency]) S.linesAgency = (ags.find(a => a.id === 'euskotren') || ags[0] || {}).id || '';
  body.innerHTML = `<select class="field" id="lines-ag" aria-label="${t('pick_agency')}">${ags.map(a => `<option value="${esc(a.id)}"${a.id === S.linesAgency ? ' selected' : ''}>${esc(a.name)}${a.rt.vehicles || a.rt.trips ? ' (live)' : ''}</option>`).join('')}</select>
    <input type="text" id="lines-q" placeholder="${t('filter_lines')}" style="margin:8px 0"><div id="lines-list"><div class="empty">${t('loading')}</div></div>`;
  $('#lines-ag').onchange = e => { S.linesAgency = e.target.value; localStorage.setItem('linesAgency', S.linesAgency); renderLines(body); };
  $('#lines-q').oninput = drawLinesList;
  if (!S.linesAgency) return;
  if (!S.routesCache[S.linesAgency]) {
    try { S.routesCache[S.linesAgency] = (await api('routes', { agency: S.linesAgency })).routes; } catch (e) { $('#lines-list').innerHTML = `<div class="empty">${t('error')}</div>`; return; }
  }
  drawLinesList();
}
function drawLinesList() {
  const el = $('#lines-list'); if (!el) return;
  const q = fold($('#lines-q').value);
  const rs = (S.routesCache[S.linesAgency] || []).filter(r => !q || fold(r.line + ' ' + r.long).includes(q)).slice(0, 300);
  el.innerHTML = rs.length ? rs.map(r => `<div class="list-item" data-act="route" data-agency="${esc(S.linesAgency)}" data-route="${esc(r.route_id)}">${badge(r)}<div class="grow ellipsis">${esc(r.long || '')}</div><span class="muted">${ic('chev')}</span></div>`).join('') : `<div class="empty">${t('no_results')}</div>`;
}
function openRoute(agency, route) {
  go({ name: 'route', agency, route, data: null }, 'lines');
}
async function renderRoute(body) {
  const v = S.view;
  body.innerHTML = `<div class="empty">${t('loading')}</div>`;
  try {
    const d = await api('route', { agency: v.agency, route: v.route });
    if (S.view !== v) return;
    v.data = d;
    const c = colors(d);
    const isOnly = S.filters.line && S.filters.line.agency === v.agency && S.filters.line.route_id === v.route;
    let h = `<div class="row" style="margin-bottom:8px">${backBtn()}<div class="grow"></div>
      <button class="btn small${isOnly ? ' primary' : ''}" data-act="${isOnly ? 'clear-line' : 'only-line'}" data-agency="${esc(v.agency)}" data-route="${esc(v.route)}" data-line="${esc(d.line)}">${isOnly ? t('clear_filter') : t('only_line')}</button></div>
      <div class="row" style="margin-bottom:8px">${badge(d)}<div class="grow"><div style="font-size:18px;font-weight:700">${esc(d.long || d.line)}</div><div class="muted small">${esc(agName(v.agency))}</div></div></div>`;
    const live = S.vehicles.filter(x => x.agency === v.agency && x.route_id === v.route).length;
    h += `<div class="notice ${live ? 'ok' : ''} small">${live ? `<span class="tag live"><span class="d"></span>${live} ${t('live_vehicles')}</span>` : t('no_rt')}</div>`;
    for (const sh of d.shapes) {
      h += `<h2>${t('departs_from')} ${esc(sh.headsign || '')}</h2><ul class="tl" style="--c:${c.bg}">` +
        sh.stops.map(s => `<li data-act="station" data-agency="${esc(v.agency)}" data-id="${esc(s.station_id)}" data-lat="${s.lat}" data-lon="${s.lon}"><span class="nm">${esc(s.name)}</span></li>`).join('') + '</ul>';
    }
    body.innerHTML = h;
    clearRouteLayer(); selLayer.clearLayers();
    let bounds = L.latLngBounds([]);
    d.shapes.forEach((sh, i) => {
      const pts = sh.pts && sh.pts.length ? sh.pts : sh.stops.filter(s => s.lat).map(s => [s.lat, s.lon]);
      if (!pts.length) return;
      const pl = L.polyline(pts, { color: c.bg, weight: 5, opacity: i ? .55 : .85, dashArray: i ? '8 8' : null }).addTo(routeLayer);
      bounds.extend(pl.getBounds());
      sh.stops.forEach(s => s.lat && L.circleMarker([s.lat, s.lon], { radius: 5, weight: 2, color: '#fff', fillColor: c.bg, fillOpacity: 1, bubblingMouseEvents: false })
        .bindTooltip(esc(s.name)).on('click', () => openStation(v.agency, s.station_id)).addTo(routeLayer));
    });
    if (bounds.isValid()) map.fitBounds(bounds, isMobile() ? { paddingBottomRight: [20, window.innerHeight * .5], padding: [20, 20] } : { padding: [30, 30] });
    setFocus({ agency: v.agency, route_id: v.route });
  } catch (e) { body.innerHTML = `<div class="empty">${t('error')}</div>`; }
}

// ───────────────────────────────────────────────────────────── sources
async function renderInfo(body) {
  body.innerHTML = `<p class="small muted">${t('src_intro')}</p><div id="info-t"><div class="empty">${t('loading')}</div></div>`;
  try {
    const d = await api('agencies', { probe: 1 });
    S.agencies = Object.fromEntries(d.agencies.map(a => [a.id, a]));
    const st = s => s ? `<span class="st ${s.status}">${t('st_' + s.status)}${s.n ? ' ' + s.n : ''}</span>` : '<span class="muted">—</span>';
    $('#info-t').innerHTML = `<table class="src"><tr><th>${t('src_operator')}</th><th>${t('src_veh')}</th><th>${t('src_trips')}</th><th>${t('src_alerts')}</th></tr>` +
      d.agencies.map(a => `<tr><td>${esc(a.name)}<div class="muted small">${a.ready ? (a.modes || []).map(m => modeSvg(m, 'sm')).join('') + ' ' + esc((a.gtfs_updated || '').slice(0, 16)) : (a.importing ? t('importing') : esc(a.error || ''))}</div></td>
      <td>${st(a.rt.vehicles)}</td><td>${st(a.rt.trips)}</td><td>${st(a.rt.alerts)}</td></tr>`).join('') + '</table>' +
      `<p class="small muted">${d.agencies.filter(a => a.ready).length}/${d.agencies.length} · ${new Date(d.time * 1000).toLocaleTimeString()}</p>`;
  } catch (e) { $('#info-t').innerHTML = `<div class="empty">${t('error')}</div>`; }
}

// ───────────────────────────────────────────────────────────── search (stops, lines, operators in one box)
const qEl = $('#q'), sugEl = $('#suggest');
let sugData = [], sugSel = -1, sugTimer, sugReq = 0;
function renderSuggest(d) {
  sugData = [];
  let h = '';
  const sect = (title, items, fn) => { if (!items.length) return; h += `<li class="hd">${title}</li>`; items.forEach(x => { sugData.push(x); h += fn(x, sugData.length - 1); }); };
  sect(t('search_lines'), d.routes.slice(0, 6).map(r => Object.assign({ type: 'route' }, r)),
    (r, i) => `<li data-i="${i}">${badge(r)}<div class="grow ellipsis">${esc(r.long || r.line)} <span class="muted small">${esc(r.agency_name)}</span></div></li>`);
  sect(t('search_ops'), d.operators.slice(0, 4).map(o => Object.assign({ type: 'operator' }, o)),
    (o, i) => `<li data-i="${i}"><span class="mi">${ic('bus')}</span><div class="grow ellipsis"><b>${esc(o.name)}</b></div></li>`);
  sect(t('search_stops'), d.results.map(s => Object.assign({ type: 'station' }, s)),
    (s, i) => `<li data-i="${i}"><span class="mode-ic">${modeIcons(s.modes)}</span><div class="grow ellipsis"><b>${esc(s.name)}</b> <span class="muted small">${esc(s.agency_name)}</span></div></li>`);
  sugEl.innerHTML = h || `<li class="muted pad">${t('no_results')}</li>`;
  sugSel = -1; sugEl.hidden = false;
}
qEl.addEventListener('input', () => {
  clearTimeout(sugTimer);
  const q = qEl.value.trim();
  if (q.length < 1) { sugEl.hidden = true; return; }
  sugTimer = setTimeout(async () => {
    const id = ++sugReq;
    try { const d = await api('search', { q }); if (id === sugReq) renderSuggest(d); } catch (e) { /* ignore */ }
  }, 180);
});
qEl.addEventListener('keydown', e => {
  const lis = $$('li[data-i]', sugEl);
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault(); if (!lis.length) return;
    sugSel = (sugSel + (e.key === 'ArrowDown' ? 1 : -1) + lis.length) % lis.length;
    lis.forEach((l, i) => l.classList.toggle('sel', i === sugSel));
    lis[sugSel].scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Enter') {
    const s = sugData[sugSel >= 0 ? sugSel : 0]; if (s) pickSuggestion(s);
  } else if (e.key === 'Escape') { sugEl.hidden = true; qEl.blur(); }
});
sugEl.addEventListener('mousedown', e => { const li = e.target.closest('li[data-i]'); if (li) { e.preventDefault(); pickSuggestion(sugData[+li.dataset.i]); } });
qEl.addEventListener('blur', () => setTimeout(() => sugEl.hidden = true, 150));
qEl.addEventListener('focus', () => { if (sugData.length && qEl.value.trim()) sugEl.hidden = false; });
function pickSuggestion(s) {
  sugEl.hidden = true; qEl.value = ''; qEl.blur();
  if (s.type === 'station') openStation(s.agency, s.station_id);
  else if (s.type === 'route') {
    S.filters.line = { agency: s.agency, route_id: s.route_id, line: s.line };
    filtersChanged(); openRoute(s.agency, s.route_id);
  } else if (s.type === 'operator') {
    S.filters.agencies = new Set([s.agency]); S.filters.line = null;
    filtersChanged(); toast(s.name);
  }
}

// ───────────────────────────────────────────────────────────── geolocation
function locate() {
  if (!navigator.geolocation) { toast(t('loc_denied')); return; }
  toast(t('locating'), 5000);
  navigator.geolocation.getCurrentPosition(async pos => {
    const { latitude: lat, longitude: lon } = pos.coords;
    S.me = [lat, lon];
    meLayer.clearLayers();
    L.marker(S.me, { icon: L.divIcon({ className: '', html: '<div class="me"></div>', iconSize: [0, 0] }), interactive: false }).addTo(meLayer);
    map.flyTo(S.me, 16, { duration: .8 });
    try { S.nearby = (await api('nearby', { lat, lon, radius: 600 })).results; } catch (e) { S.nearby = []; }
    setTab('stops'); expandSheet();
  }, () => toast(t('loc_denied')), { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 });
}

// ───────────────────────────────────────────────────────────── events
document.addEventListener('click', ev => {
  const el = ev.target.closest('[data-act]'); if (!el) return;
  const a = el.dataset.act, d = el.dataset;
  if (el.tagName === 'INPUT') return;
  ev.stopPropagation();
  switch (a) {
    case 'station':
      if (d.lat && S.view.name === 'trip') showPoint(+d.lat, +d.lon);
      openStation(d.agency, d.id); break;
    case 'trip': openTrip(d.agency, d.trip, d.date); break;
    case 'route': openRoute(d.agency, d.route); break;
    case 'back': back(); break;
    case 'reload': render(); break;
    case 'fav': {
      const st = S.view.data && S.view.data.station; if (!st) break;
      if (isFav(st.agency, st.station_id)) S.favs = S.favs.filter(f => !(f.agency === st.agency && f.station_id === st.station_id));
      else S.favs.push({ agency: st.agency, station_id: st.station_id, name: st.name, modes: st.modes });
      saveFavs(); drawStationHeader($('#panel-body')); break;
    }
    case 'unfav': S.favs.splice(+d.i, 1); saveFavs(); render(); break;
    case 'focus-stn': { const st = S.view.data && S.view.data.station; if (st) { map.flyTo([st.lat, st.lon], 17, { duration: .5 }); if (isMobile()) $('#panel').classList.add('collapsed'); } break; }
    case 'locate': locate(); break;
    case 'only-line': S.filters.line = { agency: d.agency, route_id: d.route, line: d.line }; filtersChanged(); if (S.view.name === 'route') render(); break;
    case 'clear-line': S.filters.line = null; filtersChanged(); if (S.view.name === 'route') render(); break;
    case 'clear-agency': S.filters.agencies.delete(d.id); if (!S.filters.agencies.size) S.filters.agencies = null; filtersChanged(); break;
    case 'mode': S.filters.modes.has(d.mode) ? S.filters.modes.delete(d.mode) : S.filters.modes.add(d.mode); filtersChanged(); break;
    case 'ag-all': S.filters.agencies = null; filtersChanged(); break;
    case 'ag-none': S.filters.agencies = new Set(); filtersChanged(); break;
  }
});
document.addEventListener('change', ev => {
  const el = ev.target; const a = el.dataset && el.dataset.act;
  if (a === 'ag') {
    if (!S.filters.agencies) S.filters.agencies = new Set(Object.keys(S.agencies));
    el.checked ? S.filters.agencies.add(el.dataset.id) : S.filters.agencies.delete(el.dataset.id);
    saveFilters(); drawVehicles(); renderMapFilter(); loadStations();
  } else if (a === 'opt') {
    S.filters[el.dataset.opt] = el.checked; saveFilters();
    if (el.dataset.opt === 'showStops') loadStations(); else drawVehicles();
  }
});
$$('#tabs button').forEach(b => b.addEventListener('click', () => { setTab(b.dataset.tab); if (b.dataset.tab === 'alerts') loadAlerts(); expandSheet(); }));
$('#btn-locate').addEventListener('click', locate);
$('#lang').value = S.lang;
$('#lang').addEventListener('change', e => { S.lang = e.target.value; localStorage.setItem('lang', S.lang); applyI18n(); renderMapFilter(); render(); });
$('#sheet-handle').addEventListener('click', () => {
  const p = $('#panel');
  if (p.classList.contains('collapsed')) { p.classList.remove('collapsed'); }
  else if (!p.classList.contains('expanded')) p.classList.add('expanded');
  else { p.classList.remove('expanded'); p.classList.add('collapsed'); }
});
map.on('click', () => { if (isMobile()) $('#panel').classList.add('collapsed'); });
document.addEventListener('visibilitychange', () => { if (!document.hidden) { pollVehicles(); refreshView(); } });

function refreshView() {
  const n = S.view.name;
  if (document.hidden) return;
  if (n === 'station' || n === 'trip') render();
  else if (n === 'home' && S.favs.length) loadFavNext();
}
setInterval(pollVehicles, POLL_VEHICLES_MS);
setInterval(refreshView, POLL_VIEW_MS);
setInterval(() => { // keep countdowns ticking between fetches
  if (S.view.name === 'station' && S.view.data && !document.hidden) { const l = $('#dep-list'); if (l) l.innerHTML = depList(S.view.data); }
}, 10000);
setInterval(loadAlerts, 120000);

// vertical mouse wheel scrolls the tab strip horizontally
$('#tabs').addEventListener('wheel', e => {
  if (e.deltaY && !e.deltaX) { e.preventDefault(); e.currentTarget.scrollLeft += e.deltaY; }
}, { passive: false });

// drag handle to resize the side panel (desktop)
(function () {
  const root = document.documentElement, handle = $('#resizer');
  const saved = +localStorage.getItem('panelW');
  if (saved >= 300) root.style.setProperty('--panel-w', saved + 'px');
  let drag = false;
  const move = e => {
    if (!drag) return;
    const x = (e.touches ? e.touches[0].clientX : e.clientX);
    const w = Math.min(Math.max(x, 300), Math.min(900, window.innerWidth - 200));
    root.style.setProperty('--panel-w', w + 'px');
    localStorage.setItem('panelW', Math.round(w));
    map.invalidateSize();
  };
  const stop = () => { drag = false; document.body.classList.remove('resizing'); map.invalidateSize(); };
  handle.addEventListener('mousedown', e => { drag = true; document.body.classList.add('resizing'); e.preventDefault(); });
  handle.addEventListener('touchstart', () => { drag = true; document.body.classList.add('resizing'); }, { passive: true });
  window.addEventListener('mousemove', move); window.addEventListener('touchmove', move, { passive: true });
  window.addEventListener('mouseup', stop); window.addEventListener('touchend', stop);
  handle.addEventListener('dblclick', () => { root.style.removeProperty('--panel-w'); localStorage.removeItem('panelW'); map.invalidateSize(); });
  handle.addEventListener('keydown', e => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    const w = $('#panel').offsetWidth + (e.key === 'ArrowRight' ? 30 : -30);
    root.style.setProperty('--panel-w', Math.min(Math.max(w, 300), 900) + 'px'); localStorage.setItem('panelW', w); map.invalidateSize();
  });
})();

// ───────────────────────────────────────────────────────────── boot
async function loadAgencies() {
  try {
    const d = await api('agencies');
    S.agencies = Object.fromEntries(d.agencies.map(a => [a.id, a]));
    if (S.view.name === 'home') renderHome($('#panel-body'));
    return d.agencies.some(a => !a.ready || a.importing);
  } catch (e) { return true; }
}
async function boot() {
  const h = decodeURIComponent((location.hash || '').slice(1));
  $('#btn-locate').innerHTML = ic('target');
  $('#brand-logo').innerHTML = ic('train');
  applyI18n();
  renderMapFilter();
  render();
  const importing = await loadAgencies();
  renderMapFilter();
  pollVehicles(); loadAlerts(); loadStations();
  if (importing) { // first run: timetables are still being imported
    const iv = setInterval(async () => { const still = await loadAgencies(); if (!still) { clearInterval(iv); loadStations(); } }, 8000);
  }
  if (h.startsWith('s=')) { const [a, id] = h.slice(2).split('|'); if (a && id) openStation(a, id); }
  else if (h.startsWith('t=')) { const [a, id] = h.slice(2).split('|'); if (a && id) openTrip(a, id, ''); }
}
boot();
