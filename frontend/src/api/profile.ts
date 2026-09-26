import type { ProfileInput } from '../lib/schemas'
import { api, ApiError } from './client'

export type Profile = ProfileInput

export async function getProfile(): Promise<Profile | null> {
  try {
    return await api<Profile>('/profile')
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

export function saveProfile(profile: ProfileInput): Promise<Profile> {
  return api<Profile>('/profile', { method: 'PUT', body: JSON.stringify(profile) })
}
