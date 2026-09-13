import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "destructive";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-brand text-white shadow-[0_1px_0_#ffffff26_inset,0_6px_16px_-8px_#7c5cffcc] hover:bg-brand-hi active:bg-brand-lo",
  secondary:
    "bg-surface-2 text-ink border border-line-strong hover:bg-surface-3 hover:border-line-strong active:bg-surface-2",
  outline:
    "bg-transparent text-ink-2 border border-line-strong hover:text-ink hover:border-brand/60 hover:bg-brand-soft",
  ghost: "bg-transparent text-ink-2 hover:bg-surface-2 hover:text-ink",
  destructive: "bg-bad text-white hover:brightness-110 active:brightness-95",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5 rounded-lg",
  md: "h-9 px-3.5 text-sm gap-2 rounded-lg",
  lg: "h-10 px-4 text-sm gap-2 rounded-[10px]",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  /** Leading icon; hidden from AT since the label carries the meaning. */
  icon?: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  className = "",
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex shrink-0 items-center justify-center font-medium whitespace-nowrap transition-[background-color,border-color,color,filter,opacity] duration-150 disabled:pointer-events-none disabled:opacity-45 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {loading ? (
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-[1.5px] border-current/30 border-t-current" />
      ) : (
        icon
      )}
      {children}
    </button>
  );
}

/** Square, label-less affordance. `label` is required — it becomes the a11y name. */
export function IconButton({
  label,
  variant = "ghost",
  size = "md",
  className = "",
  children,
  ...props
}: Omit<ButtonProps, "icon" | "loading"> & { label: string }) {
  const box = size === "sm" ? "h-7 w-7 rounded-md" : size === "lg" ? "h-10 w-10 rounded-[10px]" : "h-8 w-8 rounded-lg";
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`inline-flex shrink-0 items-center justify-center transition-colors duration-150 disabled:pointer-events-none disabled:opacity-45 ${VARIANTS[variant]} ${box} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
