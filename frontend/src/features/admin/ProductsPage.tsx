import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useLoaderData, useNavigate } from 'react-router'

import { adminApi } from '../../api/admin'
import { Card, PageHeader, StatusBadge } from '../../components/ui/Card'
import { buttonClass } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { PRODUCT_CATEGORY_LABEL } from '../../lib/format'
import type { productsLoader } from './loaders'
import { ProductForm } from './ProductForm'
import { EMPTY_PRODUCT, productSchema } from './schemas'

export function ProductsPage() {
  const { products } = useLoaderData<typeof productsLoader>()
  const navigate = useNavigate()
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)

  return (
    <>
      <PageHeader
        title="Products"
        description="What customers can request. Each product's price comes from its template."
      />

      {adding ? (
        <Card title="New product">
          <ProductForm
            initial={EMPTY_PRODUCT}
            submitLabel="Create and add template"
            error={error}
            onCancel={() => {
              setAdding(false)
              setError(null)
            }}
            onSubmit={async (values) => {
              setError(null)
              try {
                const created = await adminApi.createProduct(productSchema.parse(values))
                navigate(`/admin/products/${created.id}`)
              } catch (err) {
                setError(messageOf(err))
              }
            }}
          />
        </Card>
      ) : (
        <div>
          <button type="button" className={buttonClass} onClick={() => setAdding(true)}>
            <Plus className="size-4" aria-hidden />
            New product
          </button>
        </div>
      )}

      <Card>
        {products.length === 0 ? (
          <p className="text-muted">No products yet.</p>
        ) : (
          <ul className="divide-y divide-brand-50">
            {products.map((p) => (
              <li key={p.id}>
                <Link
                  to={`/admin/products/${p.id}`}
                  className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg px-2 py-3 hover:bg-brand-50"
                >
                  <span className="font-mono text-xs">{p.code}</span>
                  <span className="font-medium">{p.name}</span>
                  <span className="text-sm text-muted">{PRODUCT_CATEGORY_LABEL[p.category]}</span>
                  <span className="text-sm text-muted">
                    {p.min_width_mm}–{p.max_width_mm} × {p.min_height_mm}–{p.max_height_mm} mm
                  </span>
                  <span className="ml-auto">
                    <StatusBadge active={p.is_active} />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  )
}
