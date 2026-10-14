import { z } from 'zod'

// Mirrors backend/app/schemas/. The server re-validates everything; this is for fast feedback.

// ---------- shared field rules (backend/app/schemas/common.py) ----------

/** PH mobile: 09XXXXXXXXX or +639XXXXXXXXX. Spaces, dashes, dots and brackets are ignored. */
export const phMobile = z
  .string()
  .trim()
  .transform((v) => v.replace(/[\s().-]/g, ''))
  .pipe(z.string().regex(/^(09|\+639)\d{9}$/, 'Enter a PH mobile number, e.g. 0917 123 4567 or +63 917 123 4567'))

const LETTERS = "Use letters only (spaces and . , ' - are fine)"
const NAME = /^\p{L}[\p{L}\p{M} .,'’-]*$/u
const PLACE = /^\p{L}[\p{L}\p{M} .,'’()-]*$/u

/** A person's name: letters, spaces and . , ' - (e.g. Ma. Cristina O'Neil-Reyes). */
export const personName = (required: string) => z.string().trim().min(2, required).max(120).regex(NAME, LETTERS)

/** Same rule as personName, but may be left empty. */
export const optionalPersonName = z
  .string()
  .trim()
  .max(120)
  .refine((v) => v === '' || NAME.test(v), LETTERS)

/** City, municipality or province: letters, spaces and . , ' - ( ). */
export const placeName = (required: string) => z.string().trim().min(2, required).max(80).regex(PLACE, LETTERS)

/** Optional email: blank is fine, anything else must be a valid address. */
export const optionalEmail = z
  .string()
  .trim()
  .max(254)
  .refine((v) => v === '' || z.email().safeParse(v).success, 'Enter a valid email, or leave it blank')

// ---------- forms ----------

export const staffLoginSchema = z.object({
  email: z.email('Enter a valid email'),
  password: z.string().min(1, 'Enter your password').max(128),
})
export type StaffLoginInput = z.infer<typeof staffLoginSchema>

export const profileSchema = z.object({
  full_name: personName('Enter your full name'),
  age: z.number({ error: 'Enter your age' }).int().min(18, 'Must be 18 or older').max(120),
  contact_number: phMobile,
  address_line: z.string().trim().min(5, 'Enter your street address').max(200),
  city: placeName('Enter your city or municipality'),
  province: placeName('Enter your province'),
})
export type ProfileInput = z.input<typeof profileSchema>
