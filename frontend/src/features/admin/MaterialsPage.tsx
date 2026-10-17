import { Boxes } from 'lucide-react'
import { useLoaderData } from 'react-router'

import { adminApi } from '../../api/admin'
import { CatalogItemsPage } from './CatalogItemsPage'
import type { materialsLoader } from './loaders'
import type { PriceItemForm } from './schemas'

/** Form values -> API body. Only bars send a length; the server clears it for other units. */
function body({ price, stock_length, stock_length_unit, ...rest }: Partial<PriceItemForm> & { is_active?: boolean }) {
  return {
    ...rest,
    ...(price === undefined ? {} : { unit_price: price }),
    ...(rest.unit === 'bar' ? { stock_length, stock_length_unit } : {}),
  }
}

export function MaterialsPage() {
  const { materials } = useLoaderData<typeof materialsLoader>()
  return (
    <CatalogItemsPage
      title="Materials"
      description="Glass, aluminum, metal and hardware at the prices you buy them: per piece, kilo, foot, sq ft or bar."
      icon={Boxes}
      singular="material"
      codeHint="Short unique code, e.g. GL-6MM"
      withCategory
      units={['piece', 'kg', 'ft', 'sqft', 'bar']}
      items={materials.map((m) => ({ ...m, price: m.unit_price }))}
      create={(values) => adminApi.createMaterial(body(values))}
      update={(id, values) => adminApi.updateMaterial(id, body(values))}
      remove={adminApi.deleteMaterial}
    />
  )
}
