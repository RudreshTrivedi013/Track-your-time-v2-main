import { useEffect } from 'react'
import { LoginForm } from '@/components/auth/LoginForm'
import { useAuthStore } from '@/stores/authStore'
import { useNavigate } from 'react-router-dom'

export default function LoginPage() {
  const { isAuthenticated } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/')
    }
  }, [isAuthenticated, navigate])

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg px-4 py-8 select-none">

      <LoginForm />
    </div>
  )
}