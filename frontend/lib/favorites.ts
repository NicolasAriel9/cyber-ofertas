"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, getSubscriberId } from "@/lib/api";

/** The current subscriber's favorites, plus a toggle keyed by product id. */
export function useFavorites() {
  const subscriberId = getSubscriberId();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["favorites", subscriberId],
    queryFn: () => api.listFavorites(subscriberId!),
    enabled: subscriberId !== null,
  });
  const byProduct = new Map(query.data?.map((f) => [f.product.id, f]));

  const toggle = useMutation({
    mutationFn: async (productId: number) => {
      if (!subscriberId) throw new Error("No subscriber selected");
      const existing = byProduct.get(productId);
      if (existing) await api.removeFavorite(existing.id, subscriberId);
      else await api.addFavorite(subscriberId, productId);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["favorites"] }),
  });

  return {
    query,
    isFavorite: (productId: number) => byProduct.has(productId),
    toggle: (productId: number) => toggle.mutate(productId),
    isPending: (productId: number) => toggle.isPending && toggle.variables === productId,
  };
}
