"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { ArrowRight, ChevronDown, Flame, PackageSearch, Search, SlidersHorizontal, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { ReactNode, Suspense, useEffect, useRef, useState } from "react";
import { api, CategoryHighlights, ListingFilters, Section } from "@/lib/api";
import { categoryStyle } from "@/lib/categories";
import { cn } from "@/lib/cn";
import { formatCLP } from "@/lib/format";
import { Button, EmptyState } from "@/components/ui";
import { OfferCard, OfferCardSkeleton } from "@/components/OfferCard";

// Categories shown before "ver más" in the highlights block.
const HIGHLIGHTS_INITIAL = 6;

// Where the user was when they opened a product, so "back" lands there again.
const SCROLL_MAX_AGE_MS = 30 * 60 * 1000;

// The scraper runs every 5 minutes; checking every minute shows its results soon after.
const REFRESH_MS = 60 * 1000;

interface SavedScroll {
  query: string;
  y: number;
  at: number;
}

/** What differs between the offers home page and Cyber Viajes. */
export interface SectionConfig {
  section: Section;
  /** Page path, with trailing slash (next.config has trailingSlash). */
  path: string;
  badge: ReactNode;
  title: string;
  describe: (offers: number, stores: number) => string;
  fallbackDescription: string;
  /** Background of the hero banner. */
  heroClassName: string;
  searchPlaceholder: string;
  highlightsTitle: string;
  highlightsDescription: string;
  defaultSort: SortKey;
  /** Group the store picker into retailers and brand stores. */
  groupStores: boolean;
  /** Empty option of the store picker ("Todas las tiendas"). */
  allStoresLabel: string;
  /** Chip order by category slug; the rest keep the API's alphabetical order. */
  categoryOrder?: string[];
  /** Sort picker options, as [value, label]. */
  sorts: [SortKey, string][];
  /** Minimum discount and star filters (retail only: travel sites have neither). */
  qualityFilters: boolean;
  /** Price filter options, as [min, max] in CLP; max undefined = no limit. */
  priceRanges: [number, number | undefined][];
}

type SortKey = NonNullable<ListingFilters["sort"]>;

const DISCOUNT_OPTIONS = [30, 50, 70];
const RATING_OPTIONS = [4, 4.5];

/** "?precio=20000-100000" <-> [20000, 100000]; "1000000-" has no upper limit. */
function parsePriceRange(value: string | null): [number | undefined, number | undefined] {
  const match = value?.match(/^(\d+)-(\d*)$/);
  return match ? [Number(match[1]) || undefined, match[2] ? Number(match[2]) : undefined] : [undefined, undefined];
}

/** Short enough for a pill on a phone: "$20 mil a $100 mil", "Más de $1 millón". */
function compactCLP(amount: number): string {
  if (amount >= 1_000_000) {
    const millions = amount / 1_000_000;
    return `$${millions.toLocaleString("es-CL")} ${millions === 1 ? "millón" : "millones"}`;
  }
  return amount >= 1_000 ? `$${(amount / 1_000).toLocaleString("es-CL")} mil` : formatCLP(amount);
}

function priceRangeLabel([min, max]: [number, number | undefined]): string {
  if (max === undefined) return `Más de ${compactCLP(min)}`;
  if (!min) return `Hasta ${compactCLP(max)}`;
  return `${compactCLP(min)} a ${compactCLP(max)}`;
}

export function OffersBrowser({ config }: { config: SectionConfig }) {
  return (
    <Suspense fallback={null}>
      <Listings config={config} />
    </Suspense>
  );
}

