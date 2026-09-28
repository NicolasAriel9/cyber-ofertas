const AUTH_KEY = "cyber-ofertas-auth";
const SUBSCRIBER_KEY = "cyber-ofertas-subscriber-id";
const SUBSCRIBER_NAME_KEY = "cyber-ofertas-subscriber-name";

export interface Credentials {
  apiBase: string;
  username: string;
  password: string;
}

export function getCredentials(): Credentials | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(AUTH_KEY);
  return raw ? (JSON.parse(raw) as Credentials) : null;
}

export function setCredentials(creds: Credentials) {
  window.localStorage.setItem(AUTH_KEY, JSON.stringify(creds));
}

export function clearCredentials() {
  window.localStorage.removeItem(AUTH_KEY);
}

export function getSubscriberId(): number | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(SUBSCRIBER_KEY);
  return raw ? Number(raw) : null;
}

export function getSubscriberName(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(SUBSCRIBER_NAME_KEY);
}

export function setSubscriber(id: number, name: string) {
  window.localStorage.setItem(SUBSCRIBER_KEY, String(id));
  window.localStorage.setItem(SUBSCRIBER_NAME_KEY, name);
}

export function clearSubscriber() {
  window.localStorage.removeItem(SUBSCRIBER_KEY);
  window.localStorage.removeItem(SUBSCRIBER_NAME_KEY);
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const creds = getCredentials();
  if (!creds) throw new ApiError(401, "No credentials configured");

  const headers = new Headers(options.headers);
  headers.set("Authorization", "Basic " + btoa(`${creds.username}:${creds.password}`));
  if (options.body) headers.set("Content-Type", "application/json");

  const res = await fetch(`${creds.apiBase}${path}`, { ...options, headers });
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface Store {
  id: number;
  name: string;
  slug: string;
  logo_url: string | null;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
}

export interface Listing {
  id: number;
  product_id: number;
  store: Store;
  title: string;
  url: string;
  image_url: string | null;
  latest_price: number | null;
  latest_original_price: number | null;
  latest_discount_pct: number | null;
}

export interface Product {
  id: number;
  canonical_title: string;
  category: Category | null;
  brand: string | null;
  image_url: string | null;
  listings: Listing[];
}

export interface ProductSummary {
  id: number;
  canonical_title: string;
  image_url: string | null;
  best_price: number | null;
  best_store: string | null;
  max_discount_pct: number | null;
}

export interface Favorite {
  id: number;
  product: ProductSummary;
  target_price: number | null;
}

export interface Subscriber {
  id: number;
  name: string;
  telegram_linked: boolean;
}

export interface PriceHistoryPoint {
  scraped_at: string;
  price: number;
  store_slug: string;
}

export interface TelegramLinkCode {
  code: string;
  deep_link: string;
  expires_at: string;
}

export interface ListingFilters {
  category?: string;
  store?: string;
  search?: string;
  min_discount?: number;
  sort?: "discount" | "price_asc" | "price_desc" | "recent";
  page?: number;
}

function toQuery(params: object): string {
  const parts = Object.entries(params as Record<string, unknown>)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

export const api = {
  listStores: () => request<Store[]>("/stores"),
  listCategories: () => request<Category[]>("/categories"),
  listSubscribers: () => request<Subscriber[]>("/subscribers"),
  listListings: (filters: ListingFilters) => request<Listing[]>(`/listings${toQuery(filters)}`),
  getProduct: (id: number) => request<Product>(`/products/${id}`),
  getPriceHistory: (id: number, days = 30) =>
    request<PriceHistoryPoint[]>(`/products/${id}/price-history${toQuery({ days })}`),
  listFavorites: (subscriberId: number) =>
    request<Favorite[]>(`/favorites${toQuery({ subscriber_id: subscriberId })}`),
  addFavorite: (subscriberId: number, productId: number, targetPrice?: number) =>
    request<Favorite>(`/favorites${toQuery({ subscriber_id: subscriberId })}`, {
      method: "POST",
      body: JSON.stringify({ product_id: productId, target_price: targetPrice ?? null }),
    }),
  removeFavorite: (favoriteId: number, subscriberId: number) =>
    request<void>(`/favorites/${favoriteId}${toQuery({ subscriber_id: subscriberId })}`, {
      method: "DELETE",
    }),
  createTelegramLinkCode: (subscriberId: number) =>
    request<TelegramLinkCode>(`/subscribers/${subscriberId}/telegram-link-code`, { method: "POST" }),
};

export { ApiError };
