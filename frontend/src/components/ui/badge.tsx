import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-cyan-300/20 bg-cyan-300/[0.12] text-cyan-100 shadow-[0_10px_20px_rgba(90,220,255,0.12)]",
        secondary:
          "border-fuchsia-300/20 bg-fuchsia-300/[0.12] text-fuchsia-100",
        destructive:
          "border-destructive/25 bg-destructive/10 text-destructive-foreground",
        outline: "border-white/[0.12] bg-white/5 text-slate-200",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
