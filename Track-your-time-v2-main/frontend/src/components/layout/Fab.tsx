import { Plus } from '@/lib/icons'

interface FabProps {
  onClick: () => void
}

/**
 * Mobile-only "new reminder" button.
 *
 * Sits above the bottom nav (56px) plus the home indicator, so it never
 * overlaps either. Desktop gets a normal button in the Home header instead.
 */
export function Fab({ onClick }: FabProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="New reminder"
      className="fixed right-4 z-30 flex size-14 items-center justify-center rounded-full bg-white text-bg shadow-lg transition-transform active:scale-95 md:hidden"
      style={{ bottom: 'calc(env(safe-area-inset-bottom, 0px) + 4.5rem)' }}
    >
      <Plus size={24} />
    </button>
  )
}
