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

function basicAuth(creds: Credentials) {
  return "Basic " + btoa(`${creds.username}:${creds.password}`);
}

/** Tries the credentials before saving them, so the login form can tell a
 * wrong user/password apart from a server it can't reach. */
export async function checkCredentials(creds: Credentials): Promise<"ok" | "wrong" | "offline"> {
  try {
    const res = await fetch(`${creds.apiBase}/subscribers`, { headers: { Authorization: basicAuth(creds) } });
    if (res.ok) return "ok";
    return res.status === 401 ? "wrong" : "offline";
  } catch {
    return "offline";
  }
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

async function rawRequest(path: string, options: RequestInit = {}): Promise<Response> {
  const creds = getCredentials();
  if (!creds) throw new ApiError(401, "No credentials configured");

  const headers = new Headers(options.headers);
  headers.set("Authorization", basicAuth(creds));
  if (options.body) headers.set("Content-Type", "application/json");

  const res = await fetch(`${creds.apiBase}${path}`, { ...options, headers });
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  return res;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await rawRequest(path, options);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface ListingsPage {
  items: Listing[];
  total: number;
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
  /** Travel offers: dates, nights, what the price covers. */
  details: string | null;
  category_slug: string | null;
  /** Shoppers' rating out of 5; review_count is null when the store doesn't say. */
  rating: number | null;
  review_count: number | null;
  first_seen_at: string | null;
  /** How much the price fell since the Cyber began (%), when it did. */
  cyber_drop_pct: number | null;
}

/** Retail offers ("/") or travel deals ("/viajes"). */
export type Section = "productos" | "viajes";

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
  brand: string | null;
  category: Category | null;
  best_price: number | null;
  best_original_price: number | null;
  best_discount_pct: number | null;
  best_store: string | null;
  best_url: string | null;
  max_discount_pct: number | null;
  store_count: number;
  lowest_price: number | null;
}

export interface Favorite {
  id: number;
  product: ProductSummary;
  target_price: number | null;
  created_at: string | null;
  price_when_added: number | null;
}

export interface CategoryHighlights {
  category: Category;
  total: number;
  listings: Listing[];
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
  section?: Section;
  category?: string;
  store?: string;
  search?: string;
  min_discount?: number;
  /** Only offers that got cheaper, or appeared, since the Cyber began. */
  cyber?: boolean;
  /** Stars out of 5; only ratings backed by a few reviews count. */
  min_rating?: number;
  min_price?: number;
  max_price?: number;
  sort?: "top" | "discount" | "savings" | "price_asc" | "price_desc" | "recent" | "rating";
  page?: number;
}

function toQuery(params: object): string {
  const parts = Object.entries(params as Record<string, unknown>)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

export const api = {
  listStores: (section?: Section) => request<Store[]>(`/stores${toQuery({ section })}`),
  listCategories: (section?: Section) => request<Category[]>(`/categories${toQuery({ section })}`),
  listSubscribers: () => request<Subscriber[]>("/subscribers"),
  listListings: async (filters: ListingFilters): Promise<ListingsPage> => {
    const res = await rawRequest(`/listings${toQuery(filters)}`);
    const items = (await res.json()) as Listing[];
    return { items, total: Number(res.headers.get("X-Total-Count") ?? items.length) };
  },
  listHighlights: (section: Section) => request<CategoryHighlights[]>(`/highlights${toQuery({ section })}`),
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
  updateFavorite: (favoriteId: number, subscriberId: number, targetPrice: number | null) =>
    request<Favorite>(`/favorites/${favoriteId}${toQuery({ subscriber_id: subscriberId })}`, {
      method: "PATCH",
      body: JSON.stringify({ target_price: targetPrice }),
    }),
  removeFavorite: (favoriteId: number, subscriberId: number) =>
    request<void>(`/favorites/${favoriteId}${toQuery({ subscriber_id: subscriberId })}`, {
      method: "DELETE",
    }),
  createTelegramLinkCode: (subscriberId: number) =>
    request<TelegramLinkCode>(`/subscribers/${subscriberId}/telegram-link-code`, { method: "POST" }),
};

export { ApiError };
