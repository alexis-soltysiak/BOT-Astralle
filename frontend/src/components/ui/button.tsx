import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-[linear-gradient(135deg,rgba(110,231,255,1),rgba(151,71,255,0.86)_55%,rgba(255,107,214,0.92))] text-slate-950 shadow-[0_12px_34px_rgba(110,231,255,0.2)] hover:scale-[1.01] hover:shadow-[0_18px_40px_rgba(151,71,255,0.24)]",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline:
          "border border-white/[0.12] bg-white/5 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] hover:border-cyan-300/25 hover:bg-white/10 hover:text-cyan-100",
        secondary:
          "bg-secondary/[0.18] text-secondary-foreground shadow-[0_10px_24px_rgba(151,71,255,0.16)] hover:bg-secondary/[0.28]",
        ghost: "text-slate-200 hover:bg-white/[0.08] hover:text-white",
        link: "text-cyan-200 underline-offset-4 hover:text-white hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-lg px-3 text-xs",
        lg: "h-11 rounded-xl px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
