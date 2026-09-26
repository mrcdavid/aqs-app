import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useLoaderData, useNavigate } from 'react-router'

import { saveProfile } from '../../api/profile'
import { buttonClass, Field, inputClass } from '../../components/ui/Field'
import { profileSchema, type ProfileInput } from '../../lib/schemas'
import type { profileLoader } from './loader'

const TEXT_FIELDS: { name: Exclude<keyof ProfileInput, 'age'>; label: string; auto: string }[] = [
  { name: 'full_name', label: 'Full name', auto: 'name' },
  { name: 'contact_number', label: 'Mobile number', auto: 'tel' },
  { name: 'address_line', label: 'Street address', auto: 'street-address' },
  { name: 'city', label: 'City / Municipality', auto: 'address-level2' },
  { name: 'province', label: 'Province', auto: 'address-level1' },
]

export function ProfilePage() {
  const { profile } = useLoaderData<typeof profileLoader>()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ProfileInput>({
    resolver: zodResolver(profileSchema),
    defaultValues: profile ?? undefined,
  })

  async function onSubmit(values: ProfileInput) {
    setServerError(null)
    try {
      await saveProfile(values)
      navigate('/app/quotations')
    } catch {
      setServerError('Could not save your profile. Check the fields and try again.')
    }
  }

  return (
    <section className="mx-auto max-w-lg rounded-xl bg-white p-6 shadow-sm">
      <h1 className="text-xl font-semibold">{profile ? 'Your profile' : 'Set up your profile'}</h1>
      <p className="mt-1 text-sm text-muted">
        We use this on your quotation. You can change it later.
      </p>

      <form onSubmit={handleSubmit(onSubmit)} noValidate className="mt-6 space-y-4">
        {serverError && (
          <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {serverError}
          </p>
        )}
        {TEXT_FIELDS.slice(0, 1).map((f) => (
          <Field key={f.name} label={f.label} htmlFor={f.name} error={errors[f.name]?.message}>
            <input
              id={f.name}
              autoComplete={f.auto}
              className={inputClass}
              aria-invalid={!!errors[f.name]}
              {...register(f.name)}
            />
          </Field>
        ))}
        <Field label="Age" htmlFor="age" error={errors.age?.message}>
          <input
            id="age"
            type="number"
            inputMode="numeric"
            min={18}
            max={120}
            className={inputClass}
            aria-invalid={!!errors.age}
            {...register('age', { valueAsNumber: true })}
          />
        </Field>
        {TEXT_FIELDS.slice(1).map((f) => (
          <Field key={f.name} label={f.label} htmlFor={f.name} error={errors[f.name]?.message}>
            <input
              id={f.name}
              autoComplete={f.auto}
              className={inputClass}
              aria-invalid={!!errors[f.name]}
              {...register(f.name)}
            />
          </Field>
        ))}
        <button type="submit" disabled={isSubmitting} className={`${buttonClass} w-full`}>
          {isSubmitting ? 'Saving…' : 'Save and continue'}
        </button>
      </form>
    </section>
  )
}
