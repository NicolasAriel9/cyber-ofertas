import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "cyber-ofertas-personal-tool/0.1 (contacto: 81039659+NicolasAriel9@users.noreply.github.com)"
)

CATEGORY_SLUGS = [
    "tecnologia",
    "hogar",
    "vestuario-y-calzado",
    "multitiendas-y-supermercados",
    "viajes-y-turismo",
    "deportes-y-outdoor",
]


def fetch_category_page(category_slug: str) -> str:
    url = f"https://cyber.cl/cyber/marcas/{category_slug}"
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text
