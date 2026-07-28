import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as zod from 'zod'
import { useAuth } from '@/hooks/useAuth'
import { useNavigate, Link } from 'react-router-dom'
import { parseApiError } from '@/lib/utils'
import toast from 'react-hot-toast'
import { Loader2, Mail, Lock } from 'lucide-react'
import { idbClearToken } from '@/stores/authStore'

const loginSchema = zod.object({
  email: zod.string().email('Please enter a valid email address'),
  password: zod.string().min(8, 'Password must be at least 8 characters long'),
})

type LoginFormValues = zod.infer<typeof loginSchema>

export function LoginForm() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (values: LoginFormValues) => {
    setLoading(true)
    try {
      await login(values.email, values.password)
      toast.success('Logged in successfully!')
      navigate('/')
    } catch (err) {
      toast.error(parseApiError(err))
    } finally {
      setLoading(false)
    }
  }

  const resetAppData = async () => {
    try {
      localStorage.clear()
      await idbClearToken()
      if ('serviceWorker' in navigator) {
        const regs = await navigator.serviceWorker.getRegistrations()
        await Promise.all(regs.map((r) => r.unregister()))
      }
      toast.success('App data cleared — please try again.')
      window.location.reload()
    } catch {
      toast.error('Could not reset app data.')
    }
  }

  return (
    <div className="w-full max-w-md p-8 glass-card space-y-6">
      <div className="text-center">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary">Welcome Back</h1>
        <p className="text-sm text-text-secondary mt-2">Log in to manage your smart reminders</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">Email</label>
          <div className="relative">
            <Mail className="absolute left-3 top-3 h-5 w-5 text-text-muted" />
            <input
              type="email"
              {...register('email')}
              placeholder="you@example.com"
              className="input-field pl-10"
              disabled={loading}
            />
          </div>
          {errors.email && <p className="text-xs text-danger mt-1">{errors.email.message}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">Password</label>
          <div className="relative">
            <Lock className="absolute left-3 top-3 h-5 w-5 text-text-muted" />
            <input
              type="password"
              {...register('password')}
              placeholder="********"
              className="input-field pl-10"
              disabled={loading}
            />
          </div>
          {errors.password && <p className="text-xs text-danger mt-1">{errors.password.message}</p>}
        </div>

        <button type="submit" className="btn-primary w-full py-2.5 flex items-center justify-center gap-2" disabled={loading}>
          {loading ? (
            <>
              <Loader2 className="animate-spin h-5 w-5" /> Signing in...
            </>
          ) : (
            'Sign In'
          )}
        </button>
      </form>

      <p className="text-center text-sm text-text-secondary mt-6">
        Don't have an account?{' '}
        <Link to="/signup" className="text-text-primary hover:underline font-medium">
          Sign up
        </Link>
      </p>

      <p className="text-center text-xs text-text-muted mt-2">
        Having trouble?{' '}
        <button
          type="button"
          onClick={resetAppData}
          className="underline hover:text-text-secondary transition-colors"
        >
          Reset app data
        </button>
      </p>
    </div>
  )
}
