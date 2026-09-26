import { Boxes } from 'lucide-react'
import { useLoaderData } from 'react-router'

import { adminApi } from '../../api/admin'
import { CatalogItemsPage } from './CatalogItemsPage'
import type { materialsLoader } from './loaders'

export function MaterialsPage() {
  const { materials } = useLoaderData<typeof materialsLoader>()
  return (
    <CatalogItemsPage
      title="Materials"
      description="Glass, aluminum, metal and hardware with their current prices."
      icon={Boxes}
      singular="material"
      codeHint="Short unique code, e.g. GL-6MM"
      withCategory
      items={materials.map((m) => ({ ...m, price: m.unit_price }))}
      create={({ price, ...rest }) => adminApi.createMaterial({ ...rest, unit_price: price })}
      update={(id, { price, ...rest }) =>
        adminApi.updateMaterial(id, price === undefined ? rest : { ...rest, unit_price: price })
      }
      remove={adminApi.deleteMaterial}
    />
  )
}
