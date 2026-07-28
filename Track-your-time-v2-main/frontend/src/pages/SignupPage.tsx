import { useEffect } from 'react'
import { SignupForm } from '@/components/auth/SignupForm'
import { useAuthStore } from '@/stores/authStore'
import { useNavigate } from 'react-router-dom'

export default function SignupPage() {
  const { isAuthenticated } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/')
    }
  }, [isAuthenticated, navigate])

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg px-4 py-8 select-none">

      <SignupForm />
    </div>
  )
}