"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api, ApiError, getSubscriberId, Listing, ListingFilters } from "@/lib/api";

export default function ListingsPage() {
  const [filters, setFilters] = useState<ListingFilters>({ sort: "discount" });
  const [search, setSearch] = useState("");

  const categoriesQuery = useQuery({ queryKey: ["categories"], queryFn: api.listCategories });
  const storesQuery = useQuery({ queryKey: ["stores"], queryFn: api.listStores });
  const listingsQuery = useQuery({
    queryKey: ["listings", filters],
    queryFn: () => api.listListings(filters),
  });

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-4 text-2xl font-bold">Ofertas del Cyber</h1>

      <div className="mb-4 flex flex-wrap gap-2">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setFilters((f) => ({ ...f, search }));
          }}
        >
          <input
            className="rounded border px-3 py-1.5"
            placeholder="Buscar producto..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </form>

        <select
          className="rounded border px-2 py-1.5"
          value={filters.category ?? ""}
          onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value || undefined }))}
        >
          <option value="">Todas las categorías</option>
          {categoriesQuery.data?.map((c) => (
            <option key={c.id} value={c.slug}>
              {c.name}
            </option>
          ))}
        </select>

        <select
          className="rounded border px-2 py-1.5"
          value={filters.store ?? ""}
          onChange={(e) => setFilters((f) => ({ ...f, store: e.target.value || undefined }))}
        >
          <option value="">Todas las tiendas</option>
          {storesQuery.data?.map((s) => (
            <option key={s.id} value={s.slug}>
              {s.name}
            </option>
          ))}
        </select>

        <select
          className="rounded border px-2 py-1.5"
          value={filters.sort}
          onChange={(e) => setFilters((f) => ({ ...f, sort: e.target.value as ListingFilters["sort"] }))}
        >
          <option value="discount">Mayor descuento</option>
          <option value="price_asc">Precio: menor a mayor</option>
          <option value="price_desc">Precio: mayor a menor</option>
        </select>
      </div>

      {listingsQuery.isLoading && <p>Cargando...</p>}
      {listingsQuery.isError && <p className="text-red-600">No se pudieron cargar las ofertas.</p>}
      {listingsQuery.data?.length === 0 && (
        <p className="text-gray-500">
          Sin ofertas todavía. Es normal si el Cyber aún no comienza o el scraper no ha corrido.
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
        {listingsQuery.data?.map((listing) => (
          <ListingCard key={listing.id} listing={listing} />
        ))}
      </div>
    </div>
  );
}

function ListingCard({ listing }: { listing: Listing }) {
  const queryClient = useQueryClient();
  const subscriberId = getSubscriberId();

  const addFavorite = useMutation({
    mutationFn: () => {
      if (!subscriberId) throw new Error("No subscriber selected");
      return api.addFavorite(subscriberId, listing.product_id);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["favorites"] }),
  });

  return (
    <div className="rounded border p-3 hover:shadow">
      <div className="mb-1 flex items-start justify-between gap-2">
        <Link href={`/product?id=${listing.product_id}`} className="min-w-0">
          <p className="text-xs uppercase text-gray-500">{listing.store.name}</p>
          <p className="font-medium">{listing.title}</p>
        </Link>
        <button
          title="Agregar a favoritos"
          className="shrink-0 text-xl leading-none"
          onClick={() => addFavorite.mutate()}
          disabled={addFavorite.isPending}
        >
          {addFavorite.isSuccess ? "❤️" : "🤍"}
        </button>
      </div>
      <p className="text-lg font-bold">
        {listing.latest_price ? `$${listing.latest_price.toLocaleString("es-CL")}` : "-"}
      </p>
      {listing.latest_discount_pct ? (
        <p className="text-sm text-green-700">-{listing.latest_discount_pct.toFixed(0)}%</p>
      ) : null}
      <a
        href={listing.url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-1 inline-block text-sm text-blue-600 underline"
      >
        Ver oferta ↗
      </a>
      {addFavorite.isError && (
        <p className="mt-1 text-xs text-red-600">
          {addFavorite.error instanceof ApiError && addFavorite.error.status === 409
            ? "Ya estaba en favoritos"
            : "No se pudo agregar"}
        </p>
      )}
    </div>
  );
}
