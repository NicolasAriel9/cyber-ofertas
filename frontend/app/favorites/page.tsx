"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, Star, Trash2 } from "lucide-react";
import Link from "next/link";
import { api, getSubscriberId } from "@/lib/api";
import { formatCLP } from "@/lib/format";
import { Card, EmptyState, IconButton, Skeleton } from "@/components/ui";
import { ProductThumb } from "@/components/ProductThumb";

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
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Mis favoritos</h1>
        <p className="mt-1 text-sm text-muted">Productos que estás siguiendo para no perderte una baja de precio.</p>
      </div>

      {favoritesQuery.isLoading && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="flex items-center gap-3 p-3">
              <Skeleton className="h-14 w-14 shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-3 w-1/3" />
              </div>
            </Card>
          ))}
        </div>
      )}

      {favoritesQuery.data?.length === 0 && (
        <EmptyState
          icon={<Star size={20} />}
          title="Todavía no tienes favoritos"
          description="Toca el corazón en cualquier oferta para empezar a seguirla."
        />
      )}

      <div className="flex flex-col gap-3">
        {favoritesQuery.data?.map((fav) => (
          <Card key={fav.id} className="flex items-center gap-3 p-3 transition-shadow hover:shadow-md hover:shadow-black/5">
            <Link href={`/product?id=${fav.product.id}`} className="shrink-0">
              <ProductThumb
                src={fav.product.image_url}
                seed={fav.product.canonical_title}
                label={fav.product.best_store ?? undefined}
                className="h-14 w-14 rounded-xl"
              />
            </Link>
            <Link href={`/product?id=${fav.product.id}`} className="min-w-0 flex-1">
              <p className="truncate font-medium">{fav.product.canonical_title}</p>
              <p className="text-sm text-muted">
                Mejor precio: {fav.product.best_price ? formatCLP(fav.product.best_price) : "-"}
                {fav.product.best_store ? ` en ${fav.product.best_store}` : ""}
              </p>
              {fav.target_price && (
                <p className="mt-0.5 flex items-center gap-1 text-xs font-medium text-accent">
                  <BellRing size={12} /> Aviso cuando baje de {formatCLP(fav.target_price)}
                </p>
              )}
            </Link>
            <IconButton
              title="Quitar de favoritos"
              onClick={() => removeFavorite.mutate(fav.id)}
              className="text-muted hover:text-danger"
            >
              <Trash2 size={15} />
            </IconButton>
          </Card>
        ))}
      </div>
    </div>
  );
}
