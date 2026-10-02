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

---

# Re-inspección 2026-10-01 (4 días antes del evento) — resuelto

## cyber.cl tiene una API JSON pública (no hace falta parsear RSC)
Buscando en los bundles JS del sitio aparecieron las rutas de su backend, servido en `https://app.cyber.cl/api/` (JSON plano, sin auth):

| Endpoint | Contenido |
|---|---|
| `/api/events/current/` | Evento activo: `{"id":35,"name":"Cyber Monday","slug":"cyber","start":"2026-10-05T03:00:00Z","end":"2026-10-08T03:00:00Z",...}` |
| `/api/events/cyber/brands/` | **524 marcas participantes**, cada una con `name`, `logo`, `url`, `category` |
| `/api/events/cyber/categories/` | Las 25 categorías oficiales (Tecnología, Hogar, Vestuario y Calzado...) |
| `/api/events/cyber/promotions/`, `/api/promotions/`, `/api/search/?q=` | Promos destacadas / búsqueda de marcas |

## Pero cyber.cl NO publica productos ni precios
La API (y el sitio) es un **directorio de marcas que redirige a cada tienda** — no existe un catálogo de productos/ofertas en cyber.cl, ni durante ni fuera del evento. El hallazgo del 2026-09-28 ("catálogo vacío") era en realidad esto: no hay catálogo que poblar.

## Implicancia: scrapers por tienda
- `backend/app/scraper/cyber_cl.py` usa la API para: categorías oficiales (las `Category` de la app son un espejo de las de cyber.cl), y logos/participación de las tiendas.
- Las ofertas salen de scrapers por tienda en `backend/app/scraper/stores/`:

| Tienda | Fuente de datos | Notas |
|---|---|---|
| Falabella, Sodimac | `__NEXT_DATA__` de las páginas de categoría (`?page=N`) | Filtro server-side "20% dcto y más". Precio CMR (tarjeta) solo como fallback. |
| Ripley | `__NEXT_DATA__` → `findabilityProps.data.products` | El JSON no trae URL; se reconstruye `/<slug del nombre>-<parentProductID>` (verificado 200). |
| Hites | HTML SFCC, atributo `data-gtmselectitem` (JSON) de cada tile, `?start=&sz=48` | |
| Paris, Easy, Jumbo | API pública de Constructor.io (`ac.cnstrc.com/browse/group_id/<id>?key=...`) | Keys públicas del bundle de Cencosud (`cnstrc.com/js/cust/cencosud_*.js`). Paris pagina client-side, su HTML siempre muestra la página 1. Paris solo expone precio final + % dcto → el precio normal se reconstruye. |

**No cubiertas:** Lider.cl (desafío anti-bot "Robot or human?"), Tottus (Cloudflare 526), Mercado Libre (API de listados requiere OAuth).

## Volumen
Las tiendas tienen decenas de miles de productos con descuento por departamento (Falabella Tecnología ≥20% dcto: ~80.000; Ripley Tecno: ~72.000). El scraper recorre todos los departamentos en el orden de relevancia de cada tienda, hasta `SCRAPE_MAX_PAGES` (default 10) páginas por departamento.
