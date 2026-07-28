import * as React from 'react'
import { Drawer as DrawerPrimitive } from 'vaul'
import { cn } from '@/lib/utils'

/**
 * Bottom sheet built on vaul.
 *
 * Chosen over a hand-rolled Radix Dialog because vaul already handles
 * drag-to-dismiss, background scroll locking, keyboard avoidance and
 * safe-area insets — all of which are fiddly to get right on iOS and all of
 * which a naive centred dialog gets wrong.
 */
const Drawer = ({
  shouldScaleBackground = false,
  ...props
}: React.ComponentProps<typeof DrawerPrimitive.Root>) => (
  <DrawerPrimitive.Root shouldScaleBackground={shouldScaleBackground} {...props} />
)
Drawer.displayName = 'Drawer'

const DrawerTrigger = DrawerPrimitive.Trigger
const DrawerPortal = DrawerPrimitive.Portal
const DrawerClose = DrawerPrimitive.Close

/**
 * The overlay had no exit animation, and that was a real bug — not a cosmetic
 * one.
 *
 * vaul keeps the overlay mounted while it plays its close transition and only
 * removes it once that transition ends. With no animation defined, the
 * `animationend`/`transitionend` never fired, so the element stayed in the DOM
 * forever as `data-state="closed"` with `opacity: 1` and `pointer-events: auto`
 * — a full-screen, invisible, z-50 sheet that silently swallowed every click on
 * the page. The only way out was reloading the tab.
 *
 * Two defences, deliberately belt-and-braces:
 *   1. Real enter/exit animations, so vaul's unmount actually gets triggered.
 *   2. `data-[state=closed]:pointer-events-none` — even if the element lingers
 *      for any reason, it can no longer intercept clicks.
 */
const DrawerOverlay = React.forwardRef<
  React.ElementRef<typeof DrawerPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DrawerPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DrawerPrimitive.Overlay
    ref={ref}
    className={cn(
      'fixed inset-0 z-50 bg-black/70',
      'data-[state=open]:animate-in data-[state=open]:fade-in-0',
      'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
      'data-[state=closed]:pointer-events-none',
      className,
    )}
    {...props}
  />
))
DrawerOverlay.displayName = DrawerPrimitive.Overlay.displayName

const DrawerContent = React.forwardRef<
  React.ElementRef<typeof DrawerPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DrawerPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DrawerPortal>
    <DrawerOverlay />
    <DrawerPrimitive.Content
      ref={ref}
      className={cn(
        'fixed inset-x-0 bottom-0 z-50 mt-24 flex h-auto max-h-[85dvh] flex-col',
        'rounded-t-2xl border-t border-border bg-bg-surface',
        // Same reasoning as DrawerOverlay: without a close transition vaul never
        // unmounts this, leaving a stale panel (and its focus trap) behind.
        'data-[state=closed]:pointer-events-none',
        // Sheets often sit above the keyboard; keep content clear of the
        // home indicator when it does not.
        'pb-[env(safe-area-inset-bottom,0px)]',
        className,
      )}
      {...props}
    >
      <div className="mx-auto mt-3 h-1 w-10 shrink-0 rounded-full bg-white/20" aria-hidden />
      {children}
    </DrawerPrimitive.Content>
  </DrawerPortal>
))
DrawerContent.displayName = 'DrawerContent'

const DrawerHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex flex-col gap-1 p-4 text-left', className)} {...props} />
)
DrawerHeader.displayName = 'DrawerHeader'

const DrawerFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('mt-auto flex flex-col gap-2 p-4', className)} {...props} />
)
DrawerFooter.displayName = 'DrawerFooter'

const DrawerTitle = React.forwardRef<
  React.ElementRef<typeof DrawerPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DrawerPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DrawerPrimitive.Title
    ref={ref}
    className={cn('text-base font-semibold text-foreground', className)}
    {...props}
  />
))
DrawerTitle.displayName = DrawerPrimitive.Title.displayName

const DrawerDescription = React.forwardRef<
  React.ElementRef<typeof DrawerPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DrawerPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DrawerPrimitive.Description
    ref={ref}
    className={cn('text-xs text-muted-foreground', className)}
    {...props}
  />
))
DrawerDescription.displayName = DrawerPrimitive.Description.displayName

export {
  Drawer,
  DrawerPortal,
  DrawerOverlay,
  DrawerTrigger,
  DrawerClose,
  DrawerContent,
  DrawerHeader,
  DrawerFooter,
  DrawerTitle,
  DrawerDescription,
}
