import { redirect, type LoaderFunctionArgs } from 'react-router'

import { quotationsApi } from '../../api/quotations'
import { requireRole } from '../../lib/guards'

/** Customers must be signed in and have a profile before quoting. */
async function requireCustomerWithProfile() {
  const me = await requireRole(['user'])
  if (!me.has_profile) throw redirect('/app/profile')
  return me
}

export async function quotationsLoader() {
  await requireCustomerWithProfile()
  return { quotations: await quotationsApi.list() }
}

export async function newQuotationLoader() {
  await requireCustomerWithProfile()
  return { products: await quotationsApi.catalog() }
}

export async function quotationDetailLoader({ params }: LoaderFunctionArgs) {
  await requireCustomerWithProfile()
  return { quotation: await quotationsApi.get(params.quotationId ?? '') }
}
