"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { api, getSubscriberId } from "@/lib/api";

export default function TelegramPage() {
  const subscriberId = getSubscriberId();

  const subscribersQuery = useQuery({ queryKey: ["subscribers"], queryFn: api.listSubscribers });
  const me = subscribersQuery.data?.find((s) => s.id === subscriberId);

  const linkCode = useMutation({
    mutationFn: () => api.createTelegramLinkCode(subscriberId!),
  });

  return (
    <div className="mx-auto max-w-md">
      <h1 className="mb-4 text-2xl font-bold">Notificaciones por Telegram</h1>

      {me?.telegram_linked ? (
        <p className="rounded border border-green-300 bg-green-50 p-3 text-green-800">
          ✅ Ya estás conectado a Telegram.
        </p>
      ) : (
        <>
          <p className="mb-4 text-gray-600">
            Conecta tu Telegram para recibir avisos cuando un producto que sigues baje de precio.
          </p>
          <button
            className="rounded bg-black px-4 py-2 text-white"
            onClick={() => linkCode.mutate()}
            disabled={linkCode.isPending}
          >
            Generar link de conexión
          </button>
          {linkCode.data && (
            <div className="mt-4 rounded border p-4">
              <a
                href={linkCode.data.deep_link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 underline"
              >
                Abrir en Telegram
              </a>
              <p className="mt-2 text-xs text-gray-500">
                Expira a las {new Date(linkCode.data.expires_at).toLocaleTimeString("es-CL")}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
