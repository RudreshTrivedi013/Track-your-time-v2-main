import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import LoginPage from '@/pages/LoginPage'
import SignupPage from '@/pages/SignupPage'
import HomePage from '@/pages/HomePage'
import SummaryPage from '@/pages/SummaryPage'
import SettingsPage from '@/pages/SettingsPage'
import { useAuthStore } from '@/stores/authStore'
import { useTokenRefresh } from '@/hooks/useTokenRefresh'

/**
 * Auth gate + app shell, used as a single layout route so that `Layout` (and
 * with it the WebSocket, service-worker registration and device heartbeat)
 * mounts once for the whole session instead of once per navigation.
 */
function ProtectedLayout() {
  const { isAuthenticated } = useAuthStore()

  // Proactively refresh the access token before it expires so the user is
  // never silently logged out when the tab is inactive.
  useTokenRefresh()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return <Layout />
}

/**
 * Redirect that PRESERVES the query string.
 *
 * This is permanent, not a migration shim. Service workers already installed
 * on real devices navigate to `/dashboard?checkin=1&reminderId=…` when a
 * check-in notification is tapped, and they only update on their own schedule.
 * A plain <Navigate to="/"> would silently drop reminderId and every one of
 * those deep links would open a blank home screen.
 */
function LegacyRedirect() {
  const { search } = useLocation()
  return <Navigate to={{ pathname: '/', search }} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />

      {/* One shared shell for all authenticated pages. Navigating between the
          children swaps only the <Outlet/> contents — Layout itself, and every
          effect it owns, stays mounted. */}
      <Route element={<ProtectedLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/summary" element={<SummaryPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>

      {/* Retired routes. /dashboard must keep its search params — see above. */}
      <Route path="/dashboard" element={<LegacyRedirect />} />
      <Route path="/tasks" element={<Navigate to="/" replace />} />
      <Route path="/voice" element={<Navigate to="/" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
