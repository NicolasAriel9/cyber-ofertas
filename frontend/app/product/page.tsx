"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import { api, getSubscriberId } from "@/lib/api";

export default function ProductPage() {
  return (
    <Suspense fallback={<p>Cargando...</p>}>
      <ProductDetail />
    </Suspense>
  );
}

function ProductDetail() {
  const searchParams = useSearchParams();
  const id = Number(searchParams.get("id"));
  const subscriberId = getSubscriberId();
  const [targetPrice, setTargetPrice] = useState("");
  const queryClient = useQueryClient();

  const productQuery = useQuery({
    queryKey: ["product", id],
    queryFn: () => api.getProduct(id),
    enabled: Number.isFinite(id) && id > 0,
  });

  const historyQuery = useQuery({
    queryKey: ["price-history", id],
    queryFn: () => api.getPriceHistory(id),
    enabled: Number.isFinite(id) && id > 0,
  });

  const addFavorite = useMutation({
    mutationFn: () => {
      if (!subscriberId) throw new Error("No subscriber selected");
      const parsed = targetPrice ? Number(targetPrice) : undefined;
      return api.addFavorite(subscriberId, id, parsed);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["favorites"] }),
  });

  if (!Number.isFinite(id) || id <= 0) return <p>Producto inválido.</p>;
  if (productQuery.isLoading) return <p>Cargando...</p>;
  if (productQuery.isError || !productQuery.data) return <p>No se encontró el producto.</p>;

  const product = productQuery.data;
  const chartData = (historyQuery.data ?? []).map((p) => ({
    date: new Date(p.scraped_at).toLocaleDateString("es-CL"),
    price: p.price,
    store: p.store_slug,
  }));

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-1 text-2xl font-bold">{product.canonical_title}</h1>
      {product.category && <p className="mb-4 text-sm text-gray-500">{product.category.name}</p>}

      <h2 className="mb-2 font-semibold">Comparar precios</h2>
      <div className="mb-6 flex flex-col gap-2">
        {product.listings.map((listing) => (
          <a
            key={listing.id}
            href={listing.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between rounded border p-3 hover:shadow"
          >
            <span>{listing.store.name}</span>
            <span className="font-bold">
              {listing.latest_price ? `$${listing.latest_price.toLocaleString("es-CL")}` : "-"}
            </span>
          </a>
        ))}
      </div>

      {chartData.length > 1 && (
        <div className="mb-6 h-64">
          <h2 className="mb-2 font-semibold">Historial de precio</h2>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis domain={["auto", "auto"]} />
              <Tooltip />
              <Line type="monotone" dataKey="price" stroke="#2563eb" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <h2 className="mb-2 font-semibold">Avisarme cuando baje de precio</h2>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          addFavorite.mutate();
        }}
      >
        <input
          className="rounded border px-3 py-1.5"
          placeholder="Precio objetivo (opcional)"
          value={targetPrice}
          onChange={(e) => setTargetPrice(e.target.value)}
        />
        <button className="rounded bg-black px-4 py-1.5 text-white" type="submit">
          {addFavorite.isSuccess ? "Agregado ✓" : "Seguir producto"}
        </button>
      </form>
    </div>
  );
}
