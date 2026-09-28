"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Send, ShieldCheck, Timer } from "lucide-react";
import { api, getSubscriberId } from "@/lib/api";
import { Button, Card } from "@/components/ui";

export default function TelegramPage() {
  const subscriberId = getSubscriberId();

  const subscribersQuery = useQuery({ queryKey: ["subscribers"], queryFn: api.listSubscribers });
  const me = subscribersQuery.data?.find((s) => s.id === subscriberId);

  const linkCode = useMutation({
    mutationFn: () => api.createTelegramLinkCode(subscriberId!),
  });

  return (
    <div className="mx-auto max-w-md">
      <div className="mb-6 text-center">
        <span className="mb-3 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-[#26A5E4] text-white shadow-md shadow-[#26A5E4]/30">
          <Send size={22} />
        </span>
        <h1 className="text-2xl font-bold tracking-tight">Notificaciones por Telegram</h1>
        <p className="mt-1 text-sm text-muted">
          Recibe un mensaje apenas un producto que sigues baje de precio.
        </p>
      </div>

      <Card className="p-5">
        {me?.telegram_linked ? (
          <div className="flex items-center gap-3 rounded-xl bg-success-bg px-4 py-3.5 text-success">
            <ShieldCheck size={20} className="shrink-0" />
            <p className="text-sm font-medium">Ya estás conectado a Telegram.</p>
          </div>
        ) : (
          <>
            <Button className="w-full" onClick={() => linkCode.mutate()} disabled={linkCode.isPending}>
              {linkCode.isPending ? <Loader2 size={16} className="animate-spin" /> : "Generar link de conexión"}
            </Button>

            {linkCode.data && (
              <div className="mt-4 flex flex-col items-center gap-2 rounded-xl border border-border bg-surface-hover p-4 text-center animate-fade-in-up">
                <a href={linkCode.data.deep_link} target="_blank" rel="noopener noreferrer">
                  <Button variant="secondary" size="sm">
                    <Send size={14} /> Abrir en Telegram
                  </Button>
                </a>
                <p className="flex items-center gap-1 text-xs text-muted">
                  <Timer size={12} /> Expira a las{" "}
                  {new Date(linkCode.data.expires_at).toLocaleTimeString("es-CL")}
                </p>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
