import { NavLink, useNavigate } from 'react-router-dom'
import { Bell, FileText, Home, LogOut, Settings } from '@/lib/icons'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/', icon: Home, label: 'Home', end: true },
  { to: '/summary', icon: FileText, label: 'Summary', end: false },
  { to: '/settings', icon: Settings, label: 'Settings', end: false },
]

export function Sidebar() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <aside className="sticky top-0 z-20 hidden h-screen w-56 shrink-0 flex-col border-r border-border bg-bg-surface p-3 md:flex">
      <div className="mb-6 flex items-center gap-2.5 px-2 py-2">
        <div className="flex size-7 items-center justify-center rounded-lg bg-white/10">
          <Bell size={15} className="text-text-primary" />
        </div>
        <span className="text-sm font-semibold tracking-tight text-text-primary">SmartRemind</span>
      </div>

      <nav className="flex-1 space-y-1">
        {navItems.map(({ to, icon: Icon, label, end }) => (
          <NavLink key={to} to={to} end={end}>
            {({ isActive }) => (
              <div className={cn('nav-item text-sm', isActive && 'nav-item-active')}>
                <Icon size={18} />
                <span className="font-medium">{label}</span>
              </div>
            )}
          </NavLink>
        ))}
      </nav>

      {/* The old footer showed a websocket "Live sync" indicator plus the
          user's email and timezone. None of it was actionable, and the
          connection state is not something a user should have to think about.
          useWebSocket() still runs in Layout — only the readout is gone. */}
      <button onClick={handleLogout} className="nav-item w-full text-sm text-text-secondary">
        <LogOut size={18} />
        <span className="font-medium">Sign out</span>
      </button>
    </aside>
  )
}
