import { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Button({
  className,
  variant = "primary",
  size = "md",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-xl font-medium transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.98]",
        size === "sm" ? "px-3 py-1.5 text-sm" : "px-4 py-2.5 text-sm",
        variant === "primary" &&
          "brand-gradient text-accent-foreground shadow-sm shadow-accent/20 hover:brightness-110",
        variant === "secondary" &&
          "border border-border bg-surface text-foreground hover:bg-surface-hover",
        variant === "ghost" && "text-muted hover:bg-surface-hover hover:text-foreground",
        variant === "danger" && "text-danger hover:bg-danger-bg",
        className
      )}
      {...props}
    />
  );
}

export function IconButton({
  className,
  active,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      className={cn(
        "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border bg-surface transition-all duration-150 hover:bg-surface-hover active:scale-90",
        active && "border-accent/40 bg-accent/10 text-accent",
        className
      )}
      {...props}
    />
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-border bg-surface transition-colors duration-150",
        className
      )}
    >
      {children}
    </div>
  );
}

export function Badge({
  className,
  variant = "neutral",
  children,
}: {
  className?: string;
  variant?: "neutral" | "success" | "accent" | "danger";
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold",
        variant === "neutral" && "bg-surface-hover text-muted",
        variant === "success" && "bg-success-bg text-success",
        variant === "accent" && "brand-gradient text-accent-foreground",
        variant === "danger" && "bg-danger-bg text-danger",
        className
      )}
    >
      {children}
    </span>
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "w-full rounded-xl border border-border bg-surface px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted",
        "outline-none transition-shadow duration-150 focus:border-accent focus:ring-4 focus:ring-accent/15",
        className
      )}
      {...props}
    />
  );
}

export function Select({
  className,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "appearance-none rounded-xl border border-border bg-surface px-3.5 py-2.5 text-sm text-foreground",
        "outline-none transition-shadow duration-150 focus:border-accent focus:ring-4 focus:ring-accent/15",
        className
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-xl", className)} />;
}

export function Avatar({ name, className }: { name: string; className?: string }) {
  const initial = name.trim().charAt(0).toUpperCase();
  return (
    <div
      className={cn(
        "brand-gradient inline-flex shrink-0 items-center justify-center rounded-full text-sm font-semibold text-accent-foreground",
        className
      )}
    >
      {initial}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
}: {
  icon: ReactNode;
  title: string;
  description?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border px-6 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-surface-hover text-muted">
        {icon}
      </div>
      <p className="font-medium text-foreground">{title}</p>
      {description && <p className="max-w-xs text-sm text-muted">{description}</p>}
    </div>
  );
}
