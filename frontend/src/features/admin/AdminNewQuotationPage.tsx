import { zodResolver } from '@hookform/resolvers/zod'
import { Calculator, FilePlus2, PackageX, X } from 'lucide-react'
import { useState } from 'react'
import { FormProvider, useForm } from 'react-hook-form'
import { useLoaderData, useNavigate } from 'react-router'
import type { z } from 'zod'

import { adminApi } from '../../api/admin'
import { Button, ButtonLink } from '../../components/ui/Button'
import { Card, EmptyState, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { Field, inputClass } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { toast } from '../../stores/feedback'
import { chosenOptions, EMPTY_QUOTE_ITEM, quoteItemSchema, sizeErrors } from '../quotations/quoteItem'
import { ProductStep, SizeStep, Step } from '../quotations/QuoteItemFields'
import type { adminNewQuotationLoader } from './loaders'
import { EMPTY_WALK_IN_CLIENT, walkInClientSchema } from './schemas'

const schema = quoteItemSchema.extend({ client: walkInClientSchema })
type FormValues = z.input<typeof schema>

/** Staff quote a walk-in or phone client who has no account. Priced and approved like any request. */
export function AdminNewQuotationPage() {
  const { products } = useLoaderData<typeof adminNewQuotationLoader>()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { ...EMPTY_QUOTE_ITEM, client: EMPTY_WALK_IN_CLIENT },
  })
  const { register, handleSubmit, setError: setFieldError, formState } = form
  const { isSubmitting } = formState
  const errors = formState.errors.client

  async function onSubmit(values: FormValues) {
    setError(null)
    const product = products.find((p) => p.id === values.product_id)
    if (!product) return
    const sizes = sizeErrors(values, product)
    if (sizes.width) setFieldError('width', { message: sizes.width })
    if (sizes.height) setFieldError('height', { message: sizes.height })
    if (sizes.width || sizes.height) return
    const { client, ...item } = schema.parse(values)
    try {
      const created = await adminApi.createQuotation({
        ...item,
        option_ids: chosenOptions(item.option_ids, product),
        client: { ...client, email: client.email || null },
      })
      toast.success(`Estimate ready for ${client.full_name}. Check the amount, then approve to issue it.`)
      navigate(`/admin/quotations/${created.id}`)
    } catch (err) {
      setError(messageOf(err))
    }
  }

  const header = (
    <PageHeader
      title="New quotation"
      description="Quote a walk-in or phone client who has no account. It starts as pending, like any request."
      icon={FilePlus2}
      backTo="/admin/quotations"
      backLabel="All quotations"
    />
  )

  if (products.length === 0) {
    return (
      <>
        {header}
        <Card>
          <EmptyState
            icon={PackageX}
            title="No products to quote yet"
            text="Add a product with a complete template under Catalogue → Products first."
          />
        </Card>
      </>
    )
  }

  return (
    <FormProvider {...form}>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6">
        {header}
        <ErrorBanner message={error} />

        <fieldset disabled={isSubmitting} className="space-y-6">
          <Step n={1} title="Client details">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Full name" htmlFor="c-name" error={errors?.full_name?.message}>
                <input id="c-name" autoComplete="off" className={inputClass} aria-invalid={!!errors?.full_name} {...register('client.full_name')} />
              </Field>
              <Field label="Contact number" htmlFor="c-phone" hint="Mobile or landline" error={errors?.contact_number?.message}>
                <input
                  id="c-phone"
                  type="tel"
                  autoComplete="off"
                  placeholder="e.g. 0917 123 4567"
                  className={inputClass}
                  aria-invalid={!!errors?.contact_number}
                  {...register('client.contact_number')}
                />
              </Field>
              <Field label="Email (optional)" htmlFor="c-email" error={errors?.email?.message}>
                <input id="c-email" type="email" autoComplete="off" className={inputClass} aria-invalid={!!errors?.email} {...register('client.email')} />
              </Field>
              <Field label="Street address" htmlFor="c-street" hint="House no., street, barangay" error={errors?.address_line?.message}>
                <input id="c-street" autoComplete="off" className={inputClass} aria-invalid={!!errors?.address_line} {...register('client.address_line')} />
              </Field>
              <Field label="City / municipality" htmlFor="c-city" error={errors?.city?.message}>
                <input id="c-city" autoComplete="off" className={inputClass} aria-invalid={!!errors?.city} {...register('client.city')} />
              </Field>
              <Field label="Province" htmlFor="c-province" error={errors?.province?.message}>
                <input id="c-province" autoComplete="off" className={inputClass} aria-invalid={!!errors?.province} {...register('client.province')} />
              </Field>
            </div>
          </Step>
          <ProductStep n={2} products={products} />
          <SizeStep n={3} products={products} />
        </fieldset>

        <div className="flex justify-end gap-3">
          <ButtonLink to="/admin/quotations" variant="secondary" icon={X}>
            Cancel
          </ButtonLink>
          <Button type="submit" icon={Calculator} loading={isSubmitting}>
            {isSubmitting ? 'Processing…' : 'Process'}
          </Button>
        </div>
      </form>
    </FormProvider>
  )
}
