// Customer quotation API. Amounts are decimal strings computed by the server.

import type { ProductCategory } from './admin'
import { api } from './client'

export type QuotationStatus = 'pending' | 'approved' | 'rejected' | 'cancelled'
export type LengthUnit = 'cm' | 'in'

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
}

export interface QuotationSummary {
  id: string
  number: string | null
  status: QuotationStatus
  product_name: string
  width_mm: number
  height_mm: number
  quantity: number
  total: string
  currency: string
  created_at: string
}

export interface Quotation {
  id: string
  number: string | null
  status: QuotationStatus
  product_name: string
  product_description: string
  includes: string[]
  input_width: string
  input_height: string
  input_unit: LengthUnit
  width_mm: number
  height_mm: number
  quantity: number
  unit_price: string
  amount: string
  vat_percent: string
  vat: string
  total: string
  currency: string
  created_at: string
  reviewed_at: string | null
  review_note: string | null
  valid_until: string | null
  can_cancel: boolean
}

export interface QuotationRequest {
  product_id: string
  width: string
  height: string
  unit: LengthUnit
  quantity: number
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
