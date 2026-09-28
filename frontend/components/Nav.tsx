"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Ofertas" },
  { href: "/favorites", label: "Favoritos" },
  { href: "/telegram", label: "Telegram" },
];

export default function Nav() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-4 border-b px-4 py-3">
      {LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className={pathname === link.href ? "font-semibold underline" : "text-gray-600"}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
