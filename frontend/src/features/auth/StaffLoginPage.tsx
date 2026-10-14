import { zodResolver } from '@hookform/resolvers/zod'
import { Eye, EyeOff, Lock, LogIn, Mail, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'

import { staffLogin } from '../../api/auth'
import { ApiError } from '../../api/client'
import { Button } from '../../components/ui/Button'
import { ErrorBanner } from '../../components/ui/Card'
import { Field, inputClass } from '../../components/ui/Field'
import { homeFor } from '../../lib/guards'
import { staffLoginSchema, type StaffLoginInput } from '../../lib/schemas'
import { AuthShell } from './AuthShell'

export function StaffLoginPage() {
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)
  const [showPassword, setShowPassword] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<StaffLoginInput>({ resolver: zodResolver(staffLoginSchema) })

  async function onSubmit(values: StaffLoginInput) {
    setServerError(null)
    try {
      const me = await staffLogin(values.email, values.password)
      navigate(homeFor(me), { replace: true })
    } catch (err) {
      setServerError(
        err instanceof ApiError && err.status === 429
          ? 'Too many attempts. Wait a minute and try again.'
          : err instanceof ApiError && err.status === 401
            ? 'Invalid email or password.'
            : 'Something went wrong. Please try again.',
      )
    }
  }

  return (
    <AuthShell
      icon={ShieldCheck}
      title="Staff login"
      subtitle="For admins and the business owner."
      footer={
        <>
          Customer?{' '}
          <Link to="/login" className="font-medium text-brand hover:underline">
            Sign in with Google
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <ErrorBanner message={serverError} />
        <Field label="Email" htmlFor="email" required error={errors.email?.message}>
          <div className="relative">
            <Mail className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input
              id="email"
              type="email"
              autoComplete="username"
              autoFocus
              className={`${inputClass} pl-10`}
              aria-invalid={!!errors.email}
              {...register('email')}
            />
          </div>
        </Field>
        <Field label="Password" htmlFor="password" required error={errors.password?.message}>
          <div className="relative">
            <Lock className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              className={`${inputClass} pr-11 pl-10`}
              aria-invalid={!!errors.password}
              {...register('password')}
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              title={showPassword ? 'Hide password' : 'Show password'}
              className="absolute top-1/2 right-1.5 grid size-8 -translate-y-1/2 place-items-center rounded-lg text-muted hover:bg-surface-2 hover:text-ink"
            >
              {showPassword ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
            </button>
          </div>
        </Field>
        <Button type="submit" icon={LogIn} loading={isSubmitting} className="h-12 w-full text-base">
          {isSubmitting ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
    </AuthShell>
  )
}
