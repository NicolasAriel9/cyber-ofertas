"use client";

import { Plane } from "lucide-react";
import { OffersBrowser, SectionConfig } from "@/components/OffersBrowser";

const TRAVEL: SectionConfig = {
  section: "viajes",
  path: "/viajes/",
  badge: (
    <>
      <Plane size={13} /> Cyber Viajes 2026
    </>
  ),
  title: "Vuelos, paquetes y hoteles en oferta",
  describe: (offers, stores) =>
    `${offers.toLocaleString("es-CL")} ofertas de ${stores} sitios de viaje, actualizadas cada 5 minutos`,
  fallbackDescription: "Tarifas de aerolíneas y agencias de viaje de Chile",
  heroClassName: "bg-gradient-to-br from-sky-500 via-cyan-600 to-indigo-700",
  searchPlaceholder: "¿A dónde quieres ir? Ej: Buenos Aires, Punta Cana...",
  highlightsTitle: "Lo más conveniente",
  highlightsDescription: "Los 3 precios más bajos de cada tipo de viaje (o los mayores descuentos, cuando los hay).",
  defaultSort: "price_asc",
  groupStores: false,
  allStoresLabel: "Todos los sitios",
  categoryOrder: ["vuelos", "paquetes", "alojamientos"],
};

export default function TravelPage() {
  return <OffersBrowser config={TRAVEL} />;
}