function Listings({ config }: { config: SectionConfig }) {
  const { section } = config;
  const scrollKey = `cyber-ofertas-scroll-${section}`;
  // Filters live in the URL (?categoria=...&tienda=...&q=...&orden=...&descuento=
  // ...&estrellas=...&precio=...&mas=1) so they survive opening a product and
  // coming back, and links can be shared.
  const searchParams = useSearchParams();
  const router = useRouter();
  const query = searchParams.toString();
  const filters: ListingFilters = {
    section,
    category: searchParams.get("categoria") ?? undefined,
    store: searchParams.get("tienda") ?? undefined,
    search: searchParams.get("q") ?? undefined,
    sort: (searchParams.get("orden") as SortKey | null) ?? config.defaultSort,
    min_discount: Number(searchParams.get("descuento")) || undefined,
    cyber: searchParams.get("cyber") === "1" || undefined,
    min_rating: Number(searchParams.get("estrellas")) || undefined,
  };
  [filters.min_price, filters.max_price] = parsePriceRange(searchParams.get("precio"));
  const showAllHighlights = searchParams.get("mas") === "1";
  // Phones show only the sort picker and a "Filtros" button that opens the rest.
  const [filtersOpen, setFiltersOpen] = useState(false);
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
    if (params.get("orden") === config.defaultSort) params.delete("orden");
    const qs = params.toString();
    if (qs === query && scrollToResults.current) {
      // Same filters again: nothing will re-render, so scroll right away.
      scrollToResults.current = false;
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    // replace, not push: tweaking filters shouldn't fill the back button.
    router.replace(qs ? `${config.path}?${qs}` : config.path, { scroll: false });
  }

  const categoriesQuery = useQuery({ queryKey: ["categories", section], queryFn: () => api.listCategories(section) });
  const storesQuery = useQuery({ queryKey: ["stores", section], queryFn: () => api.listStores(section) });
  const highlightsQuery = useQuery({
    queryKey: ["highlights", section],
    queryFn: () => api.listHighlights(section),
    refetchInterval: REFRESH_MS,
  });
  // Brand-owned stores (slug "marca-...") are listed after the big retailers.
  const allStores = storesQuery.data ?? [];
  const storeGroups: [string, typeof allStores][] = config.groupStores
    ? [
        ["Multitiendas", allStores.filter((s) => !s.slug.startsWith("marca-"))],
        ["Marcas", allStores.filter((s) => s.slug.startsWith("marca-"))],
      ]
    : [["Sitios", allStores]];
  const listingsQuery = useInfiniteQuery({
    // Keep loaded pages ("Cargar más") around for when the user comes back.
    gcTime: 30 * 60 * 1000,
    queryKey: ["listings", filters],
    queryFn: ({ pageParam }) => api.listListings({ ...filters, page: pageParam }),
    // New offers show up without reloading (paused while the tab is hidden).
    refetchInterval: REFRESH_MS,
    initialPageParam: 1,
    getNextPageParam: (last, pages) =>
      pages.reduce((n, p) => n + p.items.length, 0) < last.total ? pages.length + 1 : undefined,
  });
  const listings = listingsQuery.data?.pages.flatMap((p) => p.items);
  const total = listingsQuery.data?.pages[0]?.total;

  // Narrowed or re-sorted: show the matching offers right under the filters
  // instead of below the per-category highlights.
  const hasRefinements = Boolean(
    filters.store || filters.cyber || filters.min_discount || filters.min_rating || filters.min_price || filters.max_price
  );
  const isFiltered = Boolean(filters.search || filters.category || hasRefinements || filters.sort !== config.defaultSort);
  const refinementCount = [filters.store, filters.min_discount, filters.min_rating, filters.min_price || filters.max_price].filter(
    Boolean
  ).length;
  const categories = [...(categoriesQuery.data ?? [])].sort((a, b) => {
    const order = config.categoryOrder ?? [];
    const rank = (slug: string) => (order.includes(slug) ? order.indexOf(slug) : order.length);
    return rank(a.slug) - rank(b.slug);
  });
  const activeCategory = categories.find((c) => c.slug === filters.category);
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
      saved = JSON.parse(sessionStorage.getItem(scrollKey) ?? "null");
      sessionStorage.removeItem(scrollKey);
    } catch {
      return;
    }
    if (!saved || saved.query !== query || Date.now() - saved.at > SCROLL_MAX_AGE_MS) return;
    const y = saved.y;
    requestAnimationFrame(() => window.scrollTo({ top: y, behavior: "instant" }));
  }, [contentReady, query, scrollKey]);

  useEffect(() => {
    if (!scrollToResults.current) return;
    scrollToResults.current = false;
    requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, [query]);

  function rememberScroll(e: React.MouseEvent) {
    if (!(e.target as Element).closest('a[href^="/product"]')) return;
    const saved: SavedScroll = { query, y: window.scrollY, at: Date.now() };
    try {
      sessionStorage.setItem(scrollKey, JSON.stringify(saved));
    } catch {
      // Private mode etc.: coming back just starts at the top.
    }
  }

  function selectCategory(slug: string | undefined) {
    scrollToResults.current = true;
    updateUrl({ categoria: slug });
  }

  function applyFilter(changes: Record<string, string | undefined>) {
    setFiltersOpen(false);
    scrollToResults.current = true;
    updateUrl(changes);
  }

  function clearFilters() {
    setSearch("");
    applyFilter({
      categoria: undefined,
      tienda: undefined,
      q: undefined,
      cyber: undefined,
      orden: undefined,
      descuento: undefined,
      estrellas: undefined,
      precio: undefined,
    });
  }

  return (
    <div className="mx-auto max-w-5xl" onClickCapture={rememberScroll}>
      {/* Hero */}
      <section
        className={cn(
          "relative mb-6 overflow-hidden rounded-3xl px-5 py-7 text-white shadow-lg shadow-accent/20 sm:px-8 sm:py-9",
          config.heroClassName
        )}
      >
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-20 left-1/3 h-48 w-48 rounded-full bg-fuchsia-400/20 blur-3xl" />
        <p className="relative inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1 text-xs font-semibold backdrop-blur">
          {config.badge}
        </p>
        <h1 className="relative mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">{config.title}</h1>
        <p className="relative mt-1.5 text-sm text-white/80">
          {totalOffers ? config.describe(totalOffers, allStores.length) : config.fallbackDescription}
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
            placeholder={config.searchPlaceholder}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button type="submit" className="rounded-xl bg-zinc-900 px-4 py-2 text-sm font-semibold text-white hover:bg-zinc-700">
            Buscar
          </button>
        </form>
      </section>

      {/* Category chips */}
      <nav className="-mx-4 mb-2 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none]">
        <CategoryChip active={!filters.category} label="Todas" onClick={() => updateUrl({ categoria: undefined })} />
        {categories.map((c) => (
          <CategoryChip
            key={c.id}
            slug={c.slug}
            label={c.name}
            active={filters.category === c.slug}
            onClick={() => selectCategory(filters.category === c.slug ? undefined : c.slug)}
          />
        ))}
      </nav>

      {/* Filters: sticky under the header, so they're at hand anywhere on the page. */}
      <div className="sticky top-16 z-30 -mx-4 mb-8 border-b border-border bg-bg/90 px-4 py-2.5 backdrop-blur-md">
        <div className="flex flex-wrap items-center gap-2">
          <SlidersHorizontal size={16} className="shrink-0 text-muted max-sm:hidden" />
          <button
            type="button"
            onClick={() => setFiltersOpen((open) => !open)}
            className={cn(
              "flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13px] font-medium sm:hidden",
              refinementCount || filtersOpen
                ? "border-accent bg-accent/10 text-accent"
                : "border-border bg-surface text-foreground"
            )}
          >
            <SlidersHorizontal size={14} /> Filtros
            {refinementCount > 0 && (
              <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-accent px-1 text-xs text-accent-foreground">
                {refinementCount}
              </span>
            )}
          </button>
          <FilterSelect
            label="Ordenar"
            active={filters.sort !== config.defaultSort}
            value={filters.sort ?? config.defaultSort}
            onChange={(v) => applyFilter({ orden: v })}
          >
            {config.sorts.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </FilterSelect>
          <button
            type="button"
            aria-pressed={Boolean(filters.cyber)}
            title="Solo lo que bajó de precio o apareció desde que empezó el Cyber"
            onClick={() => applyFilter({ cyber: filters.cyber ? undefined : "1" })}
            className={cn(
              "flex shrink-0 items-center gap-1 rounded-full border px-3 py-1.5 text-[13px] font-semibold transition-colors",
              filters.cyber
                ? "border-transparent bg-gradient-to-r from-orange-500 to-rose-500 text-white shadow-md"
                : "border-orange-400/50 bg-orange-500/10 text-orange-500 hover:bg-orange-500/20"
            )}
          >
            <Flame size={14} /> Ofertas Cyber
          </button>
          <div className={cn("grid w-full grid-cols-2 gap-2 sm:contents", !filtersOpen && "max-sm:hidden")}>
            <FilterSelect
              label="Tienda"
              active={Boolean(filters.store)}
              value={filters.store ?? ""}
              onChange={(v) => applyFilter({ tienda: v || undefined })}
            >
              <option value="">{config.allStoresLabel}</option>
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
            </FilterSelect>
            {config.qualityFilters && (
              <>
                <FilterSelect
                  label="Descuento mínimo"
                  active={Boolean(filters.min_discount)}
                  value={String(filters.min_discount ?? "")}
                  onChange={(v) => applyFilter({ descuento: v || undefined })}
                >
                  <option value="">Descuento</option>
                  {DISCOUNT_OPTIONS.map((pct) => (
                    <option key={pct} value={pct}>
                      {pct}% o más
                    </option>
                  ))}
                </FilterSelect>
                <FilterSelect
                  label="Valoración mínima"
                  active={Boolean(filters.min_rating)}
                  value={String(filters.min_rating ?? "")}
                  onChange={(v) => applyFilter({ estrellas: v || undefined })}
                >
                  <option value="">Valoración</option>
                  {RATING_OPTIONS.map((stars) => (
                    <option key={stars} value={stars}>
                      ★ {stars.toLocaleString("es-CL")} o más
                    </option>
                  ))}
                </FilterSelect>
              </>
            )}
            <FilterSelect
              label="Precio"
              active={Boolean(filters.min_price || filters.max_price)}
              value={searchParams.get("precio") ?? ""}
              onChange={(v) => applyFilter({ precio: v || undefined })}
            >
              <option value="">Precio</option>
              {config.priceRanges.map(([min, max]) => (
                <option key={min} value={`${min}-${max ?? ""}`}>
                  {priceRangeLabel([min, max])}
                </option>
              ))}
            </FilterSelect>
          </div>
          {isFiltered && (
            <button
              type="button"
              onClick={clearFilters}
              title="Quitar todos los filtros"
              className="flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1.5 text-[13px] font-medium text-muted transition-colors hover:bg-surface-hover hover:text-foreground"
            >
              <X size={14} /> <span className="max-sm:sr-only">Limpiar</span>
            </button>
          )}
        </div>
      </div>

      {/* Best offers per category */}
      {!isFiltered && (
        <section className="mb-12">
          <div className="mb-5">
            <h2 className="text-xl font-bold tracking-tight sm:text-2xl">{config.highlightsTitle}</h2>
            <p className="mt-0.5 text-sm text-muted">{config.highlightsDescription}</p>
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
      <section ref={resultsRef} className="scroll-mt-32">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold tracking-tight sm:text-2xl">
              {activeCategory ? activeCategory.name : filters.search ? `Resultados para "${filters.search}"` : "Todas las ofertas"}
            </h2>
            <p className="mt-0.5 flex items-center gap-2 text-sm text-muted">
              {total !== undefined ? `${total.toLocaleString("es-CL")} ofertas` : "Buscando ofertas..."}
              <span className="inline-flex items-center gap-1.5 text-xs" title="La lista se actualiza sola cada minuto">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
                </span>
                En vivo
              </span>
            </p>
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
            title={
              filters.cyber
                ? "Todavía no hay ofertas Cyber con estos filtros"
                : isFiltered
                  ? "No encontramos ofertas con esos filtros"
                  : "Todavía no hay ofertas"
            }
            description={
              filters.cyber
                ? "Aquí aparece lo que baja de precio o se publica desde las 00:00 del día del Cyber. Las tiendas se revisan cada 5 minutos."
                : isFiltered
                  ? "Prueba con otra palabra o quita algún filtro."
                  : "Es normal si el Cyber aún no comienza o el scraper no ha corrido."
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

/** A native select styled as a pill; highlighted while it narrows the results. */
function FilterSelect({
  label,
  active,
  value,
  onChange,
  children,
}: {
  label: string;
  active: boolean;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <label
      className={cn(
        "relative flex shrink-0 items-center rounded-full border text-[13px] font-medium transition-colors",
        active
          ? "border-accent bg-accent/10 text-accent"
          : "border-border bg-surface text-foreground hover:bg-surface-hover"
      )}
    >
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-w-0 flex-1 cursor-pointer appearance-none bg-transparent py-1.5 pl-3 pr-7 outline-none [&_optgroup]:bg-surface [&_option]:bg-surface [&_option]:text-foreground"
      >
        {children}
      </select>
      <ChevronDown size={14} className="pointer-events-none absolute right-2.5" />
    </label>
  );
}
