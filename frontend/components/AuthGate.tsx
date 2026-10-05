"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Loader2, Sparkles, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import {
  api,
  checkCredentials,
  getCredentials,
  getSubscriberId,
  setCredentials,
  setSubscriber,
} from "@/lib/api";
import { Avatar, Button, Input } from "@/components/ui";

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
      <AuthShell title="¿Quién eres?" subtitle="Elige tu perfil para continuar">
        <div className="flex flex-col gap-2.5">
          {subscribersQuery.data.map((s) => (
            <button
              key={s.id}
              className="group flex items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3.5 text-left transition-all duration-150 hover:border-accent/40 hover:bg-surface-hover"
              onClick={() => {
                setSubscriber(s.id, s.name);
                setSubscriberIdState(s.id);
              }}
            >
              <Avatar name={s.name} className="h-9 w-9" />
              <span className="font-medium">{s.name}</span>
              <ArrowRight
                size={16}
                className="ml-auto text-muted opacity-0 transition-opacity group-hover:opacity-100"
              />
            </button>
          ))}
        </div>
      </AuthShell>
    );
  }

  return children;
}

function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-bg px-4">
      <div className="w-full max-w-sm animate-fade-in-up">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="brand-gradient mb-3 flex h-11 w-11 items-center justify-center rounded-xl text-accent-foreground shadow-md shadow-accent/25">
            <Sparkles size={20} />
          </span>
          <h1 className="text-lg font-bold tracking-tight">{title}</h1>
          <p className="mt-0.5 text-sm text-muted">{subtitle}</p>
        </div>
        {children}
      </div>
    </div>
  );
}

function LoginForm({ onDone, error }: { onDone: () => void; error?: string }) {
  const [apiBase, setApiBase] = useState(process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(error);

  return (
    <AuthShell title="Cyber Ofertas" subtitle="Conecta con tu backend para continuar">
      {formError && (
        <div className="mb-4 flex items-start gap-2 rounded-xl bg-danger-bg px-3.5 py-2.5 text-sm text-danger">
          <TriangleAlert size={16} className="mt-0.5 shrink-0" />
          <span>{formError}</span>
        </div>
      )}
      <form
        className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-5"
        onSubmit={async (e) => {
          e.preventDefault();
          setSubmitting(true);
          setFormError(undefined);
          // Phone keyboards capitalize the first letter and autocomplete can
          // add a trailing space; neither should make the login fail.
          const creds = { apiBase: apiBase.trim().replace(/\/$/, ""), username: username.trim(), password: password.trim() };
          const result = await checkCredentials(creds);
          setSubmitting(false);
          if (result === "ok") {
            setCredentials(creds);
            onDone();
          } else if (result === "wrong") {
            setFormError("Usuario o contraseña incorrectos.");
          } else {
            setFormError("No se pudo conectar con el servidor. Revisa la URL del backend o intenta de nuevo en un minuto.");
          }
        }}
      >
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-muted">URL del backend</span>
          <Input
            value={apiBase}
            onChange={(e) => setApiBase(e.target.value)}
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-muted">Usuario</span>
          <Input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-muted">Contraseña</span>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        <Button type="submit" className="mt-1.5 w-full" disabled={submitting}>
          {submitting ? <Loader2 size={16} className="animate-spin" /> : "Entrar"}
        </Button>
      </form>
    </AuthShell>
  );
}
