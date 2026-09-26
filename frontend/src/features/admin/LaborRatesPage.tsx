import { HardHat } from 'lucide-react'
import { useLoaderData } from 'react-router'

import { adminApi } from '../../api/admin'
import { CatalogItemsPage } from './CatalogItemsPage'
import type { laborRatesLoader } from './loaders'

export function LaborRatesPage() {
  const { laborRates } = useLoaderData<typeof laborRatesLoader>()
  return (
    <CatalogItemsPage
      title="Labour rates"
      description="Fabrication and installation charges, per m², per metre, or per piece."
      icon={HardHat}
      singular="labour rate"
      codeHint="Short unique code, e.g. INSTALL"
      withCategory={false}
      items={laborRates.map((r) => ({ ...r, price: r.rate }))}
      // Labour rates have no category; the shared form's category value is dropped here.
      create={({ price, category: _category, ...rest }) => adminApi.createLaborRate({ ...rest, rate: price })}
      update={(id, { price, category: _category, ...rest }) =>
        adminApi.updateLaborRate(id, price === undefined ? rest : { ...rest, rate: price })
      }
      remove={adminApi.deleteLaborRate}
    />
  )
}
