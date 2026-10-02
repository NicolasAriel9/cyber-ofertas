"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Heart, PackageSearch, Search, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { api, ApiError, getSubscriberId, Listing, ListingFilters } from "@/lib/api";
import { formatCLP } from "@/lib/format";
import { Badge, Button, Card, EmptyState, IconButton, Input, Select, Skeleton } from "@/components/ui";
import { ProductThumb } from "@/components/ProductThumb";

export default function ListingsPage() {
  const [filters, setFilters] = useState<ListingFilters>({ sort: "discount" });
  const [search, setSearch] = useState("");

  const categoriesQuery = useQuery({ queryKey: ["categories"], queryFn: api.listCategories });
  const storesQuery = useQuery({ queryKey: ["stores"], queryFn: api.listStores });
  const listingsQuery = useInfiniteQuery({
    queryKey: ["listings", filters],
    queryFn: ({ pageParam }) => api.listListings({ ...filters, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (last, pages) =>
      pages.reduce((n, p) => n + p.items.length, 0) < last.total ? pages.length + 1 : undefined,
  });
  const listings = listingsQuery.data?.pages.flatMap((p) => p.items);
  const total = listingsQuery.data?.pages[0]?.total;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          Ofertas del <span className="brand-gradient-text">Cyber</span>
        </h1>
        <p className="mt-1 text-sm text-muted">
          {total !== undefined
            ? `${total.toLocaleString("es-CL")} ofertas encontradas`
            : "Buscando las mejores ofertas..."}
        </p>
      </div>

      <Card className="mb-6 flex flex-wrap items-center gap-2 p-3">
        <div className="relative min-w-[180px] flex-1">
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setFilters((f) => ({ ...f, search }));
            }}
          >
            <Input
              className="pl-9"
              placeholder="Buscar producto..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </form>
        </div>

        <Select
          value={filters.category ?? ""}
          onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value || undefined }))}
        >
          <option value="">Todas las categorías</option>
          {categoriesQuery.data?.map((c) => (
            <option key={c.id} value={c.slug}>
              {c.name}
            </option>
          ))}
        </Select>

        <Select
          value={filters.store ?? ""}
          onChange={(e) => setFilters((f) => ({ ...f, store: e.target.value || undefined }))}
        >
          <option value="">Todas las tiendas</option>
          {storesQuery.data?.map((s) => (
            <option key={s.id} value={s.slug}>
              {s.name}
            </option>
          ))}
        </Select>

        <Select
          value={filters.sort}
          onChange={(e) => setFilters((f) => ({ ...f, sort: e.target.value as ListingFilters["sort"] }))}
        >
          <option value="discount">Mayor descuento</option>
          <option value="price_asc">Precio: menor a mayor</option>
          <option value="price_desc">Precio: mayor a menor</option>
        </Select>
      </Card>

      {listingsQuery.isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="overflow-hidden">
              <Skeleton className="h-36 w-full rounded-none" />
              <div className="space-y-2 p-4">
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-5 w-24" />
              </div>
            </Card>
          ))}
        </div>
      )}

      {listingsQuery.isError && (
        <EmptyState
          icon={<SlidersHorizontal size={20} />}
          title="No se pudieron cargar las ofertas"
          description="Revisa la conexión con el backend e intenta de nuevo."
        />
      )}

      {listings?.length === 0 && (
        <EmptyState
          icon={<PackageSearch size={20} />}
          title="Todavía no hay ofertas"
          description="Es normal si el Cyber aún no comienza o el scraper no ha corrido."
        />
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
        {listings?.map((listing) => (
          <ListingCard key={listing.id} listing={listing} />
        ))}
      </div>

      {listingsQuery.hasNextPage && (
        <div className="mt-6 flex justify-center">
          <Button
            variant="secondary"
            onClick={() => listingsQuery.fetchNextPage()}
            disabled={listingsQuery.isFetchingNextPage}
          >
            {listingsQuery.isFetchingNextPage
              ? "Cargando..."
              : `Cargar más (${listings?.length.toLocaleString("es-CL")} de ${total?.toLocaleString("es-CL")})`}
          </Button>
        </div>
      )}
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

  const alreadyFavorited = addFavorite.isSuccess;
  const duplicateFavorite = addFavorite.error instanceof ApiError && addFavorite.error.status === 409;

  return (
    <Card className="group flex flex-col overflow-hidden transition-shadow duration-200 hover:shadow-lg hover:shadow-black/5">
      <Link href={`/product?id=${listing.product_id}`} className="relative block">
        <ProductThumb
          src={listing.image_url}
          seed={listing.title}
          label={listing.store.name}
          className="h-36 w-full"
        />
        {listing.latest_discount_pct ? (
          <Badge variant="accent" className="absolute left-2.5 top-2.5 shadow-sm">
            -{listing.latest_discount_pct.toFixed(0)}%
          </Badge>
        ) : null}
      </Link>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <Badge>{listing.store.name}</Badge>
          <IconButton
            title="Agregar a favoritos"
            active={alreadyFavorited || duplicateFavorite}
            onClick={() => addFavorite.mutate()}
            disabled={addFavorite.isPending}
          >
            <Heart size={15} fill={alreadyFavorited || duplicateFavorite ? "currentColor" : "none"} />
          </IconButton>
        </div>

        <Link href={`/product?id=${listing.product_id}`} className="line-clamp-2 text-sm font-medium">
          {listing.title}
        </Link>

        <div className="mt-auto flex items-baseline gap-2 pt-1">
          <span className="text-lg font-bold">
            {listing.latest_price ? formatCLP(listing.latest_price) : "-"}
          </span>
          {listing.latest_original_price && (
            <span className="text-xs text-muted line-through">{formatCLP(listing.latest_original_price)}</span>
          )}
        </div>

        <a
          href={listing.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-1 flex items-center gap-1 text-xs font-medium text-accent hover:underline"
        >
          Ver oferta <ExternalLink size={12} />
        </a>
      </div>
    </Card>
  );
}
