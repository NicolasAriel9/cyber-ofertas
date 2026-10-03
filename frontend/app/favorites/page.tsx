"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BellRing,
  Check,
  ExternalLink,
  Heart,
  PiggyBank,
  Store,
  Trash2,
  TrendingDown,
  TrendingUp,
  Trophy,
  X,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { api, Favorite, getSubscriberId } from "@/lib/api";
import { categoryStyle } from "@/lib/categories";
import { cn } from "@/lib/cn";
import { useFavorites } from "@/lib/favorites";
import { formatCLP } from "@/lib/format";
import { Card, EmptyState, IconButton, Select, Skeleton } from "@/components/ui";
import { DiscountBadge, savingsOf } from "@/components/OfferCard";
import { ProductThumb } from "@/components/ProductThumb";

type SortKey = "recent" | "discount" | "drop" | "price";

/** Negative when the price went down since the product was favorited. */
function changeSinceAdded(fav: Favorite): number | null {
  const { best_price } = fav.product;
  return best_price !== null && fav.price_when_added !== null ? best_price - fav.price_when_added : null;
}

const SORTS: Record<SortKey, (a: Favorite, b: Favorite) => number> = {
  recent: () => 0, // the API already returns newest first
  discount: (a, b) => (b.product.best_discount_pct ?? 0) - (a.product.best_discount_pct ?? 0),
  drop: (a, b) => (changeSinceAdded(a) ?? 0) - (changeSinceAdded(b) ?? 0),
  price: (a, b) => (a.product.best_price ?? Infinity) - (b.product.best_price ?? Infinity),
};

export default function FavoritesPage() {
  const { query } = useFavorites();
  const [sort, setSort] = useState<SortKey>("recent");
  const favorites = [...(query.data ?? [])].sort(SORTS[sort]);

  const dropped = favorites.filter((f) => (changeSinceAdded(f) ?? 0) < 0);
  const totalSavings = favorites.reduce(
    (n, f) => n + (savingsOf(f.product.best_price, f.product.best_original_price) ?? 0),
    0
  );
  const belowTarget = favorites.filter(
    (f) => f.target_price !== null && f.product.best_price !== null && f.product.best_price <= f.target_price
  );

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Mis favoritos</h1>
          <p className="mt-1 text-sm text-muted">Los productos que sigues, con su mejor precio entre todas las tiendas.</p>
        </div>
        {favorites.length > 1 && (
          <Select className="py-2" value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
            <option value="recent">Recién agregados</option>
            <option value="drop">Mayor baja de precio</option>
            <option value="discount">Mayor descuento</option>
            <option value="price">Menor precio</option>
          </Select>
        )}
      </div>

      {favorites.length > 0 && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatTile icon={<Heart size={16} />} label="Siguiendo" value={String(favorites.length)} />
          <StatTile
            icon={<TrendingDown size={16} />}
            label="Bajaron de precio"
            value={String(dropped.length)}
            tone={dropped.length ? "success" : undefined}
          />
          <StatTile
            icon={<BellRing size={16} />}
            label="Bajo tu precio objetivo"
            value={String(belowTarget.length)}
            tone={belowTarget.length ? "success" : undefined}
          />
          <StatTile icon={<PiggyBank size={16} />} label="Ahorro vs precio normal" value={formatCLP(totalSavings)} />
        </div>
      )}

      {query.isLoading && (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="flex gap-4 p-4">
              <Skeleton className="h-28 w-28 shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-6 w-1/3" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            </Card>
          ))}
        </div>
      )}

      {query.data?.length === 0 && (
        <EmptyState
          icon={<Heart size={20} />}
          title="Todavía no tienes favoritos"
          description="Toca el corazón en cualquier oferta para seguirla y recibir un aviso por Telegram si baja de precio."
        />
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {favorites.map((fav) => (
          <FavoriteCard key={fav.id} favorite={fav} />
        ))}
      </div>
    </div>
  );
}

function StatTile({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone?: "success";
}) {
  return (
    <Card className="p-3.5">
      <div className={cn("flex items-center gap-1.5 text-xs font-medium text-muted", tone === "success" && "text-success")}>
        {icon} {label}
      </div>
      <p className={cn("mt-1 text-xl font-extrabold tracking-tight", tone === "success" && "text-success")}>{value}</p>
    </Card>
  );
}

