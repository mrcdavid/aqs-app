// What is being quoted: one or more items (product, size, quantity, choices, add-ons). Shared by
// the customer's form and the staff walk-in form. Mirrors QuotationIn in
// backend/app/schemas/quotation.py.

import { z } from 'zod'

import type { CatalogProduct, LengthUnit, QuotationItemRequest, QuotationRequest } from '../../api/quotations'

export const MAX_ITEMS = 20 // per quotation (backend: models/quotation.py)

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

export const quoteFormSchema = z.object({ items: z.array(quoteItemSchema).min(1).max(MAX_ITEMS) })
export type QuoteFormValues = z.input<typeof quoteFormSchema>

export const EMPTY_QUOTE_ITEM: QuoteItemValues = {
  product_id: '',
  unit: 'cm',
  width: '',
  height: '',
  quantity: 1,
  choices: {},
  option_ids: [],
}

export const EMPTY_QUOTE_FORM: QuoteFormValues = { items: [EMPTY_QUOTE_ITEM] }

/** A problem with one item: shown on its width/height field, or above the form (field null). */
export interface ItemIssue {
  index: number
  field: 'width' | 'height' | null
  message: string
}

function rangeError(value: string, unit: LengthUnit, min: number, max: number, what: string) {
  const mm = Number(value) * MM_PER[unit]
  if (Number.isNaN(mm) || (mm >= min - 0.5 && mm <= max + 0.5)) return null
  return `${what} must be ${fromMm(min, unit)}–${fromMm(max, unit)} ${unit}`
}

/** Quick checks before sending (the server checks everything again): sizes and choices. */
export function checkItems(items: QuoteItemValues[], products: CatalogProduct[]): ItemIssue[] {
  const issues: ItemIssue[] = []
  items.forEach((item, index) => {
    const product = products.find((p) => p.id === item.product_id)
    if (!product) {
      issues.push({ index, field: null, message: `Item ${index + 1}: choose a product.` })
      return
    }
    const width = rangeError(item.width, item.unit, product.min_width_mm, product.max_width_mm, 'Width')
    const height = rangeError(item.height, item.unit, product.min_height_mm, product.max_height_mm, 'Height')
    if (width) issues.push({ index, field: 'width', message: width })
    if (height) issues.push({ index, field: 'height', message: height })
    // The form pre-selects a choice, so this is rare (e.g. a choice removed meanwhile).
    const group = product.choice_groups.find((g) => !g.choices.some((c) => c.id === item.choices[g.id]))
    if (group) issues.push({ index, field: null, message: `Item ${index + 1}: choose an option for ${group.name}.` })
  })
  return issues
}

/** One item for the request: its product's choices and add-ons only (picks may remain from a product chosen earlier). */
function itemRequest(item: z.output<typeof quoteItemSchema>, product: CatalogProduct): QuotationItemRequest {
  const picked = product.choice_groups.map((g) => item.choices[g.id]).filter((id) => id !== undefined)
  const addOns = item.option_ids.filter((id) => product.options.some((o) => o.id === id))
  return {
    product_id: item.product_id,
    unit: item.unit,
    width: item.width,
    height: item.height,
    quantity: item.quantity,
    option_ids: [...picked, ...addOns],
  }
}

/** The request body. Call after checkItems found nothing, so every product exists. */
export function toRequest(items: z.output<typeof quoteItemSchema>[], products: CatalogProduct[]): QuotationRequest {
  return {
    items: items.map((item) => itemRequest(item, products.find((p) => p.id === item.product_id) as CatalogProduct)),
  }
}
