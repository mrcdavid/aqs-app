import { ChevronRight, Package, Plus, Ruler } from 'lucide-react'
import { useState } from 'react'
import { Link, useLoaderData, useNavigate } from 'react-router'

import { adminApi } from '../../api/admin'
import { StatusBadge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card, EmptyState, PageHeader } from '../../components/ui/Card'
import { PRODUCT_CATEGORY_LABEL } from '../../lib/format'
import { toast } from '../../stores/feedback'
import type { productsLoader } from './loaders'
import { ProductFormModal } from './ProductForm'
import { EMPTY_PRODUCT } from './schemas'

export function ProductsPage() {
  const { products } = useLoaderData<typeof productsLoader>()
  const navigate = useNavigate()
  const [adding, setAdding] = useState(false)

  return (
    <>
      <PageHeader
        title="Products"
        description="What customers can request. Each product's price comes from its template."
        icon={Package}
        actions={
          <Button icon={Plus} onClick={() => setAdding(true)} className="w-full sm:w-auto">
            New product
          </Button>
        }
      />

      <Card>
        {products.length === 0 ? (
          <EmptyState
            icon={Package}
            title="No products yet"
            text="Create a product, then build its price template from materials and labour."
            action={
              <Button icon={Plus} onClick={() => setAdding(true)}>
                New product
              </Button>
            }
          />
        ) : (
          <ul className="-my-2 divide-y divide-line">
            {products.map((p) => (
              <li key={p.id}>
                <Link
                  to={`/admin/products/${p.id}`}
                  className="group -mx-2 flex items-center gap-4 rounded-xl px-2 py-3 hover:bg-surface-2/70"
                >
                  <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand">
                    <Package className="size-5" aria-hidden />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{p.name}</span>
                      <span className="font-mono text-xs text-muted">{p.code}</span>
                    </span>
                    <span className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                      <span>{PRODUCT_CATEGORY_LABEL[p.category]}</span>
                      <span className="inline-flex items-center gap-1">
                        <Ruler className="size-3.5" aria-hidden />
                        {p.min_width_mm}–{p.max_width_mm} × {p.min_height_mm}–{p.max_height_mm} mm
                      </span>
                    </span>
                  </span>
                  <StatusBadge active={p.is_active} />
                  <ChevronRight className="size-5 shrink-0 text-muted transition group-hover:translate-x-0.5" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <ProductFormModal
        open={adding}
        mode="new"
        initial={EMPTY_PRODUCT}
        onClose={() => setAdding(false)}
        onSave={async (values) => {
          const created = await adminApi.createProduct(values)
          toast.success(`${created.code} created. Now add its price template.`)
          setAdding(false)
          navigate(`/admin/products/${created.id}`)
        }}
      />
    </>
  )
}
