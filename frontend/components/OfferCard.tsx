"use client";

import { ExternalLink, Heart, Sparkles, Star, Trophy } from "lucide-react";
import Link from "next/link";
import { Listing } from "@/lib/api";
import { categoryStyle } from "@/lib/categories";
import { cn } from "@/lib/cn";
import { useFavorites } from "@/lib/favorites";
import { formatCLP } from "@/lib/format";
import { ProductThumb } from "@/components/ProductThumb";

/** Hotter colors for bigger discounts. */
export function DiscountBadge({ pct, className }: { pct: number; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-lg bg-gradient-to-br px-2 py-1 text-sm font-extrabold leading-none text-white shadow-md",
        pct >= 60 ? "from-rose-500 to-red-600" : pct >= 40 ? "from-orange-500 to-rose-500" : "from-violet-600 to-blue-600",
        className
      )}
    >
      -{pct.toFixed(0)}%
    </span>
  );
}

/** Offers the scraper first saw this recently get a "Nueva" badge. */
const NEW_FOR_MS = 60 * 60 * 1000;

function isNew(firstSeenAt: string | null): boolean {
  return firstSeenAt !== null && Date.now() - new Date(firstSeenAt).getTime() < NEW_FOR_MS;
}

/** "★ 4,6 (296)": the stores' own customer rating. */
export function Rating({ rating, reviews }: { rating: number; reviews: number | null }) {
  return (
    <p
      className="flex items-center gap-1 text-xs text-muted"
      title={reviews ? `${rating} de 5 según ${reviews.toLocaleString("es-CL")} opiniones` : `${rating} de 5`}
    >
      <Star size={13} className="fill-amber-400 text-amber-400" />
      <span className="font-semibold text-foreground">{rating.toLocaleString("es-CL", { minimumFractionDigits: 1 })}</span>
      {reviews ? <span>({reviews.toLocaleString("es-CL")})</span> : null}
    </p>
  );
}

export function savingsOf(price: number | null, original: number | null): number | null {
  return price !== null && original !== null && original > price ? original - price : null;
}

export function OfferCard({ listing, rank }: { listing: Listing; rank?: number }) {
  const favorites = useFavorites();
  const isFavorite = favorites.isFavorite(listing.product_id);
  const savings = savingsOf(listing.latest_price, listing.latest_original_price);
  const productHref = `/product?id=${listing.product_id}`;
  // Flights have no photo: show the category's icon instead of a letter.
  const placeholderIcon = listing.details ? categoryStyle(listing.category_slug ?? undefined).icon : undefined;

  return (
    <article className="group relative flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-surface transition-all duration-200 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-black/10">
      <Link href={productHref} className="relative block bg-white">
        <ProductThumb
          src={listing.image_url}
          seed={listing.title}
          label={listing.store.name}
          icon={placeholderIcon}
          className={cn(
            "aspect-[4/3] w-full transition-transform duration-300 group-hover:scale-105",
            // Product shots sit on white; destination photos fill the card.
            listing.details ? "object-cover" : "object-contain p-3"
          )}
        />
        {/* right-14 keeps the badges clear of the favorite button; they wrap on narrow cards. */}
        <div className="absolute left-2.5 right-14 top-2.5 flex flex-wrap items-center gap-1.5">
          {listing.latest_discount_pct ? <DiscountBadge pct={listing.latest_discount_pct} /> : null}
          {isNew(listing.first_seen_at) && (
            <span className="inline-flex items-center gap-1 rounded-lg bg-emerald-500 px-1.5 py-1 text-xs font-bold leading-none text-white shadow-md">
              <Sparkles size={12} /> Nueva
            </span>
          )}
          {rank === 1 && (
            <span className="inline-flex items-center gap-1 rounded-lg bg-amber-400 px-1.5 py-1 text-xs font-bold leading-none text-amber-950 shadow-md">
              <Trophy size={12} /> Top
            </span>
          )}
        </div>
      </Link>

      <button
        type="button"
        title={isFavorite ? "Quitar de favoritos" : "Agregar a favoritos"}
        onClick={() => favorites.toggle(listing.product_id)}
        disabled={favorites.isPending(listing.product_id)}
        className={cn(
          "absolute right-2.5 top-2.5 flex h-9 w-9 items-center justify-center rounded-full border shadow-sm backdrop-blur transition-all active:scale-90",
          isFavorite
            ? "border-rose-200 bg-rose-50 text-rose-500"
            : "border-zinc-200 bg-white/90 text-zinc-500 hover:text-rose-500"
        )}
      >
        <Heart size={16} fill={isFavorite ? "currentColor" : "none"} />
      </button>

      <div className="flex flex-1 flex-col gap-1.5 p-4">
        <p className="truncate text-[11px] font-semibold uppercase tracking-wide text-muted">{listing.store.name}</p>
        <Link href={productHref} className="line-clamp-2 text-sm font-medium leading-snug hover:text-accent">
          {listing.title}
        </Link>
        {listing.details && <p className="text-xs text-muted">{listing.details}</p>}
        {listing.rating ? <Rating rating={listing.rating} reviews={listing.review_count} /> : null}

        <div className="mt-auto pt-2">
          {listing.latest_original_price && (
            <p className="text-xs text-muted line-through">{formatCLP(listing.latest_original_price)}</p>
          )}
          <p className="text-xl font-extrabold tracking-tight">
            {listing.latest_price ? formatCLP(listing.latest_price) : "-"}
          </p>
          {savings && (
            <p className="mt-1 inline-flex rounded-md bg-success-bg px-1.5 py-0.5 text-xs font-semibold text-success">
              Ahorras {formatCLP(savings)}
            </p>
          )}
        </div>

        <a
          href={listing.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 flex items-center justify-center gap-1.5 rounded-xl border border-border py-2 text-xs font-semibold transition-colors hover:border-accent hover:bg-accent hover:text-accent-foreground"
        >
          Ir a la tienda <ExternalLink size={12} />
        </a>
      </div>
    </article>
  );
}

export function OfferCardSkeleton() {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface">
      <div className="skeleton aspect-[4/3] w-full" />
      <div className="space-y-2 p-4">
        <div className="skeleton h-3 w-16 rounded" />
        <div className="skeleton h-4 w-full rounded" />
        <div className="skeleton h-6 w-24 rounded" />
      </div>
    </div>
  );
}
