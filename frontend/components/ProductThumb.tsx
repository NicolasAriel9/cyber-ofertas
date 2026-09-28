import { ImageOff } from "lucide-react";
import { cn } from "@/lib/cn";

const PALETTES = [
  "from-violet-500 to-blue-500",
  "from-fuchsia-500 to-orange-400",
  "from-emerald-500 to-cyan-500",
  "from-amber-500 to-rose-500",
  "from-blue-500 to-indigo-600",
];

function paletteFor(seed: string) {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  return PALETTES[hash % PALETTES.length];
}

export function ProductThumb({
  src,
  seed,
  label,
  className,
}: {
  src?: string | null;
  seed: string;
  label?: string;
  className?: string;
}) {
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={label ?? ""} className={cn("object-cover", className)} />;
  }

  return (
    <div
      className={cn(
        "flex items-center justify-center bg-gradient-to-br text-white/90",
        paletteFor(seed),
        className
      )}
    >
      {label ? (
        <span className="text-lg font-bold tracking-tight">{label.charAt(0).toUpperCase()}</span>
      ) : (
        <ImageOff size={18} strokeWidth={1.5} />
      )}
    </div>
  );
}
