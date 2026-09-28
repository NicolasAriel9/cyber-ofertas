"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, getSubscriberId } from "@/lib/api";

export default function FavoritesPage() {
  const subscriberId = getSubscriberId();
  const queryClient = useQueryClient();

  const favoritesQuery = useQuery({
    queryKey: ["favorites", subscriberId],
    queryFn: () => api.listFavorites(subscriberId!),
    enabled: subscriberId !== null,
  });

  const removeFavorite = useMutation({
    mutationFn: (favoriteId: number) => api.removeFavorite(favoriteId, subscriberId!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["favorites"] }),
  });

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-4 text-2xl font-bold">Mis favoritos</h1>

      {favoritesQuery.data?.length === 0 && (
        <p className="text-gray-500">Todavía no tienes productos favoritos.</p>
      )}

      <div className="flex flex-col gap-2">
        {favoritesQuery.data?.map((fav) => (
          <div key={fav.id} className="flex items-center justify-between rounded border p-3">
            <Link href={`/product?id=${fav.product.id}`} className="min-w-0">
              <p className="font-medium">{fav.product.canonical_title}</p>
              <p className="text-sm text-gray-500">
                Mejor precio: {fav.product.best_price ? `$${fav.product.best_price.toLocaleString("es-CL")}` : "-"}
                {fav.product.best_store ? ` en ${fav.product.best_store}` : ""}
              </p>
              {fav.target_price && (
                <p className="text-sm text-blue-600">
                  Aviso cuando baje de ${fav.target_price.toLocaleString("es-CL")}
                </p>
              )}
            </Link>
            <button
              className="shrink-0 text-sm text-red-600"
              onClick={() => removeFavorite.mutate(fav.id)}
            >
              Quitar
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
