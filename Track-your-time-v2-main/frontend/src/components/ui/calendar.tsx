import { DayPicker } from 'react-day-picker'
import { cn } from '@/lib/utils'
import { buttonVariants } from './button'

/**
 * Styled wrapper over react-day-picker v10.
 *
 * The class-name keys below are v10's (see its `UI` enum) — they differ from
 * the v8 names most shadcn Calendar snippets online still use, so do not copy
 * a stock version over this one.
 *
 * Day cells are 44px to stay tappable; we do not import the library's own
 * stylesheet, everything is Tailwind.
 */
export type CalendarProps = React.ComponentProps<typeof DayPicker>

export function Calendar({ className, classNames, showOutsideDays = true, ...props }: CalendarProps) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      // `relative w-fit` is load-bearing. The nav is absolutely positioned with
      // inset-x-0, so its containing block must be the calendar itself — on a
      // full-width sheet the arrows otherwise fly out to the screen edges,
      // detached from the month they page through.
      className={cn('relative w-fit select-none', className)}
      classNames={{
        months: 'flex flex-col',
        month: 'space-y-3',
        month_caption: 'flex h-10 items-center justify-center',
        caption_label: 'text-sm font-semibold text-foreground',
        nav: 'absolute inset-x-0 top-0 flex h-10 items-center justify-between px-1',
        button_previous: cn(
          buttonVariants({ variant: 'ghost', size: 'icon' }),
          'h-9 w-9 min-h-0 p-0 opacity-70 hover:opacity-100',
        ),
        button_next: cn(
          buttonVariants({ variant: 'ghost', size: 'icon' }),
          'h-9 w-9 min-h-0 p-0 opacity-70 hover:opacity-100',
        ),
        month_grid: 'w-full border-collapse',
        weekdays: 'flex',
        weekday: 'w-11 text-[11px] font-medium text-text-muted',
        week: 'flex w-full',
        day: 'p-0 text-center',
        day_button: cn(
          'flex h-11 w-11 items-center justify-center rounded-lg text-sm',
          'transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
        ),
        selected: '[&>button]:bg-white [&>button]:text-bg [&>button]:font-semibold [&>button]:hover:bg-white',
        today: '[&>button]:border [&>button]:border-white/30',
        outside: '[&>button]:text-text-muted [&>button]:opacity-40',
        disabled: '[&>button]:text-text-muted [&>button]:opacity-30 [&>button]:pointer-events-none',
        hidden: 'invisible',
        ...classNames,
      }}
      {...props}
    />
  )
}
