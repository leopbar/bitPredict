import { cn } from "@/lib/utils";

type BadgeVariant = "emerald" | "coral" | "amber" | "cobalt" | "cyan" | "zinc" | "default";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: React.ReactNode;
}

const variantClasses: Record<BadgeVariant, string> = {
  emerald: "bg-emerald-400/10 text-emerald-400 border border-emerald-400/20",
  coral: "bg-rose-400/10 text-rose-400 border border-rose-400/20",
  amber: "bg-amber-400/10 text-amber-400 border border-amber-400/20",
  cobalt: "bg-blue-400/10 text-blue-400 border border-blue-400/20",
  cyan: "bg-cyan-400/10 text-cyan-400 border border-cyan-400/20",
  zinc: "bg-zinc-700/50 text-zinc-300 border border-zinc-700",
  default: "bg-zinc-800 text-zinc-300 border border-zinc-700",
};

export function Badge({ variant = "default", className, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
        variantClasses[variant],
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
