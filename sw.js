// Visor Geoelectoral Veracruz: funcionamiento sin conexión.
// Al publicar datos nuevos, cambia VERSION para que los teléfonos descarguen la actualización.
const VERSION = '2026.10.29-1';
const CACHE = 'visor-ver-' + VERSION;
const ASSETS = [
  './', 'index.html', 'manifest.webmanifest',
  'vendor/maplibre-gl.js', 'vendor/topojson-client.min.js',
  'data/geo.json', 'data/catalogo.json', 'data/resultados.json', 'data/ln2026.json',
  'fonts/plex-cond-400.woff2', 'fonts/plex-cond-500.woff2', 'fonts/plex-cond-600.woff2', 'fonts/plex-cond-700.woff2',
  'fonts/plex-mono-400.woff2', 'fonts/plex-mono-500.woff2',
  'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png'
];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS.map(u => new Request(u, {cache: 'reload'})))));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('visor-ver-') && k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('message', e => { if (e.data === 'skipWaiting') self.skipWaiting(); });
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  e.respondWith(
    caches.match(req, {ignoreSearch: true}).then(hit => hit || fetch(req).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    }).catch(() => req.mode === 'navigate' ? caches.match('index.html') : Response.error()))
  );
});
