"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { LogOut, Send, ShoppingBag, Sparkles, Star, UserRound } from "lucide-react";
import { clearCredentials, clearSubscriber, getSubscriberName } from "@/lib/api";
import { Avatar } from "@/components/ui";

const LINKS = [
  { href: "/", label: "Ofertas", icon: ShoppingBag },
  { href: "/favorites", label: "Favoritos", icon: Star },
  { href: "/telegram", label: "Telegram", icon: Send },
];

export default function Header() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const [subscriberName, setSubscriberName] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSubscriberName(getSubscriberName());
  }, [pathname]);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-bg/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-4 px-4">
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <span className="brand-gradient flex h-8 w-8 items-center justify-center rounded-lg text-accent-foreground shadow-sm shadow-accent/30">
            <Sparkles size={17} strokeWidth={2.25} />
          </span>
          <span className="hidden text-[15px] font-bold tracking-tight sm:inline">Cyber Ofertas</span>
        </Link>

        <nav className="flex items-center gap-1 rounded-full border border-border bg-surface p-1">
          {LINKS.map((link) => {
            const active = pathname === link.href;
            const Icon = link.icon;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={
                  "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-all duration-150 " +
                  (active
                    ? "brand-gradient text-accent-foreground shadow-sm"
                    : "text-muted hover:bg-surface-hover hover:text-foreground")
                }
              >
                <Icon size={15} strokeWidth={2.25} />
                <span className="hidden sm:inline">{link.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="relative shrink-0" ref={menuRef}>
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-2 rounded-full border border-border bg-surface py-1 pl-1 pr-1 hover:bg-surface-hover sm:pr-3"
          >
            <Avatar name={subscriberName ?? "?"} className="h-7 w-7 text-xs" />
            <span className="hidden text-sm font-medium sm:inline">{subscriberName}</span>
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-full mt-2 w-48 animate-fade-in-up overflow-hidden rounded-xl border border-border bg-surface shadow-lg shadow-black/5">
              <button
                onClick={() => {
                  clearSubscriber();
                  window.location.reload();
                }}
                className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-sm text-foreground hover:bg-surface-hover"
              >
                <UserRound size={15} /> Cambiar de usuario
              </button>
              <button
                onClick={() => {
                  clearCredentials();
                  window.location.reload();
                }}
                className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-sm text-danger hover:bg-danger-bg"
              >
                <LogOut size={15} /> Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
