import type { ComponentType, SVGProps } from "react";
import {
  IconGauge,
  IconLayers,
  IconSearchDoc,
  IconShare,
  IconTrend,
  IconUsers,
} from "@/components/ui/Icons";

export interface NavLink {
  href: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  description: string;
}

export interface NavGroup {
  label: string;
  links: NavLink[];
}

/**
 * Same six routes as before, grouped by what the investigator is doing:
 * watching the feed, analysing a signal, then acting on it.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Monitor",
    links: [
      {
        href: "/overview",
        label: "Overview",
        icon: IconGauge,
        description: "Volume, sentiment and flagged anomalies across the current window",
      },
      {
        href: "/timeline",
        label: "Timeline",
        icon: IconTrend,
        description: "Volume and sentiment over time, baseline through post-event",
      },
    ],
  },
  {
    label: "Analyse",
    links: [
      {
        href: "/topics",
        label: "Narratives",
        icon: IconLayers,
        description: "Detected narratives ranked by trend score",
      },
      {
        href: "/network",
        label: "Network",
        icon: IconShare,
        description: "Community structure and propagation paths",
      },
      {
        href: "/audience",
        label: "Audience",
        icon: IconUsers,
        description: "Aggregate, probabilistic audience composition",
      },
    ],
  },
  {
    label: "Act",
    links: [
      {
        href: "/investigation",
        label: "Investigation",
        icon: IconSearchDoc,
        description: "Cross-dimensional explanation, report and audit trail",
      },
    ],
  },
];

export const ALL_LINKS: NavLink[] = NAV_GROUPS.flatMap((g) => g.links);

export function isActive(pathname: string | null, href: string): boolean {
  if (!pathname) return false;
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function findLink(pathname: string | null): NavLink | undefined {
  return ALL_LINKS.find((l) => isActive(pathname, l.href));
}
