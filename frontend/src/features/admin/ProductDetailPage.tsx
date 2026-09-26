import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useLoaderData, useRevalidator } from 'react-router'

import { adminApi } from '../../api/admin'
import { Card, ErrorBanner, StatusBadge } from '../../components/ui/Card'
import { linkButtonClass, secondaryButtonClass } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { PRODUCT_CATEGORY_LABEL } from '../../lib/format'
import { PricePreviewPanel } from './PricePreviewPanel'
import { ProductForm } from './ProductForm'
import { productSchema } from './schemas'
import { TemplateEditor } from './TemplateEditor'
import type { productDetailLoader } from './loaders'

export function ProductDetailPage() {
  const { product, materials, laborRates } = useLoaderData<typeof productDetailLoader>()
  const { revalidate } = useRevalidator()
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function toggleActive() {
    setError(null)
    try {
      await adminApi.updateProduct(product.id, { is_active: !product.is_active })
      revalidate()
    } catch (err) {
      setError(messageOf(err))
    }
  }

  return (
    <>
      <div>
        <Link to="/admin/products" className={linkButtonClass}>
          <ArrowLeft className="size-4" aria-hidden />
          All products
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{product.name}</h1>
          <span className="font-mono text-xs text-muted">{product.code}</span>
          <StatusBadge active={product.is_active} />
        </div>
      </div>

      <Card
        title="Details"
        actions={
          !editing && (
            <div className="flex gap-2">
              <button type="button" className={secondaryButtonClass} onClick={() => setEditing(true)}>
                Edit
              </button>
              <button type="button" className={secondaryButtonClass} onClick={toggleActive}>
                {product.is_active ? 'Archive' : 'Restore'}
              </button>
            </div>
          )
        }
      >
        {editing ? (
          <ProductForm
            // Remount with fresh values whenever the saved product changes.
            key={product.updated_at}
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
            submitLabel="Save changes"
            error={error}
            onCancel={() => {
              setEditing(false)
              setError(null)
            }}
            onSubmit={async (values) => {
              setError(null)
              try {
                await adminApi.updateProduct(product.id, productSchema.parse(values))
                setEditing(false)
                revalidate()
              } catch (err) {
                setError(messageOf(err))
              }
            }}
          />
        ) : (
          <div className="space-y-3">
            <ErrorBanner message={error} />
            <dl className="grid gap-3 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-muted">Category</dt>
                <dd>{PRODUCT_CATEGORY_LABEL[product.category]}</dd>
              </div>
              <div>
                <dt className="text-muted">Width</dt>
                <dd>
                  {product.min_width_mm}–{product.max_width_mm} mm
                </dd>
              </div>
              <div>
                <dt className="text-muted">Height</dt>
                <dd>
                  {product.min_height_mm}–{product.max_height_mm} mm
                </dd>
              </div>
              {product.description && (
                <div className="sm:col-span-3">
                  <dt className="text-muted">Description</dt>
                  <dd className="whitespace-pre-line">{product.description}</dd>
                </div>
              )}
            </dl>
          </div>
        )}
      </Card>

      <TemplateEditor
        product={product}
        materials={materials}
        laborRates={laborRates}
        onChanged={revalidate}
      />

      <PricePreviewPanel product={product} />
    </>
  )
}
