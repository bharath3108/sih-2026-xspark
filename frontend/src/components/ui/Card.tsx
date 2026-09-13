import type { ReactNode } from "react";
import { IconArrowDownRight, IconArrowUpRight } from "./Icons";

/* -------------------------------------------------------------------------- */
/* Card                                                                        */
/* -------------------------------------------------------------------------- */

export function Card({
  title,
  subtitle,
  eyebrow,
  actions,
  children,
  className = "",
  bodyClassName = "",
  interactive = false,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  eyebrow?: ReactNode;
  /** Right-aligned controls in the card header. */
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  interactive?: boolean;
}) {
  return (
    <section
      className={`surface-card relative flex flex-col rounded-card border border-line bg-surface shadow-card ${
        interactive ? "transition-colors duration-200 hover:border-line-strong hover:bg-surface-2/60" : ""
      } ${className}`}
    >
      {/* The header wraps on narrow viewports so wide actions (legends, filter
          chips) drop under the title instead of forcing the page to scroll. */}
      {(title || actions || eyebrow) && (
        <header className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2 px-5 pt-4 pb-3">
          <div className="min-w-0 flex-1">
            {eyebrow && (
              <p className="mb-1 text-[11px] font-semibold tracking-[0.08em] text-accent uppercase">{eyebrow}</p>
            )}
            {title && <h3 className="text-[15px] leading-6 font-semibold text-ink">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-[13px] leading-5 text-ink-3">{subtitle}</p>}
          </div>
          {actions && <div className="flex min-w-0 flex-wrap items-center gap-1.5">{actions}</div>}
        </header>
      )}
      <div className={`flex min-w-0 flex-1 flex-col px-5 pb-5 ${title || actions ? "" : "pt-5"} ${bodyClassName}`}>
        {children}
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* StatCard                                                                    */
/* -------------------------------------------------------------------------- */

export function StatCard({
  label,
  value,
  icon,
  delta,
  deltaLabel,
  footer,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  /** Signed change; sign drives the colour and arrow direction. */
  delta?: number;
  deltaLabel?: string;
  /** Small breakdown row pinned to the bottom edge. */
  footer?: ReactNode;
  tone?: "neutral" | "brand" | "accent" | "ok" | "warn" | "bad";
}) {
  const iconTone = {
    neutral: "text-ink-2 bg-surface-2",
    brand: "text-brand bg-brand-soft",
    accent: "text-accent bg-accent-soft",
    ok: "text-ok bg-ok-soft",
    warn: "text-warn bg-warn-soft",
    bad: "text-bad bg-bad-soft",
  }[tone];

  return (
    <section className="surface-card group relative flex flex-col rounded-card border border-line bg-surface p-4 shadow-card transition-colors duration-200 hover:border-line-strong">
      <div className="flex items-center gap-2.5">
        {icon && (
          <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${iconTone}`}>{icon}</span>
        )}
        <p className="truncate text-[13px] font-medium text-ink-2">{label}</p>
      </div>

      <div className="mt-3 flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
        <span className="tnum text-[30px] leading-none font-semibold text-ink">{value}</span>
        {delta !== undefined && <DeltaPill delta={delta} />}
        {deltaLabel && <span className="text-[11px] leading-tight text-ink-4">{deltaLabel}</span>}
      </div>

      {footer && <div className="mt-3.5 border-t border-line pt-2.5 text-[11px] text-ink-3">{footer}</div>}
    </section>
  );
}

export function DeltaPill({ delta, suffix = "%" }: { delta: number; suffix?: string }) {
  const up = delta >= 0;
  const Arrow = up ? IconArrowUpRight : IconArrowDownRight;
  return (
    <span className={`inline-flex items-center gap-0.5 text-[12px] font-semibold ${up ? "text-ok" : "text-bad"}`}>
      <Arrow className="h-3 w-3" />
      <span className="tnum">
        {up ? "+" : ""}
        {delta}
        {suffix}
      </span>
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Badge                                                                       */
/* -------------------------------------------------------------------------- */

type BadgeTone = "neutral" | "brand" | "accent" | "ok" | "warn" | "bad" | "info";

const BADGE_TONES: Record<BadgeTone, string> = {
  neutral: "bg-surface-2 text-ink-2 border-line-strong",
  brand: "bg-brand-soft text-brand border-brand/25",
  accent: "bg-accent-soft text-accent border-accent/25",
  ok: "bg-ok-soft text-ok border-ok/25",
  warn: "bg-warn-soft text-warn border-warn/25",
  bad: "bg-bad-soft text-bad border-bad/25",
  info: "bg-info-soft text-info border-info/25",
};

export function Badge({
  children,
  tone = "neutral",
  dot = false,
  className = "",
}: {
  children: ReactNode;
  tone?: BadgeTone;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap ${BADGE_TONES[tone]} ${className}`}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const tone: BadgeTone = confidence >= 0.75 ? "ok" : confidence >= 0.5 ? "warn" : "neutral";
  return (
    <Badge tone={tone} dot>
      <span className="tnum">{pct}%</span> confidence
    </Badge>
  );
}

/* -------------------------------------------------------------------------- */
/* Meter — labelled proportion bar used by sentiment / audience breakdowns      */
/* -------------------------------------------------------------------------- */

export function Meter({
  label,
  value,
  share,
  tone = "brand",
  capitalize = true,
}: {
  label: string;
  value: ReactNode;
  /** 0–1 */
  share: number;
  tone?: "brand" | "accent" | "ok" | "warn" | "bad" | "neutral" | "info";
  /** Off for labels that are already sentences or identifiers. */
  capitalize?: boolean;
}) {
  const bar = {
    brand: "bg-brand",
    accent: "bg-accent",
    ok: "bg-ok",
    warn: "bg-warn",
    bad: "bg-bad",
    info: "bg-info",
    neutral: "bg-ink-4",
  }[tone];

  const pct = Math.max(0, Math.min(1, share)) * 100;

  return (
    <div className="group/meter">
      <div className="flex items-baseline justify-between gap-3 text-[13px]">
        <span className={`truncate text-ink-2 ${capitalize ? "first-letter:uppercase" : ""}`}>{label}</span>
        <span className="tnum shrink-0 font-medium text-ink">{value}</span>
      </div>
      <div
        className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-3"
        role="img"
        aria-label={`${label}: ${Math.round(pct)}%`}
      >
        <div
          className={`h-full rounded-full ${bar} transition-[width] duration-500 ease-out`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
