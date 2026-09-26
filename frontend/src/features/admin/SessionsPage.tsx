import { LogOut, Monitor, MonitorSmartphone, RefreshCw, Smartphone } from 'lucide-react'
import { useState } from 'react'
import { useLoaderData, useRevalidator } from 'react-router'

import { adminApi, type ActiveSession } from '../../api/admin'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card, EmptyState, PageHeader } from '../../components/ui/Card'
import { messageOf } from '../../lib/errors'
import { confirmAction, toast } from '../../stores/feedback'
import type { sessionsLoader } from './loaders'

const ROLE_LABEL = { user: 'Customer', admin: 'Admin', super_admin: 'Super admin' } as const
const TIME = new Intl.DateTimeFormat('en-PH', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Manila' })

/** "Mozilla/5.0 (Windows NT 10.0...) Chrome/..." -> "Chrome on Windows" (best effort, display only). */
function device(ua: string | null): { label: string; mobile: boolean } {
  if (!ua) return { label: 'Unknown device', mobile: false }
  const browser = /Edg\//.test(ua) ? 'Edge' : /Chrome\//.test(ua) ? 'Chrome' : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : 'Browser'
  const os = /Windows/.test(ua) ? 'Windows' : /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS' : /Mac OS/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : ''
  return { label: os ? `${browser} on ${os}` : browser, mobile: /Android|iPhone|iPad|Mobile/.test(ua) }
}

export function SessionsPage() {
  const { me, sessions } = useLoaderData<typeof sessionsLoader>()
  const { revalidate, state } = useRevalidator()
  const [busyUser, setBusyUser] = useState<string | null>(null)

  async function signOut(s: ActiveSession) {
    const ok = await confirmAction({
      title: 'Sign out everywhere?',
      message: `${s.email} will be signed out on all their devices.`,
      confirmLabel: 'Sign out',
    })
    if (!ok) return
    setBusyUser(s.user_id)
    try {
      await adminApi.signOutUser(s.user_id)
      toast.success(`${s.email} signed out.`)
      revalidate()
    } catch (err) {
      toast.error(messageOf(err))
    } finally {
      setBusyUser(null)
    }
  }

  return (
    <>
      <PageHeader
        title="Active sessions"
        description="People signed in right now. Staff idle for 30 minutes and customers idle for 8 hours are signed out automatically."
        icon={MonitorSmartphone}
        actions={
          <Button variant="secondary" icon={RefreshCw} loading={state === 'loading'} onClick={revalidate} className="w-full sm:w-auto">
            Refresh
          </Button>
        }
      />
      <Card className="p-2 sm:p-2">
        {sessions.length === 0 ? (
          <EmptyState icon={MonitorSmartphone} title="Nobody is signed in" />
        ) : (
          <ul className="divide-y divide-line">
            {sessions.map((s) => {
              const d = device(s.user_agent)
              const Icon = d.mobile ? Smartphone : Monitor
              return (
                <li key={s.id} className="flex flex-col gap-3 px-3 py-3 sm:flex-row sm:items-center">
                  <div className="flex min-w-0 flex-1 items-start gap-3">
                    <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand">
                      <Icon className="size-5" aria-hidden />
                    </span>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate font-medium">{s.email}</span>
                        <Badge tone={s.role === 'user' ? 'neutral' : 'brand'}>{ROLE_LABEL[s.role]}</Badge>
                      </div>
                      <p className="text-sm text-muted">
                        {d.label}
                        {s.ip && ` · ${s.ip}`}
                      </p>
                      <p className="text-xs text-muted">
                        Signed in {TIME.format(new Date(s.created_at))} · last active {TIME.format(new Date(s.last_seen_at))}
                      </p>
                    </div>
                  </div>
                  {s.user_id === me.id ? (
                    <Badge tone="success">This is you</Badge>
                  ) : (
                    <Button variant="secondary" size="sm" icon={LogOut} loading={busyUser === s.user_id} onClick={() => signOut(s)}>
                      Sign out
                    </Button>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </Card>
    </>
  )
}
