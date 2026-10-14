import { zodResolver } from '@hookform/resolvers/zod'
import { MapPin, Save, UserRound, X } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useLoaderData, useNavigate } from 'react-router'

import { saveProfile } from '../../api/profile'
import { Button, ButtonLink } from '../../components/ui/Button'
import { Card, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { Field, inputClass } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { profileSchema, type ProfileInput } from '../../lib/schemas'
import { toast } from '../../stores/feedback'
import type { profileLoader } from './loader'

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
      toast.success(profile ? 'Profile saved.' : 'Profile saved. You can now request quotations.')
      navigate(profile ? '/app/quotations' : '/app/quotations/new')
    } catch (err) {
      setServerError(messageOf(err))
    }
  }

  const text = (name: Exclude<keyof ProfileInput, 'age'>, label: string, auto: string, extra = {}) => (
    <Field label={label} htmlFor={name} error={errors[name]?.message}>
      <input id={name} autoComplete={auto} className={inputClass} aria-invalid={!!errors[name]} {...extra} {...register(name)} />
    </Field>
  )

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader
        title={profile ? 'Your profile' : 'Set up your profile'}
        description="We print these details on your quotations. You can change them any time."
        icon={UserRound}
      />
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6">
        <ErrorBanner message={serverError} />
        <fieldset disabled={isSubmitting} className="space-y-6">
          <Card title="About you" icon={UserRound}>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">{text('full_name', 'Full name', 'name', { autoFocus: !profile })}</div>
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
              {text('contact_number', 'Mobile number', 'tel', { inputMode: 'tel', maxLength: 20, placeholder: '09XX XXX XXXX' })}
            </div>
          </Card>
          <Card title="Address" icon={MapPin}>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">{text('address_line', 'Street address', 'street-address')}</div>
              {text('city', 'City / Municipality', 'address-level2')}
              {text('province', 'Province', 'address-level1')}
            </div>
          </Card>
        </fieldset>
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          {profile && (
            <ButtonLink to="/app/quotations" variant="secondary" icon={X}>
              Cancel
            </ButtonLink>
          )}
          <Button type="submit" icon={Save} loading={isSubmitting}>
            {profile ? 'Save changes' : 'Save and continue'}
          </Button>
        </div>
      </form>
    </div>
  )
}
