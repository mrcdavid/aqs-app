import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'

import { staffLogin } from '../../api/auth'
import { ApiError } from '../../api/client'
import { buttonClass, Field, inputClass } from '../../components/ui/Field'
import { homeFor } from '../../lib/guards'
import { staffLoginSchema, type StaffLoginInput } from '../../lib/schemas'

export function StaffLoginPage() {
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)
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
    <section className="mx-auto max-w-sm rounded-xl bg-white p-6 shadow-sm">
      <h1 className="text-xl font-semibold">Staff login</h1>
      <p className="mt-1 text-sm text-muted">For admins and the business owner.</p>

      <form onSubmit={handleSubmit(onSubmit)} noValidate className="mt-6 space-y-4">
        {serverError && (
          <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {serverError}
          </p>
        )}
        <Field label="Email" htmlFor="email" error={errors.email?.message}>
          <input
            id="email"
            type="email"
            autoComplete="username"
            className={inputClass}
            aria-invalid={!!errors.email}
            {...register('email')}
          />
        </Field>
        <Field label="Password" htmlFor="password" error={errors.password?.message}>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            className={inputClass}
            aria-invalid={!!errors.password}
            {...register('password')}
          />
        </Field>
        <button type="submit" disabled={isSubmitting} className={`${buttonClass} w-full`}>
          {isSubmitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      <p className="mt-4 text-center text-sm">
        <Link to="/login" className="text-brand-600 hover:underline">
          Customer sign-in
        </Link>
      </p>
    </section>
  )
}
