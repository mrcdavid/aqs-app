// Customer quotation API. Amounts are decimal strings computed by the server.

import type { ProductCategory } from './admin'
import { api } from './client'

export type QuotationStatus = 'pending' | 'approved' | 'rejected' | 'cancelled'
export type LengthUnit = 'cm' | 'in'

/** An add-on that can be ticked when quoting a product. */
export interface CatalogOption {
  id: string
  name: string
  description: string
}

/** A choose-one question, e.g. Glass type; exactly one choice must be sent. */
export interface CatalogChoiceGroup {
  id: string
  name: string
  choices: CatalogOption[]
}

export interface CatalogProduct {
  id: string
  code: string
  name: string
  category: ProductCategory
  description: string
  min_width_mm: number
  max_width_mm: number
  min_height_mm: number
  max_height_mm: number
  choice_groups: CatalogChoiceGroup[]
  /** Add-ons: tick any */
  options: CatalogOption[]
}

export interface QuotationSummary {
  id: string
  number: string | null
  status: QuotationStatus
  items: { product_name: string; width_mm: number; height_mm: number; quantity: number }[]
  total: string
  currency: string
  created_at: string
}

/** One product of a quotation, with its own amount (VAT included, never itemised). */
export interface QuotationItem {
  position: number
  product_name: string
  product_description: string
  includes: string[]
  /** One per choice group, e.g. [{ group: 'Glass type', name: 'Reflective' }] */
  choices: { group: string; name: string }[]
  /** Chosen add-ons, e.g. ["Open back aluminum"] */
  options: string[]
  input_width: string
  input_height: string
  input_unit: LengthUnit
  width_mm: number
  height_mm: number
  quantity: number
  /** For the whole quantity, VAT included, rounded up */
  amount: string
}

/** What the customer sees: an amount per item and the total (VAT included), and the 50/50 split. */
export interface Quotation {
  id: string
  number: string | null
  status: QuotationStatus
  items: QuotationItem[]
  /** Sum of the item amounts */
  subtotal: string
  /** total - subtotal: an amount changed on approval ('0.00' if none) */
  adjustment: string
  total: string
  /** 50% before work starts */
  downpayment: string
  /** 50% on completion and installation */
  balance: string
  currency: string
  created_at: string
  reviewed_at: string | null
  review_note: string | null
  valid_until: string | null
  can_cancel: boolean
  /** Cancelled by the shop rather than by the customer */
  cancelled_by_staff: boolean
}

export interface QuotationItemRequest {
  product_id: string
  width: string
  height: string
  unit: LengthUnit
  quantity: number
  /** Chosen add-ons plus one choice per group */
  option_ids: string[]
}

export interface QuotationRequest {
  items: QuotationItemRequest[]
}

export const quotationsApi = {
  catalog: () => api<CatalogProduct[]>('/catalog/products'),
  list: () => api<QuotationSummary[]>('/quotations'),
  get: (id: string) => api<Quotation>(`/quotations/${id}`),
  create: (body: QuotationRequest) =>
    api<Quotation>('/quotations', { method: 'POST', body: JSON.stringify(body) }),
  cancel: (id: string) => api<Quotation>(`/quotations/${id}/cancel`, { method: 'POST' }),
  /** Opened in a new tab; the session cookie authorises it. */
  pdfUrl: (id: string) => `/api/v1/quotations/${id}/pdf`,
}
