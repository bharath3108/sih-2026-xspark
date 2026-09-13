import type { ReactNode } from "react";
import { Button } from "./Button";
import { IconAlert, IconInbox, IconRefresh } from "./Icons";

/* -------------------------------------------------------------------------- */
/* Skeletons                                                                   */
/* -------------------------------------------------------------------------- */

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton rounded-md ${className}`} />;
}

function SkeletonCard({ className = "", children }: { className?: string; children?: ReactNode }) {
  return <div className={`rounded-card border border-line bg-surface ${className}`}>{children}</div>;
}

/**
 * Page-level loading. Renders the shape of the page being loaded rather than a
 * spinner, so the layout doesn't jump when data lands.
 */
export function LoadingState({ label = "Loading…", variant = "dashboard" }: { label?: string; variant?: "dashboard" | "list" | "chart" }) {
  return (
    <div className="animate-fade-rise space-y-5" role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">{label}</span>

      <div className="space-y-2">
        <Skeleton className="h-7 w-56" />
        <Skeleton className="h-4 w-80" />
      </div>

      {variant === "dashboard" && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <SkeletonCard key={i} className="p-4">
                <div className="flex items-center gap-2.5">
                  <Skeleton className="h-7 w-7 rounded-lg" />
                  <Skeleton className="h-3.5 w-24" />
                </div>
                <Skeleton className="mt-4 h-8 w-20" />
                <Skeleton className="mt-4 h-3 w-full" />
              </SkeletonCard>
            ))}
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {[0, 1].map((i) => (
              <SkeletonCard key={i} className="p-5">
                <Skeleton className="h-4 w-32" />
                <div className="mt-5 space-y-3.5">
                  {[0, 1, 2, 3].map((j) => (
                    <div key={j}>
                      <Skeleton className="h-3 w-full" />
                      <Skeleton className="mt-2 h-1.5 w-full" />
                    </div>
                  ))}
                </div>
              </SkeletonCard>
            ))}
          </div>
        </>
      )}

      {variant === "chart" && (
        <div className="space-y-4">
          {[0, 1].map((i) => (
            <SkeletonCard key={i} className="p-5">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="mt-5 h-72 w-full rounded-lg" />
            </SkeletonCard>
          ))}
        </div>
      )}

      {variant === "list" && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <SkeletonCard key={i} className="p-5">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="mt-2 h-3 w-24" />
              <Skeleton className="mt-5 h-3 w-full" />
            </SkeletonCard>
          ))}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Error                                                                       */
/* -------------------------------------------------------------------------- */

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="animate-fade-rise flex flex-col items-center rounded-card border border-bad/25 bg-bad-soft px-6 py-10 text-center"
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-full border border-bad/25 bg-bad-soft text-bad">
        <IconAlert className="h-5 w-5" />
      </span>
      <p className="mt-4 text-[15px] font-semibold text-ink">Couldn&apos;t load this view</p>
      <p className="mt-1.5 max-w-md text-[13px] leading-5 text-ink-2">{message}</p>
      {onRetry && (
        <Button
          onClick={onRetry}
          variant="secondary"
          size="md"
          className="mt-5"
          icon={<IconRefresh className="h-4 w-4" />}
        >
          Retry
        </Button>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Empty                                                                       */
/* -------------------------------------------------------------------------- */

export function EmptyState({
  message,
  icon,
  action,
  compact = false,
}: {
  message: string;
  icon?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-xl border border-dashed border-line-strong bg-base/40 text-center ${
        compact ? "px-4 py-6" : "px-6 py-10"
      }`}
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-surface-2 text-ink-4">
        {icon ?? <IconInbox className="h-[18px] w-[18px]" />}
      </span>
      <p className="mt-3 max-w-sm text-[13px] leading-5 text-ink-3">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
