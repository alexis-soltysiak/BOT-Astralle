import { cn } from "@/lib/utils";

type BrandMarkProps = {
  className?: string;
  glowClassName?: string;
};

export function BrandMark({ className, glowClassName }: BrandMarkProps) {
  return (
    <div className={cn("relative aspect-square w-16", className)}>
      <div
        className={cn(
          "absolute inset-0 rounded-full bg-[radial-gradient(circle,rgba(110,231,255,0.28),transparent_62%)] blur-xl",
          glowClassName
        )}
      />
      <svg
        viewBox="0 0 128 128"
        className="relative z-10 h-full w-full drop-shadow-[0_0_28px_rgba(110,231,255,0.22)]"
        fill="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="astralle-crescent-a" x1="14" y1="28" x2="88" y2="86">
            <stop offset="0%" stopColor="#F59DFF" />
            <stop offset="52%" stopColor="#A84DFF" />
            <stop offset="100%" stopColor="#4321B8" />
          </linearGradient>
          <linearGradient id="astralle-crescent-b" x1="42" y1="70" x2="116" y2="30">
            <stop offset="0%" stopColor="#A067FF" />
            <stop offset="50%" stopColor="#5DDFFF" />
            <stop offset="100%" stopColor="#91F7FF" />
          </linearGradient>
          <radialGradient id="astralle-star" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#FFFFFF" />
            <stop offset="55%" stopColor="#AAFAFF" />
            <stop offset="100%" stopColor="#46CFFF" />
          </radialGradient>
        </defs>

        <path
          d="M84 15c-20 2-39 12-51 28-11 15-15 34-12 51 5-12 15-24 30-34-7-5-12-12-15-22-3-11 0-21 7-31 10-14 24-24 41-30Z"
          fill="url(#astralle-crescent-a)"
        />
        <path
          d="M103 34c6 18 4 38-5 54-11 20-31 33-53 36 12-7 22-16 30-28-11 2-22 1-32-3 14 1 28-2 39-10 16-11 25-29 21-49Z"
          fill="url(#astralle-crescent-b)"
        />
        <path
          d="M64 32l7 20 21 7-21 7-7 21-7-21-21-7 21-7 7-20Z"
          fill="url(#astralle-star)"
        />
        <path d="M93 26l3 8 8 3-8 3-3 8-3-8-8-3 8-3 3-8Z" fill="#74E9FF" />
        <path d="M30 83l2 6 6 2-6 2-2 6-2-6-6-2 6-2 2-6Z" fill="#F28CFF" />
      </svg>
    </div>
  );
}
