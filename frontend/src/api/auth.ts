import { api, ApiError } from './client'

export type Role = 'user' | 'admin' | 'super_admin'

export interface Me {
  id: string
  email: string
  role: Role
  has_profile: boolean
}

export const STAFF_ROLES: readonly Role[] = ['admin', 'super_admin']

/** The signed-in user, or null when not signed in. */
export async function getMe(): Promise<Me | null> {
  try {
    return await api<Me>('/auth/me')
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null
    throw err
  }
}

export function staffLogin(email: string, password: string): Promise<Me> {
  return api<Me>('/auth/staff/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export function logout(): Promise<void> {
  return api<void>('/auth/logout', { method: 'POST' })
}

/** Google sign-in is a full-page redirect handled by the backend. */
export const GOOGLE_LOGIN_URL = '/api/v1/auth/google/login'
