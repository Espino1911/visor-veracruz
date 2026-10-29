# Visor Geoelectoral Veracruz

Aplicación web independiente. No necesita Claude, cuentas ni servidor propio: son archivos estáticos que cualquier hosting gratuito sirve. Una vez abierta en el teléfono, se instala en la pantalla de inicio y funciona sin conexión.

Versión: 2026.10.29-1

## Contenido

| Carpeta o archivo | Qué es |
|---|---|
| `index.html` | La aplicación |
| `data/` | Cartografía (5,004 secciones), resultados de 5 elecciones (PREP) y lista nominal al 15-oct-2026 |
| `vendor/`, `fonts/`, `icons/` | Mapa, tipografías e íconos, todo local |
| `sw.js`, `manifest.webmanifest` | Instalación en el teléfono y funcionamiento sin conexión |
| `herramientas/` | Scripts de Python para regenerar `data/` con bases nuevas |

## Publicarla (elige una)

**A. GitHub Pages (gratis, recomendada).** Sube el contenido de esta carpeta a un repositorio, entra a Settings → Pages, elige la rama `main` y la carpeta raíz. La dirección queda como `https://USUARIO.github.io/REPOSITORIO/`. Con el plan gratuito el sitio es público para quien tenga el enlace.

**B. Cloudflare Pages + Cloudflare Access (gratis hasta 50 usuarios, con acceso restringido).** Crea un proyecto en Pages, sube esta carpeta y activa Access para pedir un código por correo a las cuentas autorizadas. Es la opción para uso reservado.

**C. Netlify.** Arrastra la carpeta a app.netlify.com/drop con una cuenta iniciada. Admite contraseña en planes de pago.

No funciona abriendo `index.html` directo desde el teléfono o la computadora: el navegador bloquea la carga de datos desde archivos locales. Para probarla en una computadora: `python3 -m http.server` dentro de esta carpeta y abrir `http://localhost:8000`.

## Instalarla en el teléfono

- **Android (Chrome):** abre la dirección, menú ⋮ → *Instalar aplicación*.
- **iPhone (Safari):** abre la dirección, botón Compartir → *Agregar a pantalla de inicio*.

La primera apertura descarga unos 4.5 MB (1.5 MB comprimidos por el hosting). Después abre sin internet.

## Actualizar datos

1. Regenera `data/` con los scripts de `herramientas/` (o pídeselo a Claude con las bases nuevas).
2. Cambia `VERSION` en `sw.js` (por ejemplo `2026.11.15-1`).
3. Vuelve a subir la carpeta. Los teléfonos verán el aviso *Hay una versión nueva de los datos → Actualizar*.

## Fuentes

PREP 2024 (Presidencia y Diputaciones federales, INE; Gubernatura y Diputaciones locales, OPLE Veracruz), PREP 2025 (Ayuntamientos, OPLE Veracruz), cartografía electoral del INE y lista nominal por sección del INE (Datos Abiertos DERFE, corte 15-oct-2026). Resultados preliminares, no cómputos oficiales.
