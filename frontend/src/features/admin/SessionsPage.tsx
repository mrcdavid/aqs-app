import { useState } from 'react'
import { useLoaderData, useRevalidator } from 'react-router'

import { adminApi } from '../../api/admin'
import { Card, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { linkButtonClass, secondaryButtonClass } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import type { sessionsLoader } from './loaders'

const ROLE_LABEL = { user: 'Customer', admin: 'Admin', super_admin: 'Super admin' } as const

const TIME = new Intl.DateTimeFormat('en-PH', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Manila' })

/** "Mozilla/5.0 (Windows NT 10.0...) Chrome/..." -> "Chrome on Windows" (best effort, display only). */
function device(ua: string | null): string {
  if (!ua) return 'Unknown device'
  const browser = /Edg\//.test(ua) ? 'Edge' : /Chrome\//.test(ua) ? 'Chrome' : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : 'Browser'
  const os = /Windows/.test(ua) ? 'Windows' : /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS' : /Mac OS/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : ''
  return os ? `${browser} on ${os}` : browser
}

export function SessionsPage() {
  const { me, sessions } = useLoaderData<typeof sessionsLoader>()
  const { revalidate } = useRevalidator()
  const [error, setError] = useState<string | null>(null)

  async function signOut(userId: string, email: string) {
    if (!window.confirm(`Sign ${email} out on all devices?`)) return
    setError(null)
    try {
      await adminApi.signOutUser(userId)
      revalidate()
    } catch (err) {
      setError(messageOf(err))
    }
  }

  return (
    <>
      <PageHeader
        title="Active sessions"
        description="People signed in right now (staff idle 30 min and customers idle 8 h are signed out automatically)."
      />
      <div>
        <button type="button" onClick={revalidate} className={secondaryButtonClass}>
          Refresh
        </button>
      </div>
      <Card>
        <ErrorBanner message={error} />
        {sessions.length === 0 ? (
          <p className="text-muted">Nobody is signed in.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-brand-100 text-muted">
                <tr>
                  <th className="py-2 pr-4 font-medium">User</th>
                  <th className="py-2 pr-4 font-medium">Device</th>
                  <th className="py-2 pr-4 font-medium">Signed in</th>
                  <th className="py-2 pr-4 font-medium">Last active</th>
                  <th className="py-2 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.id} className="border-b border-brand-50 last:border-0">
                    <td className="py-2 pr-4">
                      <div>{s.email}</div>
                      <div className="text-xs text-muted">{ROLE_LABEL[s.role]}</div>
                    </td>
                    <td className="py-2 pr-4">
                      <div>{device(s.user_agent)}</div>
                      {s.ip && <div className="text-xs text-muted">{s.ip}</div>}
                    </td>
                    <td className="py-2 pr-4 whitespace-nowrap">{TIME.format(new Date(s.created_at))}</td>
                    <td className="py-2 pr-4 whitespace-nowrap">{TIME.format(new Date(s.last_seen_at))}</td>
                    <td className="py-2 text-right">
                      {s.user_id === me.id ? (
                        <span className="text-xs text-muted">you</span>
                      ) : (
                        <button type="button" className={linkButtonClass} onClick={() => signOut(s.user_id, s.email)}>
                          Sign out
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
