import { redirect, type LoaderFunctionArgs } from 'react-router'

import { adminApi, type UserKind } from '../../api/admin'
import type { QuotationStatus } from '../../api/quotations'
import { requireRole } from '../../lib/guards'

// Every admin loader re-checks the role; the backend enforces it again on each call.
const staff = () => requireRole(['admin', 'super_admin'])

export async function adminLayoutLoader() {
  await staff()
  return { settings: await adminApi.pricingSettings() }
}

export async function materialsLoader() {
  await staff()
  return { materials: await adminApi.materials() }
}

export async function laborRatesLoader() {
  await staff()
  return { laborRates: await adminApi.laborRates() }
}

export async function productsLoader() {
  await staff()
  return { products: await adminApi.products() }
}

export async function productDetailLoader({ params }: LoaderFunctionArgs) {
  await staff()
  const [product, materials, laborRates] = await Promise.all([
    adminApi.product(params.productId ?? ''),
    adminApi.materials(),
    adminApi.laborRates(),
  ])
  return { product, materials, laborRates }
}

const STATUSES: QuotationStatus[] = ['pending', 'approved', 'rejected', 'cancelled']

export async function adminQuotationsLoader({ request }: LoaderFunctionArgs) {
  await staff()
  const param = new URL(request.url).searchParams.get('status') ?? 'pending'
  const status = STATUSES.find((s) => s === param)
  return { status: status ?? 'all', quotations: await adminApi.quotations(status) }
}

export async function adminQuotationDetailLoader({ params }: LoaderFunctionArgs) {
  await staff()
  return { quotation: await adminApi.quotation(params.quotationId ?? '') }
}

export async function auditLogLoader({ request }: LoaderFunctionArgs) {
  await staff()
  const params = new URL(request.url).searchParams
  const filters = {
    action: params.get('action') ?? '',
    actor: params.get('actor') ?? '',
    date_from: params.get('date_from') ?? '',
    date_to: params.get('date_to') ?? '',
  }
  return { filters, page: await adminApi.auditLog(filters) }
}

export async function dashboardLoader({ request }: LoaderFunctionArgs) {
  await staff()
  const params = new URL(request.url).searchParams
  return {
    dashboard: await adminApi.dashboard(
      params.get('date_from') ?? undefined,
      params.get('date_to') ?? undefined,
    ),
  }
}

const KINDS: UserKind[] = ['customers', 'staff', 'deleted', 'all']

export async function usersLoader({ request }: LoaderFunctionArgs) {
  const me = await staff()
  const params = new URL(request.url).searchParams
  const kind = KINDS.find((k) => k === params.get('kind')) ?? 'customers'
  const q = params.get('q') ?? ''
  return { me, kind, q, users: await adminApi.users(kind, q) }
}

export async function sessionsLoader() {
  const me = await staff()
  if (me.role !== 'super_admin') throw redirect('/admin')
  return { me, sessions: await adminApi.sessions() }
}
