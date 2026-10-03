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
};

export default function HomePage() {
  return <OffersBrowser config={PRODUCTS} />;
}
