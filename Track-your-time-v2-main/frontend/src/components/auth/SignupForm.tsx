import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as zod from 'zod'
import { useAuth } from '@/hooks/useAuth'
import { useNavigate, Link } from 'react-router-dom'
import { detectTimezone, parseApiError, TIMEZONES } from '@/lib/utils'
import toast from 'react-hot-toast'
import { Loader2, Mail, Lock, Globe } from 'lucide-react'
import { idbClearToken } from '@/stores/authStore'

const signupSchema = zod.object({
  email: zod.string().email('Please enter a valid email address'),
  password: zod.string().min(8, 'Password must be at least 8 characters long'),
  timezone: zod.string().nonempty('Please select your timezone'),
})

type SignupFormValues = zod.infer<typeof signupSchema>

export function SignupForm() {
  const { signup } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignupFormValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      timezone: detectTimezone(),
    },
  })

  const onSubmit = async (values: SignupFormValues) => {
    setLoading(true)
    try {
      await signup(values.email, values.password, values.timezone)
      toast.success('Account created successfully!')
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
        <h1 className="text-3xl font-bold tracking-tight text-text-primary">Create Account</h1>
        <p className="text-sm text-text-secondary mt-2">Get started with intelligent notifications</p>
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
              placeholder="••••••••"
              className="input-field pl-10"
              disabled={loading}
            />
          </div>
          {errors.password && <p className="text-xs text-danger mt-1">{errors.password.message}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">Timezone</label>
          <div className="relative">
            <Globe className="absolute left-3 top-3 h-5 w-5 text-text-muted" />
            <select
              {...register('timezone')}
              className="input-field pl-10 appearance-none bg-bg-elevated"
              disabled={loading}
            >
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </div>
          {errors.timezone && <p className="text-xs text-danger mt-1">{errors.timezone.message}</p>}
        </div>

        <button type="submit" className="btn-primary w-full py-2.5 flex items-center justify-center gap-2" disabled={loading}>
          {loading ? (
            <>
              <Loader2 className="animate-spin h-5 w-5" /> Creating account...
            </>
          ) : (
            'Sign Up'
          )}
        </button>
      </form>

      <p className="text-center text-sm text-text-secondary mt-6">
        Already have an account?{' '}
        <Link to="/login" className="text-text-primary hover:underline font-medium">
          Log in
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
