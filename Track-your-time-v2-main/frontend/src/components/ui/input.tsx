import * as React from 'react'
import { cn } from '@/lib/utils'

/**
 * text-base (16px) is deliberate and must not be reduced: iOS Safari
 * force-zooms the viewport whenever a focused input renders below 16px.
 * Stock shadcn ships text-sm, which would reintroduce that bug.
 */
const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(
        'flex w-full min-h-[44px] rounded-xl border border-border bg-bg-elevated px-3.5 py-2',
        'text-base text-foreground placeholder:text-text-muted',
        'focus-visible:outline-none focus-visible:border-white/40',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  ),
)
Input.displayName = 'Input'

export { Input }
