"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  api,
  clearCredentials,
  getCredentials,
  getSubscriberId,
  setCredentials,
  setSubscriberId,
} from "@/lib/api";

export default function AuthGate({ children }: { children: React.ReactNode }) {
  // Credentials/subscriber live in localStorage, which isn't available during
  // server rendering -- start both null so the server and the client's first
  // render match, then read the real values after mount (avoids a hydration
  // mismatch between "no creds yet" and "creds found").
  const [mounted, setMounted] = useState(false);
  const [hasCreds, setHasCreds] = useState(false);
  const [subscriberId, setSubscriberIdState] = useState<number | null>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    setHasCreds(getCredentials() !== null);
    setSubscriberIdState(getSubscriberId());
    setMounted(true);
  }, []);

  const onCredsSubmitted = () => {
    setHasCreds(true);
    queryClient.invalidateQueries({ queryKey: ["subscribers"] });
  };

  const subscribersQuery = useQuery({
    queryKey: ["subscribers"],
    queryFn: api.listSubscribers,
    enabled: hasCreds,
    retry: false,
  });

  if (!mounted) {
    return null;
  }

  if (!hasCreds) {
    return <LoginForm onDone={onCredsSubmitted} />;
  }

  if (subscribersQuery.isError) {
    return (
      <LoginForm
        error="No se pudo conectar con el servidor. Revisa la URL y credenciales."
        onDone={onCredsSubmitted}
      />
    );
  }

  if (!subscriberId && subscribersQuery.data) {
    return (
      <div className="mx-auto max-w-sm p-6">
        <h1 className="mb-4 text-lg font-semibold">¿Quién eres?</h1>
        <div className="flex flex-col gap-2">
          {subscribersQuery.data.map((s) => (
            <button
              key={s.id}
              className="rounded border px-4 py-2 text-left hover:bg-gray-50"
              onClick={() => {
                setSubscriberId(s.id);
                setSubscriberIdState(s.id);
              }}
            >
              {s.name}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <>
      {children}
      <button
        className="fixed bottom-4 right-4 rounded-full border bg-white px-3 py-1 text-xs text-gray-500 shadow"
        onClick={() => {
          clearCredentials();
          setHasCreds(false);
        }}
      >
        Cerrar sesión
      </button>
    </>
  );
}

function LoginForm({ onDone, error }: { onDone: () => void; error?: string }) {
  const [apiBase, setApiBase] = useState("http://127.0.0.1:8000");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  return (
    <div className="mx-auto max-w-sm p-6">
      <h1 className="mb-4 text-lg font-semibold">Conectar a Cyber Ofertas</h1>
      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setCredentials({ apiBase: apiBase.replace(/\/$/, ""), username, password });
          onDone();
        }}
      >
        <input
          className="rounded border px-3 py-2"
          placeholder="URL del backend"
          value={apiBase}
          onChange={(e) => setApiBase(e.target.value)}
        />
        <input
          className="rounded border px-3 py-2"
          placeholder="Usuario"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          className="rounded border px-3 py-2"
          type="password"
          placeholder="Contraseña"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button className="rounded bg-black px-4 py-2 text-white" type="submit">
          Entrar
        </button>
      </form>
    </div>
  );
}
