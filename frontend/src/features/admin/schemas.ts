import { z } from 'zod'

import { optionalEmail, optionalPersonName, personName, phMobile, placeName } from '../../lib/schemas'

// Mirrors backend/app/schemas/catalog.py. Decimals stay strings end to end.

const code = z
  .string()
  .trim()
  .transform((v) => v.toUpperCase())
  .pipe(z.string().regex(/^[A-Z0-9][A-Z0-9-]{1,29}$/, '2–30 letters, digits or dashes'))
const name = z.string().trim().min(2, 'At least 2 characters').max(120)
const price = z
  .string()
  .trim()
  .regex(/^\d{1,10}(\.\d{1,2})?$/, 'Amount like 850 or 850.50')
const percent = z
  .string()
  .trim()
  .regex(/^\d{1,3}(\.\d{1,2})?$/, 'Percent like 12 or 12.5')
  .refine((v) => Number(v) <= 100, 'At most 100')
const mm = z.number({ error: 'Enter a number' }).int().min(1).max(20000)

export const unitSchema = z.enum(['sqm', 'lm', 'piece'])

/** Material or labour rate (labour rates simply ignore `category`). */
export const priceItemSchema = z.object({
  code,
  name,
  category: z.enum(['glass', 'aluminum', 'metal', 'hardware', 'other']),
  unit: unitSchema,
  price,
})
export type PriceItemForm = z.output<typeof priceItemSchema>

export const productSchema = z
  .object({
    code,
    name,
    category: z.enum(['sliding_window', 'sliding_door', 'window_grill', 'other']),
    description: z.string().trim().max(2000),
    min_width_mm: mm,
    max_width_mm: mm,
    min_height_mm: mm,
    max_height_mm: mm,
  })
  .refine((p) => p.min_width_mm <= p.max_width_mm, {
    path: ['max_width_mm'],
    message: 'Must be ≥ minimum width',
  })
  .refine((p) => p.min_height_mm <= p.max_height_mm, {
    path: ['max_height_mm'],
    message: 'Must be ≥ minimum height',
  })
export type ProductForm = z.input<typeof productSchema>

export const EMPTY_PRODUCT: ProductForm = {
  code: '',
  name: '',
  category: 'sliding_window',
  description: '',
  min_width_mm: 300,
  max_width_mm: 3000,
  min_height_mm: 300,
  max_height_mm: 2500,
}

export const componentSchema = z.object({
  item: z.string().min(1, 'Choose a material or labour rate'), // "material:<id>" | "labor:<id>"
  basis: z.enum(['area', 'perimeter', 'width', 'height', 'fixed']),
  factor: z
    .string()
    .trim()
    .regex(/^\d{1,6}(\.\d{1,4})?$/, 'Number like 1 or 2.5')
    .refine((v) => Number(v) > 0, 'Must be more than 0'),
  waste_percent: percent,
  label: z.string().trim().max(120),
  /** '' = always included, else the add-on's id */
  option_id: z.string(),
})
export type ComponentForm = z.input<typeof componentSchema>

/** An optional add-on of a product. Mirrors OptionIn in backend/app/schemas/catalog.py. */
export const optionSchema = z.object({
  name: z.string().trim().min(2, 'At least 2 characters').max(80),
  description: z.string().trim().max(300),
})
export type OptionForm = z.input<typeof optionSchema>

export const previewSchema = z.object({
  width: z.string().trim().regex(/^\d{1,5}(\.\d{1,2})?$/, 'Enter a size'),
  height: z.string().trim().regex(/^\d{1,5}(\.\d{1,2})?$/, 'Enter a size'),
  unit: z.enum(['cm', 'in']),
  quantity: z.number().int().min(1).max(100),
})
export type PreviewForm = z.input<typeof previewSchema>

export const settingsSchema = z.object({
  markup_percent: z
    .string()
    .trim()
    .regex(/^\d{1,3}(\.\d{1,2})?$/, 'Percent like 20 or 20.5')
    .refine((v) => Number(v) <= 500, 'At most 500'),
  vat_percent: percent,
  currency: z
    .string()
    .trim()
    .transform((v) => v.toUpperCase())
    .pipe(z.string().regex(/^[A-Z]{3}$/, '3-letter code like PHP')),
  quote_validity_days: z.number({ error: 'Enter a number of days' }).int().min(1).max(365),
  business_name: z.string().trim().min(2, 'Enter your business name').max(120),
  business_address: z.string().trim().max(300),
  business_contact: z.string().trim().max(120),
  quote_terms: z.string().trim().max(4000),
  rounding_step: z
    .string()
    .trim()
    .regex(/^\d{1,6}(\.\d{1,2})?$/, 'Amount like 100, or 0 for no rounding')
    .refine((v) => Number(v) <= 100000, 'At most 100,000'),
  owner_name: optionalPersonName,
})
export type SettingsForm = z.input<typeof settingsSchema>

/** A walk-in client typed in by staff. Mirrors ClientIn in backend/app/schemas/quotation.py. */
export const walkInClientSchema = z.object({
  full_name: personName("Enter the client's full name"),
  contact_number: phMobile,
  email: optionalEmail,
  address_line: z.string().trim().min(5, 'Enter the street address').max(200),
  city: placeName('Enter the city or municipality'),
  province: placeName('Enter the province'),
})
export type WalkInClientForm = z.input<typeof walkInClientSchema>

export const EMPTY_WALK_IN_CLIENT: WalkInClientForm = {
  full_name: '',
  contact_number: '',
  email: '',
  address_line: '',
  city: '',
  province: '',
}
