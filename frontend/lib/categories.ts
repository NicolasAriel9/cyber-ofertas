import {
  Baby,
  BedDouble,
  Bike,
  BookOpen,
  CarFront,
  Coffee,
  Gamepad2,
  Glasses,
  Hammer,
  HardHat,
  House,
  Laptop,
  LucideIcon,
  Luggage,
  Moon,
  Music,
  PawPrint,
  Plane,
  Shirt,
  ShoppingBag,
  Sofa,
  Sparkles,
  Tag,
  TreePalm,
} from "lucide-react";

interface CategoryStyle {
  icon: LucideIcon;
  /** Tailwind gradient stops for the category's icon chip. */
  gradient: string;
}

// Keyed by cyber.cl's category slugs.
const STYLES: Record<string, CategoryStyle> = {
  tecnologia: { icon: Laptop, gradient: "from-blue-500 to-indigo-600" },
  hogar: { icon: House, gradient: "from-amber-500 to-orange-600" },
  "vestuario-y-calzado": { icon: Shirt, gradient: "from-pink-500 to-rose-600" },
  "salud-y-belleza": { icon: Sparkles, gradient: "from-fuchsia-500 to-purple-600" },
  "ferreteria-y-construccion": { icon: Hammer, gradient: "from-yellow-500 to-amber-600" },
  infantil: { icon: Baby, gradient: "from-sky-400 to-cyan-500" },
  muebles: { icon: Sofa, gradient: "from-orange-400 to-red-500" },
  "deportes-y-outdoor": { icon: Bike, gradient: "from-emerald-500 to-green-600" },
  mascotas: { icon: PawPrint, gradient: "from-lime-500 to-emerald-600" },
  "multitiendas-y-supermercados": { icon: ShoppingBag, gradient: "from-violet-500 to-indigo-600" },
  "accesorios-moda": { icon: Glasses, gradient: "from-rose-400 to-pink-600" },
  "neumaticos-y-accesorios": { icon: CarFront, gradient: "from-slate-500 to-zinc-700" },
  "alimentos-y-bebidas": { icon: Coffee, gradient: "from-amber-600 to-yellow-700" },
  "educacion-y-cultura": { icon: BookOpen, gradient: "from-teal-500 to-cyan-600" },
  entretencion: { icon: Gamepad2, gradient: "from-purple-500 to-blue-600" },
  "musica-y-audio": { icon: Music, gradient: "from-indigo-500 to-violet-600" },
  "vestuario-industrial": { icon: HardHat, gradient: "from-orange-500 to-amber-600" },
  "ropa-interior-y-pijamas": { icon: Moon, gradient: "from-indigo-400 to-purple-500" },
  "equipaje-bolsos-y-maletas": { icon: Luggage, gradient: "from-cyan-500 to-blue-600" },
  // Cyber Viajes (created by the travel scrapers, not cyber.cl).
  vuelos: { icon: Plane, gradient: "from-sky-500 to-blue-600" },
  paquetes: { icon: TreePalm, gradient: "from-teal-400 to-cyan-600" },
  alojamientos: { icon: BedDouble, gradient: "from-indigo-400 to-violet-600" },
};

const FALLBACK: CategoryStyle = { icon: Tag, gradient: "from-violet-500 to-blue-500" };

export function categoryStyle(slug: string | undefined): CategoryStyle {
  return (slug && STYLES[slug]) || FALLBACK;
}
