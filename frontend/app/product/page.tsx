"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, Check, ExternalLink, TrendingDown } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, getSubscriberId } from "@/lib/api";
import { formatCLP } from "@/lib/format";
import { Badge, Button, Card, EmptyState, Input, Skeleton } from "@/components/ui";
import { ProductThumb } from "@/components/ProductThumb";

export default function ProductPage() {
  return (
    <Suspense fallback={<ProductSkeleton />}>
      <ProductDetail />
    </Suspense>
  );
}

function ProductSkeleton() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Skeleton className="h-8 w-2/3" />
      <Skeleton className="h-48 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
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

  if (!Number.isFinite(id) || id <= 0) {
    return <EmptyState icon={<TrendingDown size={20} />} title="Producto inválido" />;
  }
  if (productQuery.isLoading) return <ProductSkeleton />;
  if (productQuery.isError || !productQuery.data) {
    return <EmptyState icon={<TrendingDown size={20} />} title="No se encontró el producto" />;
  }

  const product = productQuery.data;
  const sortedListings = [...product.listings].sort(
    (a, b) => (a.latest_price ?? Infinity) - (b.latest_price ?? Infinity)
  );
  const best = sortedListings[0];

  const chartData = (historyQuery.data ?? []).map((p) => ({
    date: new Date(p.scraped_at).toLocaleDateString("es-CL", { day: "2-digit", month: "short" }),
    price: p.price,
  }));

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6 flex items-start gap-4">
        <ProductThumb
          src={product.image_url}
          seed={product.canonical_title}
          label={product.brand ?? product.category?.name}
          className="h-20 w-20 shrink-0 rounded-2xl"
        />
        <div className="min-w-0">
          <h1 className="text-xl font-bold tracking-tight sm:text-2xl">{product.canonical_title}</h1>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {product.category && <Badge>{product.category.name}</Badge>}
            {product.brand && <Badge>{product.brand}</Badge>}
          </div>
        </div>
      </div>

      {best?.latest_price && (
        <Card className="brand-gradient mb-4 flex items-center justify-between gap-4 p-5 text-accent-foreground">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide opacity-80">Mejor precio · {best.store.name}</p>
            <p className="text-3xl font-bold">{formatCLP(best.latest_price)}</p>
          </div>
          <a
            href={best.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex shrink-0 items-center gap-1.5 rounded-xl bg-white/15 px-4 py-2.5 text-sm font-semibold backdrop-blur-sm transition-colors hover:bg-white/25"
          >
            Comprar <ExternalLink size={14} />
          </a>
        </Card>
      )}

      <h2 className="mb-2 mt-6 text-sm font-semibold text-muted">Comparar precios</h2>
      <div className="mb-6 flex flex-col gap-2">
        {sortedListings.map((listing, i) => (
          <a
            key={listing.id}
            href={listing.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between rounded-xl border border-border bg-surface p-3.5 transition-colors hover:bg-surface-hover"
          >
            <div className="flex items-center gap-2">
              <span className="font-medium">{listing.store.name}</span>
              {i === 0 && <Badge variant="success">Mejor precio</Badge>}
            </div>
            <div className="flex items-center gap-2">
              <span className="font-bold">{listing.latest_price ? formatCLP(listing.latest_price) : "-"}</span>
              <ExternalLink size={13} className="text-muted" />
            </div>
          </a>
        ))}
      </div>

      {chartData.length > 1 && (
        <>
          <h2 className="mb-2 text-sm font-semibold text-muted">Historial de precio</h2>
          <Card className="mb-6 h-56 p-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                <defs>
                  <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: "var(--muted)" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fontSize: 11, fill: "var(--muted)" }}
                  axisLine={false}
                  tickLine={false}
                  width={56}
                  tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                />
                <Tooltip
                  formatter={(value) => formatCLP(Number(value))}
                  contentStyle={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    fontSize: 13,
                  }}
                />
                <Area type="monotone" dataKey="price" stroke="#8b5cf6" strokeWidth={2.5} fill="url(#priceGradient)" />
              </AreaChart>
            </ResponsiveContainer>
          </Card>
        </>
      )}

      <h2 className="mb-2 text-sm font-semibold text-muted">Avisarme cuando baje de precio</h2>
      <Card className="p-4">
        <form
          className="flex flex-col gap-3 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            addFavorite.mutate();
          }}
        >
          <div className="relative flex-1">
            <BellRing size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <Input
              className="pl-9"
              placeholder="Precio objetivo (opcional)"
              value={targetPrice}
              onChange={(e) => setTargetPrice(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={addFavorite.isPending}>
            {addFavorite.isSuccess ? (
              <>
                <Check size={15} /> Agregado
              </>
            ) : (
              "Seguir producto"
            )}
          </Button>
        </form>
      </Card>
    </div>
  );
}
