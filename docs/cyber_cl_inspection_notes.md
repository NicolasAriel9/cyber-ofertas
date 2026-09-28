# cyber.cl inspection notes — Phase 0

**Fecha de inspección:** 2026-09-28 (7 días antes del Cyber Monday, 5-7 octubre 2026).

## robots.txt
```
User-Agent: *
Allow: /
Sitemap: https://cyber.cl/sitemap.xml
```
Sin restricciones — scraping permitido explícitamente.

## Stack técnico
- Next.js (App Router), server components con protocolo RSC interno (`?_rsc=<hash>` en las requests de navegación), no el viejo `__NEXT_DATA__`.
- Assets/imágenes de categorías y eventos servidos desde `media.app.cyber.cl` (ej. `https://media.app.cyber.cl/media/categories/tecnologia.png`), lo que sugiere un backend propio en el dominio `app.cyber.cl` (no confirmado si expone una API pública).
- Imágenes optimizadas vía `/_next/image?url=...` (proxy estándar de Next.js).

## Estructura de navegación descubierta
- Home (`/`) — landing con FAQ, boletín, y botón **"Ver Categorías"** que despliega 24 categorías (Tecnología, Hogar, Vestuario y Calzado, Multitiendas y Supermercados, Viajes y Turismo, etc.).
- Cada categoría enlaza a `https://cyber.cl/cyber/marcas/<slug>` (ej. `/cyber/marcas/tecnologia`) — esta es la ruta que en teoría lista las marcas/ofertas de esa categoría.
- Otras rutas: `/cyber/favoritos` (requiere login), `/inicia-sesion`, `/magazine`, `/confianza-digital`, `/cyber/informacion`.
- El sitio promueve activamente su propia **app móvil "CyberApp"** ("¡Descarga nuestra CyberApp aquí!") — sugiere que el catálogo completo/búsqueda vive principalmente en la app nativa, y el sitio web podría ser un subconjunto o solo redirigir a las marcas.
- Hay una función "Buscar con IA" en desarrollo ("Preparando tu asistente personal...") — no funcional aún al momento de la inspección.

## Hallazgo clave: el catálogo de marcas/ofertas NO está poblado todavía
Al visitar `/cyber/marcas/tecnologia` con un navegador real (Chrome, vía Claude in Chrome):
- La página renderiza solo copy de marketing y FAQ genérico — **ninguna marca, producto ni precio visible**.
- La request RSC interna `GET /cyber/marcas/tecnologia?_rsc=...` devolvió **503** en varios intentos, junto con varios `POST` al mismo endpoint alternando entre `200` y `503` (comportamiento inconsistente/flaky, no un bloqueo sistemático — varios trackers de terceros como Meta Pixel, TikTok Pixel, Clarity y Google Ads también devolvieron 503, probablemente bloqueados por el propio navegador/extensión, así que esa parte no es concluyente).
- La ruta `/magazine?_rsc=...` también devolvió 503; en cambio `/`, `/share`, `/cyber/favoritos`, `/confianza-digital`, `/inicia-sesion` respondieron 200 vía RSC sin problema.

**Interpretación:** no encontramos un endpoint JSON público y estable para el catálogo — los datos, cuando existen, se sirven vía el protocolo RSC interno de Next.js (no es un contrato de API versionado y confiable para un scraper). Más importante: **la sección de marcas/ofertas por categoría aparenta estar vacía o inestable a 7 días del evento**, consistente con que Cyber.cl solo puebla el catálogo real durante la ventana activa del evento (5-7 de octubre).

## Implicancia para el plan
- **No se puede terminar de diseñar el parser real hoy** — depende de ver la página con datos reales.
- Acción pendiente: repetir esta inspección **un par de días antes del 5 de octubre** (o el mismo día 5) cuando el catálogo esté poblado, para confirmar si:
  (a) aparece una llamada de red a un JSON limpio (ideal), o
  (b) los datos quedan embebidos en el HTML/RSC payload servido inicialmente (parseable sin headless browser), o
  (c) hace falta renderizar con Playwright porque todo se arma client-side tras hidratación.
- Mientras tanto, el resto del proyecto (modelos de datos, API backend, frontend, bot de Telegram, deploy) puede construirse en paralelo usando fixtures/datos de prueba, sin bloquear en este hallazgo.
