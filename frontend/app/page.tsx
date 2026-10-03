"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { ArrowRight, ChevronDown, Flame, PackageSearch, Search, SlidersHorizontal, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { api, CategoryHighlights, ListingFilters } from "@/lib/api";
import { categoryStyle } from "@/lib/categories";
import { cn } from "@/lib/cn";
import { Button, EmptyState, Select } from "@/components/ui";
import { OfferCard, OfferCardSkeleton } from "@/components/OfferCard";

// Categories shown before "ver más" in the highlights block.
const HIGHLIGHTS_INITIAL = 6;

// Where the user was when they opened a product, so "back" lands there again.
const SCROLL_KEY = "cyber-ofertas-home-scroll";
const SCROLL_MAX_AGE_MS = 30 * 60 * 1000;

interface SavedScroll {
  query: string;
  y: number;
  at: number;
}

export default function ListingsPage() {
  return (
    <Suspense fallback={null}>
      <Listings />
    </Suspense>
  );
}

function Listings() {
  // Filters live in the URL (?categoria=...&tienda=...&q=...&orden=...&mas=1) so
  // they survive opening a product and coming back, and links can be shared.
  const searchParams = useSearchParams();
  const router = useRouter();
  const query = searchParams.toString();
  const filters: ListingFilters = {
    category: searchParams.get("categoria") ?? undefined,
    store: searchParams.get("tienda") ?? undefined,
    search: searchParams.get("q") ?? undefined,
    sort: (searchParams.get("orden") as ListingFilters["sort"]) ?? "discount",
  };
  const showAllHighlights = searchParams.get("mas") === "1";
  const [search, setSearch] = useState(filters.search ?? "");
  const resultsRef = useRef<HTMLDivElement>(null);
  const scrollRestored = useRef(false);
  // Set when a search/category should bring the results into view. The jump
  // waits for the new URL to render: until then the highlights block is still
  // on the page, and scrolling early lands far below once it disappears.
  const scrollToResults = useRef(false);

  function updateUrl(changes: Record<string, string | undefined>) {
    const params = new URLSearchParams(query);
    for (const [key, value] of Object.entries(changes)) {
      if (value) params.set(key, value);
      else params.delete(key);
    }
    if (params.get("orden") === "discount") params.delete("orden");
    const qs = params.toString();
    if (qs === query && scrollToResults.current) {
      // Same filters again: nothing will re-render, so scroll right away.
      scrollToResults.current = false;
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    // replace, not push: tweaking filters shouldn't fill the back button.
    router.replace(qs ? `/?${qs}` : "/", { scroll: false });
  }

  const categoriesQuery = useQuery({ queryKey: ["categories"], queryFn: api.listCategories });
  const storesQuery = useQuery({ queryKey: ["stores"], queryFn: api.listStores });
  const highlightsQuery = useQuery({ queryKey: ["highlights"], queryFn: api.listHighlights });
  // Brand-owned stores (slug "marca-...") are listed after the big retailers.
  const allStores = storesQuery.data ?? [];
  const storeGroups: [string, typeof allStores][] = [
    ["Multitiendas", allStores.filter((s) => !s.slug.startsWith("marca-"))],
    ["Marcas", allStores.filter((s) => s.slug.startsWith("marca-"))],
  ];
  const listingsQuery = useInfiniteQuery({
    // Keep loaded pages ("Cargar más") around for when the user comes back.
    gcTime: 30 * 60 * 1000,
    queryKey: ["listings", filters],
    queryFn: ({ pageParam }) => api.listListings({ ...filters, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (last, pages) =>
      pages.reduce((n, p) => n + p.items.length, 0) < last.total ? pages.length + 1 : undefined,
  });
  const listings = listingsQuery.data?.pages.flatMap((p) => p.items);
  const total = listingsQuery.data?.pages[0]?.total;

  const isFiltered = Boolean(filters.search || filters.category || filters.store);
  const activeCategory = categoriesQuery.data?.find((c) => c.slug === filters.category);
  const highlights = highlightsQuery.data ?? [];
  const visibleHighlights = showAllHighlights ? highlights : highlights.slice(0, HIGHLIGHTS_INITIAL);
  const totalOffers = highlights.reduce((n, h) => n + h.total, 0);

  // Once the offers that were on screen are back (from React Query's cache),
  // jump to where the user was before opening a product.
  const contentReady = listingsQuery.isSuccess && (isFiltered || highlightsQuery.isSuccess);
  useEffect(() => {
    if (scrollRestored.current || !contentReady) return;
    scrollRestored.current = true;
    let saved: SavedScroll | null = null;
    try {
      saved = JSON.parse(sessionStorage.getItem(SCROLL_KEY) ?? "null");
      sessionStorage.removeItem(SCROLL_KEY);
    } catch {
      return;
    }
    if (!saved || saved.query !== query || Date.now() - saved.at > SCROLL_MAX_AGE_MS) return;
    const y = saved.y;
    requestAnimationFrame(() => window.scrollTo({ top: y, behavior: "instant" }));
  }, [contentReady, query]);

  useEffect(() => {
    if (!scrollToResults.current) return;
    scrollToResults.current = false;
    requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, [query]);

  function rememberScroll(e: React.MouseEvent) {
    if (!(e.target as Element).closest('a[href^="/product"]')) return;
    const saved: SavedScroll = { query, y: window.scrollY, at: Date.now() };
    try {
      sessionStorage.setItem(SCROLL_KEY, JSON.stringify(saved));
    } catch {
      // Private mode etc.: coming back just starts at the top.
    }
  }

  function selectCategory(slug: string | undefined) {
    scrollToResults.current = true;
    updateUrl({ categoria: slug });
  }

  function clearFilters() {
    setSearch("");
    updateUrl({ categoria: undefined, tienda: undefined, q: undefined });
  }

  return (
    <div className="mx-auto max-w-5xl" onClickCapture={rememberScroll}>
      {/* Hero */}
      <section className="relative mb-6 overflow-hidden rounded-3xl brand-gradient px-5 py-7 text-white shadow-lg shadow-accent/20 sm:px-8 sm:py-9">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-20 left-1/3 h-48 w-48 rounded-full bg-fuchsia-400/20 blur-3xl" />
        <p className="relative inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1 text-xs font-semibold backdrop-blur">
          <Flame size={13} /> Cyber Monday 2026
        </p>
        <h1 className="relative mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">Las mejores ofertas del Cyber</h1>
        <p className="relative mt-1.5 text-sm text-white/80">
          {totalOffers
            ? `${totalOffers.toLocaleString("es-CL")} ofertas de ${allStores.length} tiendas, actualizadas cada 10 minutos`
            : "Comparando precios de las principales tiendas de Chile"}
        </p>
        <form
          className="relative mt-5 flex max-w-xl items-center gap-2 rounded-2xl bg-white p-1.5 shadow-xl"
          onSubmit={(e) => {
            e.preventDefault();
            scrollToResults.current = true;
            updateUrl({ q: search.trim() || undefined });
            // Close the phone keyboard so it doesn't cover the results.
            (document.activeElement as HTMLElement | null)?.blur();
          }}
        >
          <Search size={17} className="ml-2.5 shrink-0 text-zinc-400" />
          <input
            className="min-w-0 flex-1 bg-transparent py-2 text-sm text-zinc-900 outline-none placeholder:text-zinc-400"
            placeholder="¿Qué andas buscando? Ej: notebook, smart tv 55..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button type="submit" className="rounded-xl bg-zinc-900 px-4 py-2 text-sm font-semibold text-white hover:bg-zinc-700">
            Buscar
          </button>
        </form>
      </section>

      {/* Category chips */}
      <nav className="-mx-4 mb-8 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none]">
        <CategoryChip active={!filters.category} label="Todas" onClick={() => updateUrl({ categoria: undefined })} />
        {categoriesQuery.data?.map((c) => (
          <CategoryChip
            key={c.id}
            slug={c.slug}
            label={c.name}
            active={filters.category === c.slug}
            onClick={() => selectCategory(filters.category === c.slug ? undefined : c.slug)}
          />
        ))}
      </nav>

      {/* Best offers per category */}
      {!isFiltered && (
        <section className="mb-12">
          <div className="mb-5">
            <h2 className="text-xl font-bold tracking-tight sm:text-2xl">Lo mejor de cada categoría</h2>
            <p className="mt-0.5 text-sm text-muted">Las 3 ofertas que más ahorran en cada sección, sin precios inflados.</p>
          </div>

          {highlightsQuery.isLoading && (
            <div className="space-y-10">
              {Array.from({ length: 2 }).map((_, i) => (
                <div key={i}>
                  <div className="skeleton mb-4 h-8 w-48 rounded-xl" />
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                    {Array.from({ length: 3 }).map((_, j) => (
                      <OfferCardSkeleton key={j} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="space-y-10">
            {visibleHighlights.map((h) => (
              <HighlightRow key={h.category.id} highlight={h} onSeeAll={() => selectCategory(h.category.slug)} />
            ))}
          </div>

          {highlights.length > HIGHLIGHTS_INITIAL && (
            <div className="mt-8 flex justify-center">
              <Button variant="secondary" onClick={() => updateUrl({ mas: showAllHighlights ? undefined : "1" })}>
                {showAllHighlights ? "Mostrar menos categorías" : `Ver las ${highlights.length - HIGHLIGHTS_INITIAL} categorías restantes`}
                <ChevronDown size={15} className={cn("transition-transform", showAllHighlights && "rotate-180")} />
              </Button>
            </div>
          )}
        </section>
      )}

      {/* All offers */}
      <section ref={resultsRef} className="scroll-mt-20">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold tracking-tight sm:text-2xl">
              {activeCategory ? activeCategory.name : filters.search ? `Resultados para "${filters.search}"` : "Todas las ofertas"}
            </h2>
            <p className="mt-0.5 text-sm text-muted">
              {total !== undefined ? `${total.toLocaleString("es-CL")} ofertas` : "Buscando ofertas..."}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {isFiltered && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X size={14} /> Limpiar filtros
              </Button>
            )}
            <Select
              className="py-2"
              value={filters.store ?? ""}
              onChange={(e) => updateUrl({ tienda: e.target.value || undefined })}
            >
              <option value="">Todas las tiendas</option>
              {storeGroups.map(([label, stores]) =>
                stores.length ? (
                  <optgroup key={label} label={label}>
                    {stores.map((s) => (
                      <option key={s.id} value={s.slug}>
                        {s.name}
                      </option>
                    ))}
                  </optgroup>
                ) : null,
              )}
            </Select>
            <Select
              className="py-2"
              value={filters.sort}
              onChange={(e) => updateUrl({ orden: e.target.value })}
            >
              <option value="discount">Mayor descuento</option>
              <option value="price_asc">Precio: menor a mayor</option>
              <option value="price_desc">Precio: mayor a menor</option>
              <option value="recent">Recién llegadas</option>
            </Select>
          </div>
        </div>

        {listingsQuery.isLoading && (
          <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <OfferCardSkeleton key={i} />
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
            title={isFiltered ? "No encontramos ofertas con esos filtros" : "Todavía no hay ofertas"}
            description={
              isFiltered ? "Prueba con otra palabra o quita algún filtro." : "Es normal si el Cyber aún no comienza o el scraper no ha corrido."
            }
          />
        )}

        <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
          {listings?.map((listing) => (
            <OfferCard key={listing.id} listing={listing} />
          ))}
        </div>

        {listingsQuery.hasNextPage && (
          <div className="mt-8 flex justify-center">
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
      </section>
    </div>
  );
}

function CategoryChip({
  slug,
  label,
  active,
  onClick,
}: {
  slug?: string;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  const Icon = slug ? categoryStyle(slug).icon : Flame;
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex shrink-0 items-center gap-1.5 rounded-full border px-3.5 py-2 text-sm font-medium transition-all active:scale-95",
        active
          ? "border-transparent bg-foreground text-bg shadow-md"
          : "border-border bg-surface text-foreground hover:border-accent/40 hover:bg-surface-hover"
      )}
    >
      <Icon size={15} />
      {label}
    </button>
  );
}

function HighlightRow({ highlight, onSeeAll }: { highlight: CategoryHighlights; onSeeAll: () => void }) {
  const { icon: Icon, gradient } = categoryStyle(highlight.category.slug);
  return (
    <div className="animate-fade-in-up">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-md", gradient)}>
            <Icon size={19} />
          </span>
          <div className="min-w-0">
            <h3 className="truncate text-lg font-bold leading-tight">{highlight.category.name}</h3>
            <p className="text-xs text-muted">{highlight.total.toLocaleString("es-CL")} ofertas</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onSeeAll}
          className="flex shrink-0 items-center gap-1 rounded-full px-3 py-1.5 text-sm font-semibold text-accent transition-colors hover:bg-accent/10"
        >
          Ver todas <ArrowRight size={14} />
        </button>
      </div>
      {/* Swipeable on phones, three columns from sm up. */}
      <div className="-mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-2 [scrollbar-width:none] sm:mx-0 sm:grid sm:grid-cols-3 sm:gap-4 sm:overflow-visible sm:px-0 sm:pb-0">
        {highlight.listings.map((listing, i) => (
          <div key={listing.id} className="w-[72%] shrink-0 snap-start sm:w-auto">
            <OfferCard listing={listing} rank={i + 1} />
          </div>
        ))}
      </div>
    </div>
  );
}
