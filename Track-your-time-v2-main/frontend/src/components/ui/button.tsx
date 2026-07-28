import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

/**
 * Sizes deviate from stock shadcn on purpose: the defaults (h-9, text-sm) are
 * desktop-sized, and this app is mobile-first. Every variant clears the 44px
 * minimum touch target.
 *
 * On `default` (white) — use it sparingly. One primary action per screen, plus
 * the FAB and Done on a task card. A screen full of white buttons is noise.
 */
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium ' +
    'transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 ' +
    'disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        secondary: 'bg-white/5 text-foreground border border-border hover:bg-white/10',
        ghost: 'text-muted-foreground hover:text-foreground hover:bg-white/5',
        destructive: 'bg-destructive/10 text-destructive border border-destructive/20 hover:bg-destructive/20',
        success: 'bg-success/10 text-success border border-success/20 hover:bg-success/20',
        link: 'text-foreground underline-offset-4 hover:underline',
      },
      size: {
        default: 'min-h-[44px] px-4 py-2',
        sm: 'min-h-[40px] px-3 text-xs',
        lg: 'min-h-[48px] px-6 text-base',
        icon: 'h-11 w-11',
        fab: 'h-14 w-14 rounded-full',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
  },
)
Button.displayName = 'Button'

export { Button, buttonVariants }
