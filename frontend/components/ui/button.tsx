import { cn } from "@/lib/utils";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "success";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  children: React.ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-blue-500 hover:bg-blue-400 text-white font-semibold border-transparent",
  secondary:
    "bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border-zinc-700",
  ghost:
    "bg-transparent hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 border-transparent",
  danger:
    "bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border-rose-500/30",
  success:
    "bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-2.5 text-base",
};

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  className,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl border transition-all duration-150",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    >
      {loading && (
        <span className="animate-spin h-3.5 w-3.5 border-2 border-current border-t-transparent rounded-full" />
      )}
      {children}
    </button>
  );
}
