// What is being quoted (product, size, quantity, choices, add-ons): shared by the customer's form
// and the staff walk-in form. Mirrors QuotationIn in backend/app/schemas/quotation.py.

import { z } from 'zod'

import type { CatalogProduct, LengthUnit, QuotationRequest } from '../../api/quotations'

const MM_PER: Record<LengthUnit, number> = { cm: 10, in: 25.4 }

/** Display-only conversion for the allowed range hint. The server converts authoritatively. */
export function fromMm(mm: number, unit: LengthUnit): string {
  return String(Math.round((mm / MM_PER[unit]) * 10) / 10)
}

const size = z.string().trim().regex(/^\d{1,5}(\.\d{1,2})?$/, 'Enter a number like 120 or 120.5')

export const quoteItemSchema = z.object({
  product_id: z.string().min(1, 'Choose a product'),
  unit: z.enum(['cm', 'in']),
  width: size,
  height: size,
  quantity: z.number({ error: 'Enter a quantity' }).int().min(1).max(100),
  /** Picked choice per group id, e.g. { <glass group id>: <reflective id> } */
  choices: z.record(z.string(), z.string()),
  /** Ticked add-ons; unticked by default */
  option_ids: z.array(z.string()).max(10),
})
export type QuoteItemValues = z.input<typeof quoteItemSchema>

export const EMPTY_QUOTE_ITEM: QuoteItemValues = {
  product_id: '',
  unit: 'cm',
  width: '',
  height: '',
  quantity: 1,
  choices: {},
  option_ids: [],
}

/** The group a valid choice is still missing for (the form pre-selects one, so rarely). */
export function missingChoice(values: QuoteItemValues, product: CatalogProduct): string | null {
  const group = product.choice_groups.find((g) => !g.choices.some((c) => c.id === values.choices[g.id]))
  return group ? group.name : null
}

/**
 * The request body: one choice per group plus the ticked add-ons, keeping only ids of `product`
 * (ticks and picks may remain from a product chosen earlier).
 */
export function toRequest(values: z.output<typeof quoteItemSchema>, product: CatalogProduct): QuotationRequest {
  const picked = product.choice_groups.map((g) => values.choices[g.id]).filter((id) => id !== undefined)
  const addOns = values.option_ids.filter((id) => product.options.some((o) => o.id === id))
  return {
    product_id: values.product_id,
    unit: values.unit,
    width: values.width,
    height: values.height,
    quantity: values.quantity,
    option_ids: [...picked, ...addOns],
  }
}

function rangeError(value: string, unit: LengthUnit, min: number, max: number, what: string) {
  const mm = Number(value) * MM_PER[unit]
  if (Number.isNaN(mm) || (mm >= min - 0.5 && mm <= max + 0.5)) return null
  return `${what} must be ${fromMm(min, unit)}–${fromMm(max, unit)} ${unit}`
}

/** Quick check of the product's size limits before sending (the server checks again). */
export function sizeErrors(values: QuoteItemValues, product: CatalogProduct) {
  return {
    width: rangeError(values.width, values.unit, product.min_width_mm, product.max_width_mm, 'Width'),
    height: rangeError(values.height, values.unit, product.min_height_mm, product.max_height_mm, 'Height'),
  }
}
