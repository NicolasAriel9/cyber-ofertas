"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export default function Providers({ children }: { children: React.ReactNode }) {
  // Coming back from a product page should reuse what's on screen instead of
  // refetching every loaded page at once; the offer lists poll on their own (OffersBrowser).
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 60 * 1000 } } }));
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
