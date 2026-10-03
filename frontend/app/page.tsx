"use client";

import { Flame } from "lucide-react";
import { OffersBrowser, SectionConfig } from "@/components/OffersBrowser";

const PRODUCTS: SectionConfig = {
  section: "productos",
  path: "/",
  badge: (
    <>
      <Flame size={13} /> Cyber Monday 2026
    </>
  ),
  title: "Las mejores ofertas del Cyber",
  describe: (offers, stores) =>
    `${offers.toLocaleString("es-CL")} ofertas de ${stores} tiendas, actualizadas cada 5 minutos`,
  fallbackDescription: "Comparando precios de las principales tiendas de Chile",
  heroClassName: "brand-gradient",
  searchPlaceholder: "¿Qué andas buscando? Ej: notebook, smart tv 55...",
  highlightsTitle: "Lo mejor de cada categoría",
  highlightsDescription: "Las 3 ofertas que más ahorran en cada sección, sin precios inflados.",
  defaultSort: "discount",
  groupStores: true,
  allStoresLabel: "Todas las tiendas",
  sorts: [
    ["discount", "Mayor descuento"],
    ["savings", "Mayor ahorro en $"],
    ["rating", "Mejor valoradas"],
    ["price_asc", "Precio: menor a mayor"],
    ["price_desc", "Precio: mayor a menor"],
    ["recent", "Recién llegadas"],
  ],
  qualityFilters: true,
  priceRanges: [
    [0, 20_000],
    [20_000, 100_000],
    [100_000, 300_000],
    [300_000, 1_000_000],
    [1_000_000, undefined],
  ],
};

export default function HomePage() {
  return <OffersBrowser config={PRODUCTS} />;
}
