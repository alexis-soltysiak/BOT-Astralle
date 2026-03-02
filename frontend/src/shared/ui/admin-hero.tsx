import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type AdminHeroProps = {
  eyebrow?: string;
  title: string;
  description: string;
  metrics?: ReactNode;
  actions?: ReactNode;
  className?: string;
};

export function AdminHero({
  eyebrow,
  title,
  description,
  metrics,
  actions,
  className,
}: AdminHeroProps) {
  return (
    <section
      className={cn(
        "glass-panel aurora-border relative overflow-hidden rounded-[32px] p-6 md:p-8",
        className
      )}
    >
      <div className="absolute inset-y-0 right-0 hidden w-1/2 bg-[radial-gradient(circle_at_center,rgba(110,231,255,0.14),transparent_58%)] md:block" />
      <div className="relative flex flex-col gap-8 xl:flex-row xl:items-end xl:justify-between">
        <div className="max-w-3xl">
          {eyebrow ? (
            <div className="mb-4 text-xs font-semibold uppercase tracking-[0.28em] text-cyan-200/70">
              {eyebrow}
            </div>
          ) : null}
          <h1 className="max-w-3xl text-4xl font-semibold text-white md:text-5xl">
            {title}
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-300 md:text-lg">
            {description}
          </p>
          {metrics ? <div className="mt-6 flex flex-wrap gap-3">{metrics}</div> : null}
        </div>
        {actions ? <div className="grid gap-3 sm:grid-cols-2 xl:w-[420px] xl:grid-cols-1">{actions}</div> : null}
      </div>
    </section>
  );
}
