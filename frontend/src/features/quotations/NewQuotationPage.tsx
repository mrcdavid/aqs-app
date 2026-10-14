import { zodResolver } from '@hookform/resolvers/zod'
import { Calculator, FilePlus2, PackageX, X } from 'lucide-react'
import { useState } from 'react'
import { FormProvider, useForm, useWatch } from 'react-hook-form'
import { useLoaderData, useNavigate } from 'react-router'

import { quotationsApi } from '../../api/quotations'
import { Button, ButtonLink } from '../../components/ui/Button'
import { Card, EmptyState, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { RequiredNote } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { toast } from '../../stores/feedback'
import type { newQuotationLoader } from './loader'
import { EMPTY_QUOTE_ITEM, missingChoice, quoteItemSchema, sizeErrors, toRequest, type QuoteItemValues } from './quoteItem'
import { ProductStep, SizeStep } from './QuoteItemFields'

export function NewQuotationPage() {
  const { products } = useLoaderData<typeof newQuotationLoader>()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const form = useForm<QuoteItemValues>({
    resolver: zodResolver(quoteItemSchema),
    defaultValues: EMPTY_QUOTE_ITEM,
  })
  const { handleSubmit, control, setError: setFieldError, formState } = form
  const { isSubmitting } = formState
  const [productId, unit, width, height] = useWatch({ control, name: ['product_id', 'unit', 'width', 'height'] })
  const product = products.find((p) => p.id === productId)

  async function onSubmit(values: QuoteItemValues) {
    setError(null)
    if (!product) return
    const sizes = sizeErrors(values, product)
    if (sizes.width) setFieldError('width', { message: sizes.width })
    if (sizes.height) setFieldError('height', { message: sizes.height })
    if (sizes.width || sizes.height) return
    const missing = missingChoice(values, product)
    if (missing) {
      setError(`Choose an option for ${missing}.`)
      return
    }
    try {
      const created = await quotationsApi.create(toRequest(quoteItemSchema.parse(values), product))
      toast.success('Your estimate is ready.')
      navigate(`/app/quotations/${created.id}`)
    } catch (err) {
      setError(messageOf(err))
    }
  }

  if (products.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title="New quotation" icon={FilePlus2} backTo="/app/quotations" backLabel="My quotations" />
        <Card>
          <EmptyState icon={PackageX} title="No products available right now" text="Please check back later, or contact the shop." />
        </Card>
      </div>
    )
  }

  return (
    <FormProvider {...form}>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6 pb-24 sm:pb-0">
        <PageHeader
          title="New quotation"
          description="Choose a product, enter the size, and click Process to get your estimate."
          icon={FilePlus2}
          backTo="/app/quotations"
          backLabel="My quotations"
        />
        <ErrorBanner message={error} />
        <RequiredNote />

        <fieldset disabled={isSubmitting} className="space-y-6">
          <ProductStep n={1} products={products} />
          <SizeStep n={2} products={products} />
        </fieldset>

        {/* Actions: sticky above the phone tab bar, inline on larger screens */}
        <div className="fixed inset-x-0 bottom-16 z-20 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur sm:static sm:border-0 sm:bg-transparent sm:p-0 sm:backdrop-blur-none">
          <div className="mx-auto flex max-w-5xl items-center gap-3 sm:justify-end">
            <p className="min-w-0 flex-1 truncate text-sm text-muted sm:hidden">
              {product ? `${product.name}${width && height ? ` · ${width} × ${height} ${unit}` : ''}` : 'Choose a product'}
            </p>
            <ButtonLink to="/app/quotations" variant="secondary" icon={X} className="max-sm:hidden">
              Cancel
            </ButtonLink>
            <Button type="submit" icon={Calculator} loading={isSubmitting} className="shrink-0">
              {isSubmitting ? 'Processing…' : 'Process'}
            </Button>
          </div>
        </div>
      </form>
    </FormProvider>
  )
}