function FavoriteCard({ favorite: fav }: { favorite: Favorite }) {
  const queryClient = useQueryClient();
  const subscriberId = getSubscriberId();
  const { product } = fav;
  const change = changeSinceAdded(fav);
  const atLowest = product.best_price !== null && product.lowest_price !== null && product.best_price <= product.lowest_price;
  const reachedTarget = fav.target_price !== null && product.best_price !== null && product.best_price <= fav.target_price;
  const productHref = `/product?id=${product.id}`;
  const CategoryIcon = categoryStyle(product.category?.slug).icon;

  const remove = useMutation({
    mutationFn: () => api.removeFavorite(fav.id, subscriberId!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["favorites"] }),
  });

  return (
    <Card
      className={cn(
        "relative flex flex-col overflow-hidden transition-shadow hover:shadow-lg hover:shadow-black/5",
        reachedTarget && "border-success ring-2 ring-success/20"
      )}
    >
      <div className="flex gap-4 p-4">
        <Link href={productHref} className="relative shrink-0 self-start overflow-hidden rounded-xl border border-border bg-white">
          <ProductThumb
            src={product.image_url}
            seed={product.canonical_title}
            label={product.best_store ?? undefined}
            className="h-28 w-28 object-contain p-2"
          />
          {product.best_discount_pct ? (
            <DiscountBadge pct={product.best_discount_pct} className="absolute left-1.5 top-1.5 px-1.5 text-xs" />
          ) : null}
        </Link>

        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1 truncate text-[11px] font-semibold uppercase tracking-wide text-muted">
            <CategoryIcon size={12} />
            {[product.brand, product.category?.name].filter(Boolean).join(" · ") || "Producto"}
          </p>
          <Link href={productHref} className="mt-0.5 line-clamp-2 text-sm font-medium leading-snug hover:text-accent">
            {product.canonical_title}
          </Link>

          <div className="mt-2 flex flex-wrap items-baseline gap-x-2">
            <span className="text-xl font-extrabold tracking-tight">
              {product.best_price !== null ? formatCLP(product.best_price) : "Sin stock"}
            </span>
            {product.best_original_price && (
              <span className="text-xs text-muted line-through">{formatCLP(product.best_original_price)}</span>
            )}
          </div>
          {product.best_store && <p className="text-xs text-muted">en {product.best_store}</p>}
        </div>

        <IconButton
          title="Quitar de favoritos"
          onClick={() => remove.mutate()}
          disabled={remove.isPending}
          className="absolute right-3 top-3 h-8 w-8 text-muted hover:text-danger"
        >
          <Trash2 size={14} />
        </IconButton>
      </div>

      {/* What changed, at a glance */}
      <div className="flex flex-wrap gap-1.5 px-4 pb-3">
        {change !== null && change < 0 && (
          <Pill tone="success" icon={<TrendingDown size={12} />}>
            Bajó {formatCLP(-change)} desde que lo agregaste
          </Pill>
        )}
        {change !== null && change > 0 && (
          <Pill tone="danger" icon={<TrendingUp size={12} />}>
            Subió {formatCLP(change)} desde que lo agregaste
          </Pill>
        )}
        {change === 0 && <Pill>Mismo precio que cuando lo agregaste</Pill>}
        {atLowest && (
          <Pill tone="amber" icon={<Trophy size={12} />}>
            Precio más bajo visto
          </Pill>
        )}
        {product.store_count > 1 && (
          <Link href={productHref}>
            <Pill icon={<Store size={12} />}>Comparar en {product.store_count} tiendas</Pill>
          </Link>
        )}
      </div>

      <div className="mt-auto flex items-center gap-2 border-t border-border bg-surface-hover/50 px-4 py-2.5">
        <TargetPrice favorite={fav} reached={reachedTarget} />
        {product.best_url && (
          <a
            href={product.best_url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto flex shrink-0 items-center gap-1.5 rounded-lg brand-gradient px-3 py-1.5 text-xs font-semibold text-accent-foreground shadow-sm hover:brightness-110"
          >
            Ir a la tienda <ExternalLink size={12} />
          </a>
        )}
      </div>
    </Card>
  );
}

function Pill({
  tone,
  icon,
  children,
}: {
  tone?: "success" | "danger" | "amber";
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        !tone && "bg-surface-hover text-muted",
        tone === "success" && "bg-success-bg text-success",
        tone === "danger" && "bg-danger-bg text-danger",
        tone === "amber" && "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
      )}
    >
      {icon}
      {children}
    </span>
  );
}

/** Inline editor for the price-drop alert threshold. */
function TargetPrice({ favorite, reached }: { favorite: Favorite; reached: boolean }) {
  const queryClient = useQueryClient();
  const subscriberId = getSubscriberId();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(favorite.target_price ? String(favorite.target_price) : "");

  const save = useMutation({
    mutationFn: (target: number | null) => api.updateFavorite(favorite.id, subscriberId!, target),
    onSuccess: () => {
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ["favorites"] });
    },
  });

  if (editing) {
    const parsed = Number(value.replace(/\D/g, ""));
    return (
      <form
        className="flex min-w-0 items-center gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate(parsed > 0 ? parsed : null);
        }}
      >
        <span className="text-xs text-muted">Avisarme bajo</span>
        <input
          autoFocus
          inputMode="numeric"
          className="w-24 rounded-lg border border-border bg-surface px-2 py-1 text-xs outline-none focus:border-accent"
          placeholder="$ precio"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <IconButton type="submit" title="Guardar" className="h-7 w-7" disabled={save.isPending}>
          <Check size={13} />
        </IconButton>
        <IconButton type="button" title="Cancelar" className="h-7 w-7" onClick={() => setEditing(false)}>
          <X size={13} />
        </IconButton>
      </form>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setEditing(true)}
      className={cn(
        "flex min-w-0 items-center gap-1.5 truncate text-xs font-medium hover:underline",
        reached ? "text-success" : favorite.target_price ? "text-accent" : "text-muted"
      )}
    >
      <BellRing size={13} className="shrink-0" />
      {favorite.target_price
        ? reached
          ? `¡Ya está bajo tu objetivo de ${formatCLP(favorite.target_price)}!`
          : `Aviso bajo ${formatCLP(favorite.target_price)}`
        : "Definir precio objetivo"}
    </button>
  );
}
