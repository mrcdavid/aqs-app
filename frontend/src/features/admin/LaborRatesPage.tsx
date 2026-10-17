import { HardHat } from 'lucide-react'
import { useLoaderData } from 'react-router'

import { adminApi } from '../../api/admin'
import { CatalogItemsPage } from './CatalogItemsPage'
import type { laborRatesLoader } from './loaders'
import type { PriceItemForm } from './schemas'

/** Form values -> API body. Labour rates have no category or bar length; those are dropped. */
function body({
  price,
  category: _category,
  stock_length: _length,
  stock_length_unit: _lengthUnit,
  ...rest
}: Partial<PriceItemForm> & { is_active?: boolean }) {
  return price === undefined ? rest : { ...rest, rate: price }
}

export function LaborRatesPage() {
  const { laborRates } = useLoaderData<typeof laborRatesLoader>()
  return (
    <CatalogItemsPage
      title="Labour rates"
      description="Fabrication and installation charges, per piece (e.g. per grill), per foot or per sq ft."
      icon={HardHat}
      singular="labour rate"
      codeHint="Short unique code, e.g. INSTALL"
      withCategory={false}
      units={['piece', 'ft', 'sqft']}
      items={laborRates.map((r) => ({ ...r, price: r.rate }))}
      create={(values) => adminApi.createLaborRate(body(values))}
      update={(id, values) => adminApi.updateLaborRate(id, body(values))}
      remove={adminApi.deleteLaborRate}
    />
  )
}
