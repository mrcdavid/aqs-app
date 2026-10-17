import { zodResolver } from '@hookform/resolvers/zod'
import { Building2, Percent, RotateCcw, Save, Settings, TrendingUp } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useRevalidator, useRouteLoaderData } from 'react-router'

import { adminApi, type PricingSettings } from '../../api/admin'
import { Button } from '../../components/ui/Button'
import { Card, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { Field, inputClass, RequiredNote } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { confirmAction, toast } from '../../stores/feedback'
import { settingsSchema, type SettingsForm } from './schemas'

function toForm(s: PricingSettings): SettingsForm {
  return {
    markup_percent: s.markup_percent,
    vat_percent: s.vat_percent,
    currency: s.currency,
    quote_validity_days: s.quote_validity_days,
    business_name: s.business_name,
    business_address: s.business_address,
    business_contact: s.business_contact,
    quote_terms: s.quote_terms,
    rounding_step: s.rounding_step,
    owner_name: s.owner_name,
  }
}

export function PricingSettingsPage() {
  const { settings } = useRouteLoaderData('admin') as { settings: PricingSettings }
  const { revalidate } = useRevalidator()
  const [error, setError] = useState<string | null>(null)

  const { register, handleSubmit, reset, formState } = useForm<SettingsForm>({
    resolver: zodResolver(settingsSchema),
    defaultValues: toForm(settings),
  })
  const { errors, isSubmitting, isDirty } = formState

  async function onSubmit(values: SettingsForm) {
    setError(null)
    try {
      const saved = await adminApi.updatePricingSettings(settingsSchema.parse(values))
      reset(toForm(saved))
      toast.success('Settings saved. New quotations and approvals use them.')
      revalidate()
    } catch (err) {
      setError(messageOf(err))
    }
  }

  return (
    <>
      <PageHeader
        title="Settings"
        description="Pricing applied to new quotations, and the business details printed on PDFs."
        icon={Settings}
      />
      <div className="space-y-6 pb-24">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6">
        <ErrorBanner message={error} />
        <RequiredNote />
        <fieldset disabled={isSubmitting} className="grid gap-6 lg:grid-cols-2">
          <Card title="Pricing" icon={Percent}>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label="Markup (%)"
                htmlFor="markup"
                required
                hint="Products priced from materials (e.g. grills): added to their cost"
                error={errors.markup_percent?.message}
              >
                <input id="markup" inputMode="decimal" className={`${inputClass} tabular-nums`} {...register('markup_percent')} />
              </Field>
              <Field
                label="VAT (%)"
                htmlFor="vat"
                required
                hint="Included in every price, never added; staff see the VAT inside each amount"
                error={errors.vat_percent?.message}
              >
                <input id="vat" inputMode="decimal" className={`${inputClass} tabular-nums`} {...register('vat_percent')} />
              </Field>
              <Field label="Currency" htmlFor="currency" required error={errors.currency?.message}>
                <input id="currency" className={`${inputClass} uppercase`} maxLength={3} {...register('currency')} />
              </Field>
              <Field label="Quotation valid for (days)" htmlFor="validity" required error={errors.quote_validity_days?.message}>
                <input
                  id="validity"
                  type="number"
                  min={1}
                  max={365}
                  className={`${inputClass} tabular-nums`}
                  {...register('quote_validity_days', { valueAsNumber: true })}
                />
              </Field>
              <Field
                label="Round totals up to the next"
                htmlFor="rounding"
                required
                hint="e.g. 100 turns 21,423 into 21,500 · 0 = no rounding"
                error={errors.rounding_step?.message}
              >
                <input id="rounding" inputMode="decimal" className={`${inputClass} tabular-nums`} {...register('rounding_step')} />
              </Field>
            </div>
          </Card>
          <Card title="Business details on PDFs" icon={Building2}>
            <div className="space-y-4">
              <Field label="Business name" htmlFor="b-name" required error={errors.business_name?.message}>
                <input id="b-name" className={inputClass} {...register('business_name')} />
              </Field>
              <Field label="Address" htmlFor="b-address" error={errors.business_address?.message}>
                <input id="b-address" className={inputClass} {...register('business_address')} />
              </Field>
              <Field label="Contact" htmlFor="b-contact" hint="e.g. 0917 123 4567 · sales@example.com" error={errors.business_contact?.message}>
                <input id="b-contact" className={inputClass} {...register('business_contact')} />
              </Field>
              <Field label="Owner name" htmlFor="b-owner" hint="Printed under the owner's signature line" error={errors.owner_name?.message}>
                <input id="b-owner" className={inputClass} {...register('owner_name')} />
              </Field>
              <Field label="Terms and conditions" htmlFor="b-terms" error={errors.quote_terms?.message}>
                <textarea id="b-terms" rows={5} className={inputClass} {...register('quote_terms')} />
              </Field>
            </div>
          </Card>
        </fieldset>

        {/* Save bar: appears once something changed so it's obvious there are unsaved edits. */}
        {isDirty && (
          <div className="fixed inset-x-0 bottom-0 z-20 animate-fade-up border-t border-line bg-surface/95 px-4 py-3 backdrop-blur md:inset-x-auto md:right-6 md:bottom-6 md:rounded-2xl md:border md:shadow-card">
            <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 md:gap-6">
              <p className="text-sm font-medium">You have unsaved changes</p>
              <div className="flex gap-2">
                <Button variant="secondary" icon={RotateCcw} onClick={() => reset()} disabled={isSubmitting}>
                  Discard
                </Button>
                <Button type="submit" icon={Save} loading={isSubmitting}>
                  Save settings
                </Button>
              </div>
            </div>
          </div>
        )}
      </form>
      <RaiseRatesCard />
      </div>
    </>
  )
}

const PERCENT = /^-?\d{1,3}(\.\d{1,2})?$/

/** Raise (or lower) every rate per sq ft at once, e.g. when materials get dearer. */
function RaiseRatesCard() {
  const { revalidate } = useRevalidator()
  const [percent, setPercent] = useState('5')
  const [busy, setBusy] = useState(false)
  const value = percent.trim()
  const n = Number(value)
  const error = !PERCENT.test(value) || n === 0 ? 'A percent like 5 or -3' : n < -50 || n > 100 ? 'Between -50 and 100' : null

  async function apply() {
    if (error) return
    const ok = await confirmAction({
      title: n > 0 ? `Raise every rate by ${value}%?` : `Lower every rate by ${value.replace('-', '')}%?`,
      message:
        'This changes every rate per sq ft: the base rate of each product sold per sq ft and the rates of its glass types and add-ons. Quotations already made keep their prices. Products priced from materials (e.g. grills) follow their material prices instead — update those on the Materials page.',
      confirmLabel: n > 0 ? 'Yes, raise rates' : 'Yes, lower rates',
      cancelLabel: 'No',
    })
    if (!ok) return
    setBusy(true)
    try {
      const r = await adminApi.raiseRates(value)
      toast.success(`Rates changed by ${value}%: ${r.products} product rate(s) and ${r.options} option rate(s).`)
      revalidate()
    } catch (err) {
      toast.error(messageOf(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Raise all rates" icon={TrendingUp}>
      <p className="mb-4 text-sm text-muted">
        Materials got dearer? Change every rate per sq ft by the same percentage, rounded to centavos. Use a minus sign to
        lower them. Each change is recorded in the audit log.
      </p>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <Field label="Change by (%)" htmlFor="raise" required error={value && error ? error : undefined} className="sm:w-48">
          <input
            id="raise"
            inputMode="decimal"
            className={`${inputClass} tabular-nums`}
            value={percent}
            onChange={(e) => setPercent(e.target.value)}
            aria-invalid={!!error}
          />
        </Field>
        <Button icon={TrendingUp} onClick={apply} loading={busy} disabled={!!error}>
          Apply to all rates
        </Button>
      </div>
    </Card>
  )
}
