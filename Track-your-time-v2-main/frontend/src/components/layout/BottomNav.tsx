import { NavLink } from 'react-router-dom'
import { FileText, Home, Settings } from '@/lib/icons'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/', icon: Home, label: 'Home', end: true },
  { to: '/summary', icon: FileText, label: 'Summary', end: false },
  { to: '/settings', icon: Settings, label: 'Settings', end: false },
]

export function BottomNav() {
  return (
    // pb-safe is now a real utility (defined in index.css) — it was previously
    // used here but never declared anywhere, so the bar sat underneath the
    // iPhone home indicator.
    <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-bg-surface/95 backdrop-blur pb-safe md:hidden">
      <div className="flex items-stretch justify-around">
        {navItems.map(({ to, icon: Icon, label, end }) => (
          <NavLink key={to} to={to} end={end} className="flex-1">
            {({ isActive }) => (
              <div
                className={cn(
                  'flex min-h-[56px] flex-col items-center justify-center gap-1 transition-colors',
                  isActive ? 'text-text-primary' : 'text-text-muted',
                )}
              >
                <Icon size={22} />
                <span className="text-[11px] font-medium">{label}</span>
              </div>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
