// Admin catalogue API. Money/quantities are decimal strings (e.g. "850.00"); never parse them
// into numbers for arithmetic — the server does all pricing.

import { api } from './client'
import type { Quotation, QuotationStatus, QuotationSummary } from './quotations'

export type PriceUnit = 'sqm' | 'lm' | 'piece'
export type MaterialCategory = 'glass' | 'aluminum' | 'metal' | 'hardware' | 'other'
export type ProductCategory = 'sliding_window' | 'sliding_door' | 'window_grill' | 'other'
export type Basis = 'area' | 'perimeter' | 'width' | 'height' | 'fixed'

export interface Material {
  id: string
  code: string
  name: string
  category: MaterialCategory
  unit: PriceUnit
  unit_price: string
  is_active: boolean
  updated_at: string
}

export interface LaborRate {
  id: string
  code: string
  name: string
  unit: PriceUnit
  rate: string
  is_active: boolean
  updated_at: string
}

export interface Product {
  id: string
  code: string
  name: string
  category: ProductCategory
  description: string
  min_width_mm: number
  max_width_mm: number
  min_height_mm: number
  max_height_mm: number
  is_active: boolean
  updated_at: string
}

export interface Component {
  id: string
  kind: 'material' | 'labor'
  material_id: string | null
  labor_rate_id: string | null
  item_code: string
  item_name: string
  item_unit: PriceUnit
  item_price: string
  item_active: boolean
  basis: Basis
  factor: string
  waste_percent: string
  label: string
  sort_order: number
}

export interface ProductDetail extends Product {
  components: Component[]
}

export interface PricingSettings {
  markup_percent: string
  vat_percent: string
  currency: string
  quote_validity_days: number
  business_name: string
  business_address: string
  business_contact: string
  quote_terms: string
  updated_at: string
}

export interface PriceLine {
  kind: string
  code: string
  name: string
  label: string
  basis: Basis
  unit: PriceUnit
  unit_price: string
  quantity: string
  cost: string
}

export interface PricePreview {
  width_mm: number
  height_mm: number
  quantity: number
  lines: PriceLine[]
  unit_subtotal: string
  unit_price: string
  subtotal: string
  markup_percent: string
  markup: string
  net: string
  vat_percent: string
  vat: string
  total: string
  currency: string
  warnings: string[]
}

export interface AdminQuotationSummary extends QuotationSummary {
  customer_name: string
  customer_email: string
  customer_city: string
  customer_province: string
}

export interface AdminQuotation extends Quotation {
  customer: {
    email: string
    full_name: string
    contact_number: string
    address_line: string
    city: string
    province: string
  }
  reviewed_by_email: string | null
  breakdown: PricePreview
}

export interface AuditEntry {
  id: number
  created_at: string
  actor_id: string | null
  actor_email: string | null
  action: string
  entity: string | null
  entity_id: string | null
  ip: string | null
  details: Record<string, unknown>
}

export interface AuditPage {
  items: AuditEntry[]
  next_before_id: number | null
}

export interface AuditFilters {
  action?: string
  actor?: string
  date_from?: string
  date_to?: string
  before_id?: number
}

export interface DayPoint {
  day: string
  requested: number
  approved: number
  approved_value: string
}

export interface GroupRow {
  label: string
  requested: number
  approved: number
  approved_value: string
}

export interface Dashboard {
  date_from: string
  date_to: string
  currency: string
  requested: number
  pending: number
  approved: number
  rejected: number
  cancelled: number
  approved_value: string
  approval_rate: string | null
  pending_now: number
  per_day: DayPoint[]
  by_location: GroupRow[]
  by_product: GroupRow[]
  top_projects: {
    id: string
    number: string | null
    customer_name: string
    product_name: string
    city: string
    total: string
    created_at: string
  }[]
}

export type UserKind = 'customers' | 'staff' | 'deleted' | 'all'
export type StaffRole = 'admin' | 'super_admin'

export interface UserRow {
  id: string
  email: string
  role: 'user' | StaffRole
  auth_provider: 'google' | 'password'
  full_name: string | null
  city: string | null
  is_active: boolean
  deleted_at: string | null
  locked: boolean
  last_login_at: string | null
  created_at: string
  active_sessions: number
  last_seen_at: string | null
}

