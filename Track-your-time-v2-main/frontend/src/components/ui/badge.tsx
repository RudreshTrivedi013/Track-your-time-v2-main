import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

/** Colour here always encodes status — never decoration. */
const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium',
  {
    variants: {
      variant: {
        neutral: 'border-border bg-white/5 text-text-secondary',
        pending: 'border-border bg-white/5 text-text-secondary',
        snoozed: 'border-warning/25 bg-warning/10 text-warning',
        done: 'border-success/25 bg-success/10 text-success',
        overdue: 'border-danger/25 bg-danger/10 text-danger',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
