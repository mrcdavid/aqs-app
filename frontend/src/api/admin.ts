// Admin catalogue API. Money/quantities are decimal strings (e.g. "850.00"); never parse them
// into numbers for arithmetic — the server does all pricing.

import { api } from './client'
import type { Quotation, QuotationRequest, QuotationStatus, QuotationSummary } from './quotations'

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

/** A choose-one question of a product, e.g. Glass type. Its choices are ProductOptions. */
export interface ProductOptionGroup {
  id: string
  name: string
  sort_order: number
}

/** An add-on (group_id null, tick or not) or one choice of a group, made of template lines. */
export interface ProductOption {
  id: string
  group_id: string | null
  name: string
  description: string
  sort_order: number
  /** When chosen, the rest of the window is measured this much narrower / shorter (open back). */
  width_reduction_mm: number
  height_reduction_mm: number
}

export interface Component {
  id: string
  kind: 'material' | 'labor'
  material_id: string | null
  labor_rate_id: string | null
  /** null = always included; otherwise the add-on this line belongs to */
  option_id: string | null
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
  option_groups: ProductOptionGroup[]
  options: ProductOption[]
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
  rounding_step: string
  owner_name: string
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
  /** Add-on or choice name; '' = always included */
  option: string
  /** Size this line was measured at (null in quotations made before choice groups) */
  width_mm: number | null
  height_mm: number | null
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
  rounding_step: string
  /** rounded_total - total */
  rounding: string
  rounded_total: string
  currency: string
  warnings: string[]
}

export interface AdminQuotationSummary extends QuotationSummary {
  /** Quoted by staff for a client without an account */
  walk_in: boolean
  customer_name: string
  customer_email: string
  customer_city: string
  customer_province: string
}

export interface AdminQuotation extends Quotation {
  walk_in: boolean
  customer: {
    /** Empty for walk-in clients who gave none */
    email: string
    full_name: string
    contact_number: string
    address_line: string
    city: string
    province: string
  }
  created_by_email: string | null
  reviewed_by_email: string | null
  /** The total was changed by hand on approval */
  total_adjusted: boolean
  breakdown: PricePreview
}

export interface WalkInClient {
  full_name: string
  contact_number: string
  email: string | null
  address_line: string
  city: string
  province: string
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

  addOptionGroup: (productId: string, b: Body) =>
    api<ProductDetail>(`/admin/products/${productId}/option-groups`, json('POST', b)),
  updateOptionGroup: (productId: string, groupId: string, b: Body) =>
    api<ProductDetail>(`/admin/products/${productId}/option-groups/${groupId}`, json('PATCH', b)),
  /** Also removes the group's choices and their lines. */
  removeOptionGroup: (productId: string, groupId: string) =>
    api<ProductDetail>(`/admin/products/${productId}/option-groups/${groupId}`, { method: 'DELETE' }),

  addOption: (productId: string, b: Body) =>
    api<ProductDetail>(`/admin/products/${productId}/options`, json('POST', b)),
  updateOption: (productId: string, optionId: string, b: Body) =>
    api<ProductDetail>(`/admin/products/${productId}/options/${optionId}`, json('PATCH', b)),
  /** Also removes the add-on's lines. */
  removeOption: (productId: string, optionId: string) =>
    api<ProductDetail>(`/admin/products/${productId}/options/${optionId}`, { method: 'DELETE' }),

  pricePreview: (productId: string, b: Body) =>
    api<PricePreview>(`/admin/products/${productId}/price-preview`, json('POST', b)),

  pricingSettings: () => api<PricingSettings>('/admin/pricing-settings'),
  updatePricingSettings: (b: Body) => api<PricingSettings>('/admin/pricing-settings', json('PUT', b)),

  quotations: (status?: QuotationStatus) =>
    api<AdminQuotationSummary[]>(`/admin/quotations${status ? `?status=${status}` : ''}`),
  quotation: (id: string) => api<AdminQuotation>(`/admin/quotations/${id}`),
  createQuotation: (b: QuotationRequest & { client: WalkInClient }) =>
    api<AdminQuotation>('/admin/quotations', json('POST', { ...b })),
  /** `finalTotal` replaces the quoted amount; omit to keep it. */
  approveQuotation: (id: string, note: string, finalTotal?: string) =>
    api<AdminQuotation>(`/admin/quotations/${id}/approve`, json('POST', { note, final_total: finalTotal })),
  rejectQuotation: (id: string, note: string) =>
    api<AdminQuotation>(`/admin/quotations/${id}/reject`, json('POST', { note })),
  /** Withdraw a pending request; the note is optional. */
  cancelQuotation: (id: string, note: string) =>
    api<AdminQuotation>(`/admin/quotations/${id}/cancel`, json('POST', { note })),
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
