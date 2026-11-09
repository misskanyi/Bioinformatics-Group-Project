import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-200 " +
    "motion-safe:active:scale-[0.97] " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/70 focus-visible:ring-offset-2 " +
    "focus-visible:ring-offset-void disabled:pointer-events-none disabled:opacity-45 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary:
          "bg-[image:var(--btn-primary)] text-white font-semibold shadow-[0_0_24px_-6px_var(--glow-strong)] hover:bg-[image:var(--btn-primary-hover)] hover:shadow-[0_0_34px_-4px_var(--glow-cyan)]",
        secondary: "border border-line bg-elevated/70 text-ink hover:border-electric/70 hover:bg-elevated hover:shadow-[0_0_18px_-8px_var(--glow-strong)]",
        ghost: "text-muted hover:bg-elevated/70 hover:text-ink",
        outline: "border border-cyan/40 text-cyan hover:bg-cyan/10",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-4",
        lg: "h-12 px-6 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  },
);
Button.displayName = "Button";
