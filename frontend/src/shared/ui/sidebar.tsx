"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { BrandMark } from "@/shared/ui/brand-mark";
import {
  Activity,
  BarChart3,
  Cog,
  Database,
  ListChecks,
  Swords,
  Users,
} from "lucide-react";

const items = [
  { href: "/admin", label: "Dashboard", icon: Activity },
  { href: "/admin/tracked-players", label: "Tracked Players", icon: Users },
  { href: "/admin/leaderboards", label: "Leaderboards", icon: BarChart3 },
  { href: "/admin/live-games", label: "Live Games", icon: Swords },
  { href: "/admin/matches", label: "Matches", icon: Database },
  { href: "/admin/publications", label: "Publications", icon: ListChecks },
  { href: "/admin/jobs", label: "Jobs", icon: Cog },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-full md:sticky md:top-0 md:h-screen md:w-[290px] md:flex-none">
      <div className="p-4 md:h-full md:p-6">
        <div className="glass-panel aurora-border overflow-hidden rounded-[28px]">
          <div className="border-b border-white/10 p-5 md:p-6">
            <div className="flex items-center gap-4">
              <BrandMark className="w-14" />
              <div>
                <div className="text-xl font-semibold tracking-[-0.04em] text-white">
                  Astralle
                </div>
                <div className="text-sm text-slate-300">
                  Control center for rankings and matches
                </div>
              </div>
            </div>
          </div>

          <nav className="flex gap-2 overflow-x-auto p-3 md:block md:space-y-2 md:overflow-visible md:p-4">
            {items.map((it) => {
              const active = pathname === it.href;
              const Icon = it.icon;

              return (
                <Link
                  key={it.href}
                  href={it.href}
                  className={cn(
                    "group flex min-w-fit items-center gap-3 rounded-2xl px-4 py-3 text-sm transition-all duration-200 md:min-w-0",
                    active
                      ? "bg-white text-slate-950 shadow-[0_16px_30px_rgba(255,255,255,0.12)]"
                      : "text-slate-300 hover:bg-white/[0.08] hover:text-white"
                  )}
                >
                  <span
                    className={cn(
                      "flex h-9 w-9 items-center justify-center rounded-xl border transition",
                      active
                        ? "border-slate-200/70 bg-slate-950 text-cyan-300"
                        : "border-white/10 bg-white/5 text-slate-300 group-hover:border-cyan-300/25 group-hover:text-cyan-200"
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="font-medium">{it.label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="hidden p-4 pt-2 md:block">
            <div className="star-divider h-px w-full" />
            <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4">
              <div className="text-xs uppercase tracking-[0.24em] text-slate-400">
                Identity
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Palette inspiree du logo: bleu cosmique, cyan lumineux et magenta neon pour un rendu plus premium.
              </p>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
