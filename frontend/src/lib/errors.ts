import { ApiError } from '../api/client'

/** A message safe to show a user for any thrown error. */
export function messageOf(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return 'Your session has ended. Please sign in again.'
    if (err.status === 403) return 'You are not allowed to do that.'
    return err.message
  }
  return 'Something went wrong. Please try again.'
}
