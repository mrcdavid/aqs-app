import { useRouteLoaderData } from 'react-router'

import type { PricingSettings } from '../../api/admin'

/** Shop currency from the admin layout loader (for display formatting). */
export function useCurrency(): string {
  const data = useRouteLoaderData('admin') as { settings: PricingSettings } | undefined
  return data?.settings.currency ?? 'PHP'
}
