import { z } from 'zod'

// Mirrors backend/app/schemas/. The server re-validates everything; this is for fast feedback.

export const staffLoginSchema = z.object({
  email: z.email('Enter a valid email'),
  password: z.string().min(1, 'Enter your password').max(128),
})
export type StaffLoginInput = z.infer<typeof staffLoginSchema>

export const profileSchema = z.object({
  full_name: z.string().trim().min(2, 'Enter your full name').max(120),
  age: z.number({ error: 'Enter your age' }).int().min(18, 'Must be 18 or older').max(120),
  contact_number: z
    .string()
    .trim()
    .regex(/^(09|\+639)\d{9}$/, 'Use 09XXXXXXXXX or +639XXXXXXXXX'),
  address_line: z.string().trim().min(5, 'Enter your street address').max(200),
  city: z.string().trim().min(2, 'Enter your city or municipality').max(80),
  province: z.string().trim().min(2, 'Enter your province').max(80),
})
export type ProfileInput = z.infer<typeof profileSchema>
