// Route loaders that redirect based on who is signed in.
// These are for UX only; the backend enforces every permission.

import { redirect } from 'react-router'

import { getMe, STAFF_ROLES, type Me, type Role } from '../api/auth'

export function homeFor(me: Me): string {
  if (STAFF_ROLES.includes(me.role)) return '/admin'
  return me.has_profile ? '/app/quotations' : '/app/profile'
}

export async function requireRole(roles: readonly Role[]): Promise<Me> {
  const me = await getMe()
  if (!me) throw redirect(roles.includes('user') ? '/login' : '/staff/login')
  if (!roles.includes(me.role)) throw redirect(homeFor(me))
  return me
}

/** For login pages: already signed-in users go straight to their home page. */
export async function redirectIfSignedIn(): Promise<null> {
  const me = await getMe()
  if (me) throw redirect(homeFor(me))
  return null
}

/** Root loader: the signed-in user (or null) for the header and child pages. */
export function rootLoader(): Promise<Me | null> {
  return getMe()
}
