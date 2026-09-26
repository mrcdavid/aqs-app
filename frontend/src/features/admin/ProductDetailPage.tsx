import { Archive, ArchiveRestore, Info, Package, Pencil, Ruler, Tag } from 'lucide-react'
import { useState } from 'react'
import { useLoaderData, useRevalidator } from 'react-router'

import { adminApi } from '../../api/admin'
import { StatusBadge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card, PageHeader } from '../../components/ui/Card'
import { messageOf } from '../../lib/errors'
import { PRODUCT_CATEGORY_LABEL } from '../../lib/format'
import { confirmAction, toast } from '../../stores/feedback'
import type { productDetailLoader } from './loaders'
import { PricePreviewPanel } from './PricePreviewPanel'
import { ProductFormModal } from './ProductForm'
import { TemplateEditor } from './TemplateEditor'

export function ProductDetailPage() {
  const { product, materials, laborRates } = useLoaderData<typeof productDetailLoader>()
  const { revalidate } = useRevalidator()
  const [editing, setEditing] = useState(false)
  const [archiving, setArchiving] = useState(false)

  async function toggleActive() {
    if (product.is_active) {
      const ok = await confirmAction({
        title: `Archive ${product.code}?`,
        message: 'Customers will no longer be able to choose it. Existing quotations are kept, and you can restore it any time.',
        confirmLabel: 'Archive product',
      })
      if (!ok) return
    }
    setArchiving(true)
    try {
      await adminApi.updateProduct(product.id, { is_active: !product.is_active })
      toast.success(product.is_active ? `${product.code} archived.` : `${product.code} restored — customers can choose it again.`)
      revalidate()
    } catch (err) {
      toast.error(messageOf(err))
    } finally {
      setArchiving(false)
    }
  }

  return (
    <>
      <PageHeader
        backTo="/admin/products"
        backLabel="All products"
        title={product.name}
        icon={Package}
        actions={
          <>
            <Button variant="secondary" icon={Pencil} onClick={() => setEditing(true)} className="flex-1 sm:flex-none">
              Edit details
            </Button>
            <Button
              variant="secondary"
              icon={product.is_active ? Archive : ArchiveRestore}
              loading={archiving}
              onClick={toggleActive}
              className="flex-1 sm:flex-none"
            >
              {product.is_active ? 'Archive' : 'Restore'}
            </Button>
          </>
        }
      >
        <span className="font-mono text-xs text-muted">{product.code}</span>
        <StatusBadge active={product.is_active} />
      </PageHeader>

      <Card title="Details" icon={Info}>
        <dl className="grid gap-4 text-sm sm:grid-cols-3">
          <div className="flex items-start gap-3">
            <Tag className="mt-0.5 size-4 text-muted" aria-hidden />
            <div>
              <dt className="text-muted">Category</dt>
              <dd className="font-medium">{PRODUCT_CATEGORY_LABEL[product.category]}</dd>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <Ruler className="mt-0.5 size-4 text-muted" aria-hidden />
            <div>
              <dt className="text-muted">Width</dt>
              <dd className="font-medium tabular-nums">
                {product.min_width_mm}–{product.max_width_mm} mm
              </dd>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <Ruler className="mt-0.5 size-4 rotate-90 text-muted" aria-hidden />
            <div>
              <dt className="text-muted">Height</dt>
              <dd className="font-medium tabular-nums">
                {product.min_height_mm}–{product.max_height_mm} mm
              </dd>
            </div>
          </div>
          {product.description && (
            <div className="sm:col-span-3">
              <dt className="text-muted">Description</dt>
              <dd className="whitespace-pre-line">{product.description}</dd>
            </div>
          )}
        </dl>
      </Card>

      <TemplateEditor product={product} materials={materials} laborRates={laborRates} onChanged={revalidate} />

      <PricePreviewPanel product={product} />

      <ProductFormModal
        open={editing}
        mode="edit"
        code={product.code}
        initial={{
          code: product.code,
          name: product.name,
          category: product.category,
          description: product.description,
          min_width_mm: product.min_width_mm,
          max_width_mm: product.max_width_mm,
          min_height_mm: product.min_height_mm,
          max_height_mm: product.max_height_mm,
        }}
        onClose={() => setEditing(false)}
        onSave={async (values) => {
          await adminApi.updateProduct(product.id, values)
          toast.success('Product details saved.')
          setEditing(false)
          revalidate()
        }}
      />
    </>
  )
}
