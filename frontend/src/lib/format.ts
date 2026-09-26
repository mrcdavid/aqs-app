import type { Basis, MaterialCategory, PriceUnit, ProductCategory } from '../api/admin'

// Display only. Amounts arrive as decimal strings computed by the server.
export function formatMoney(amount: string, currency = 'PHP'): string {
  return new Intl.NumberFormat('en-PH', { style: 'currency', currency }).format(Number(amount))
}

export const UNIT_LABEL: Record<PriceUnit, string> = {
  sqm: 'per m²',
  lm: 'per metre',
  piece: 'per piece',
}

export const BASIS_LABEL: Record<Basis, string> = {
  area: 'Area (m²)',
  perimeter: 'Perimeter (m)',
  width: 'Width (m)',
  height: 'Height (m)',
  fixed: 'Fixed count',
}

/** Which measurement fits each price unit (mirrors BASIS_UNIT in the backend). */
export const BASES_FOR_UNIT: Record<PriceUnit, Basis[]> = {
  sqm: ['area'],
  lm: ['perimeter', 'width', 'height'],
  piece: ['fixed'],
}

export const MATERIAL_CATEGORY_LABEL: Record<MaterialCategory, string> = {
  glass: 'Glass',
  aluminum: 'Aluminum',
  metal: 'Metal',
  hardware: 'Hardware',
  other: 'Other',
}

export const PRODUCT_CATEGORY_LABEL: Record<ProductCategory, string> = {
  sliding_window: 'Sliding window',
  sliding_door: 'Sliding door',
  window_grill: 'Window grill',
  other: 'Other',
}

/** Strip trailing zeros for display: "2.0000" -> "2", "1.2500" -> "1.25". */
export function trimDecimal(value: string): string {
  return value.includes('.') ? value.replace(/\.?0+$/, '') : value
}

const DATE_FORMAT = new Intl.DateTimeFormat('en-PH', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  timeZone: 'Asia/Manila',
})

/** "2026-09-26T..." or "2026-10-26" -> "Sep 26, 2026" (Philippine time). */
export function formatDate(value: string): string {
  // Date-only strings are calendar dates; pin them to noon so no timezone shifts the day.
  const d = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00+08:00`) : new Date(value)
  return DATE_FORMAT.format(d)
}