export interface ActiveSession {
  id: string
  user_id: string
  email: string
  role: 'user' | StaffRole
  ip: string | null
  user_agent: string | null
  created_at: string
  last_seen_at: string
}

type Body = Record<string, unknown>
const json = (method: string, body: Body) => ({ method, body: JSON.stringify(body) })

export const adminApi = {
  materials: () => api<Material[]>('/admin/materials'),
  createMaterial: (b: Body) => api<Material>('/admin/materials', json('POST', b)),
  updateMaterial: (id: string, b: Body) => api<Material>(`/admin/materials/${id}`, json('PATCH', b)),
  deleteMaterial: (id: string) => api<void>(`/admin/materials/${id}`, { method: 'DELETE' }),

  laborRates: () => api<LaborRate[]>('/admin/labor-rates'),
  createLaborRate: (b: Body) => api<LaborRate>('/admin/labor-rates', json('POST', b)),
  updateLaborRate: (id: string, b: Body) =>
    api<LaborRate>(`/admin/labor-rates/${id}`, json('PATCH', b)),
  deleteLaborRate: (id: string) => api<void>(`/admin/labor-rates/${id}`, { method: 'DELETE' }),

  products: () => api<Product[]>('/admin/products'),
  product: (id: string) => api<ProductDetail>(`/admin/products/${id}`),
  createProduct: (b: Body) => api<ProductDetail>('/admin/products', json('POST', b)),
  updateProduct: (id: string, b: Body) =>
    api<ProductDetail>(`/admin/products/${id}`, json('PATCH', b)),

  addComponent: (productId: string, b: Body) =>
    api<ProductDetail>(`/admin/products/${productId}/components`, json('POST', b)),
  updateComponent: (productId: string, componentId: string, b: Body) =>
    api<ProductDetail>(`/admin/products/${productId}/components/${componentId}`, json('PATCH', b)),
  removeComponent: (productId: string, componentId: string) =>
    api<ProductDetail>(`/admin/products/${productId}/components/${componentId}`, {
      method: 'DELETE',
    }),

  pricePreview: (productId: string, b: Body) =>
    api<PricePreview>(`/admin/products/${productId}/price-preview`, json('POST', b)),

  pricingSettings: () => api<PricingSettings>('/admin/pricing-settings'),
  updatePricingSettings: (b: Body) => api<PricingSettings>('/admin/pricing-settings', json('PUT', b)),

  quotations: (status?: QuotationStatus) =>
    api<AdminQuotationSummary[]>(`/admin/quotations${status ? `?status=${status}` : ''}`),
  quotation: (id: string) => api<AdminQuotation>(`/admin/quotations/${id}`),
  approveQuotation: (id: string, note: string) =>
    api<AdminQuotation>(`/admin/quotations/${id}/approve`, json('POST', { note })),
  rejectQuotation: (id: string, note: string) =>
    api<AdminQuotation>(`/admin/quotations/${id}/reject`, json('POST', { note })),
  quotationPdfUrl: (id: string) => `/api/v1/admin/quotations/${id}/pdf`,

  auditLog: (filters: AuditFilters) => {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== '') params.set(key, String(value))
    }
    return api<AuditPage>(`/admin/audit-log?${params}`)
  },

  dashboard: (dateFrom?: string, dateTo?: string) => {
    const params = new URLSearchParams()
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    return api<Dashboard>(`/admin/dashboard?${params}`)
  },

  users: (kind: UserKind, q?: string) => {
    const params = new URLSearchParams({ kind })
    if (q) params.set('q', q)
    return api<UserRow[]>(`/admin/users?${params}`)
  },
  createStaff: (b: Body) => api<UserRow>('/admin/users/staff', json('POST', b)),
  updateUser: (id: string, b: Body) => api<UserRow>(`/admin/users/${id}`, json('PATCH', b)),
  deleteUser: (id: string) => api<UserRow>(`/admin/users/${id}`, { method: 'DELETE' }),
  resetPassword: (id: string, password: string) =>
    api<UserRow>(`/admin/users/${id}/reset-password`, json('POST', { password })),
  signOutUser: (id: string) => api<UserRow>(`/admin/users/${id}/sign-out`, { method: 'POST' }),
  sessions: () => api<ActiveSession[]>('/admin/sessions'),
}
