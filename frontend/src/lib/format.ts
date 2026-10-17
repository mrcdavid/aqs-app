import type { Basis, LegacyUnit, MaterialCategory, PriceUnit, ProductCategory } from '../api/admin'

// Display only. Amounts arrive as decimal strings computed by the server.
export function formatMoney(amount: string, currency = 'PHP'): string {
  return new Intl.NumberFormat('en-PH', { style: 'currency', currency }).format(Number(amount))
}

/** Includes the metric units of quotations priced before v2. */
export const UNIT_LABEL: Record<PriceUnit | LegacyUnit, string> = {
  piece: 'per piece',
  kg: 'per kilo',
  ft: 'per foot',
  sqft: 'per sq ft',
  bar: 'per bar',
  sqm: 'per m²',
  lm: 'per metre',
}

/** Short unit for quantities: "16.8 sq ft", "2 bars", "0.8 kg". */
export const QTY_UNIT: Record<PriceUnit | LegacyUnit, string> = {
  piece: 'pc',
  kg: 'kg',
  ft: 'ft',
  sqft: 'sq ft',
  bar: 'bar',
  sqm: 'm²',
  lm: 'm',
}

export const BASIS_LABEL: Record<Basis, string> = {
  area: 'Area (sq ft)',
  perimeter: 'Perimeter (ft)',
  width: 'Width (ft)',
  height: 'Height (ft)',
  fixed: 'Fixed count',
}

const LENGTHS: Basis[] = ['perimeter', 'width', 'height']
/** Which measurements fit each unit (mirrors BASES_FOR_UNIT in the backend). Bars: a length
 * (feet needed / bar length), an area (factor = bars per sq ft, e.g. grills) or a fixed count. */
export const BASES_FOR_UNIT: Record<PriceUnit, Basis[]> = {
  piece: ['fixed'],
  kg: [...LENGTHS, 'area', 'fixed'],
  ft: LENGTHS,
  sqft: ['area'],
  bar: [...LENGTHS, 'area', 'fixed'],
}

/** "21 ft bar", "6 m bar" */
export function barLabel(length: string | null | undefined, unit: string | null | undefined): string {
  return length && unit ? `${trimDecimal(length)} ${unit} bar` : 'bar'
}

/** Area of one piece from the typed size, as the server works it out (sq ft, 2 dp). */
export function areaSqft(width: string, height: string, unit: 'cm' | 'in'): string | null {
  const w = Number(width)
  const h = Number(height)
  if (!(w > 0 && h > 0)) return null
  const inches = unit === 'in' ? 1 : 1 / 2.54
  return trimDecimal(((w * inches * h * inches) / 144).toFixed(2))
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

/** "Sliding window" or "Sliding window + 2 more" for a quotation's items. */
export function itemsTitle(items: { product_name: string }[]): string {
  const [first, ...rest] = items
  return rest.length ? `${first.product_name} + ${rest.length} more` : first.product_name
}

/** "48 × 48 in · qty 2" for one item, or "3 items · 5 pieces" for several. */
export function itemsDetail(
  items: { input_width: string; input_height: string; input_unit: string; quantity: number }[],
): string {
  if (items.length === 1) {
    const [i] = items
    return `${trimDecimal(i.input_width)} × ${trimDecimal(i.input_height)} ${i.input_unit} · qty ${i.quantity}`
  }
  const pieces = items.reduce((n, i) => n + i.quantity, 0)
  return `${items.length} items · ${pieces} pieces`
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
