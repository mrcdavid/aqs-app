import {
  Boxes,
  ChevronDown,
  FileText,
  Filter,
  HardHat,
  LogIn,
  Package,
  ScrollText,
  Settings,
  UserRound,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'
import { Form, useLoaderData, useLocation } from 'react-router'

import { adminApi, type AuditEntry } from '../../api/admin'
import { Button, ButtonLink } from '../../components/ui/Button'
import { Card, EmptyState, PageHeader } from '../../components/ui/Card'
import { Field, inputClass } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { toast } from '../../stores/feedback'
import type { auditLogLoader } from './loaders'

// Action prefixes written by the backend (services/audit.record callers).
const ACTION_GROUPS: { value: string; label: string; icon: LucideIcon }[] = [
  { value: '', label: 'All actions', icon: ScrollText },
  { value: 'login', label: 'Logins', icon: LogIn },
  { value: 'user', label: 'Users', icon: Users },
  { value: 'profile', label: 'Profiles', icon: UserRound },
  { value: 'quotation', label: 'Quotations', icon: FileText },
  { value: 'product', label: 'Products & templates', icon: Package },
  { value: 'material', label: 'Materials', icon: Boxes },
  { value: 'labor_rate', label: 'Labour rates', icon: HardHat },
  { value: 'pricing_settings', label: 'Settings', icon: Settings },
]

function iconFor(action: string): LucideIcon {
  return ACTION_GROUPS.find((g) => g.value && action.startsWith(g.value))?.icon ?? ScrollText
}

const TIME_FORMAT = new Intl.DateTimeFormat('en-PH', { dateStyle: 'medium', timeStyle: 'medium', timeZone: 'Asia/Manila' })

/** Short, readable summary of an entry's details; the full JSON is one click away. */
function summarize(details: Record<string, unknown>): string {
  const changes = details.changes as Record<string, [unknown, unknown]> | undefined
  if (changes) {
    return Object.entries(changes)
      .map(([field, [from, to]]) => `${field}: ${String(from)} → ${String(to)}`)
      .join(', ')
  }
  return Object.entries(details)
    .filter(([, v]) => typeof v !== 'object')
    .map(([k, v]) => `${k}: ${String(v)}`)
    .join(', ')
}

export function AuditLogPage() {
  const { filters, page } = useLoaderData<typeof auditLogLoader>()
  const location = useLocation()
  // Older pages loaded with "Load more"; tied to the current filters so a new search starts over.
  const [more, setMore] = useState<{ search: string; items: AuditEntry[]; next: number | null }>()
  const [loading, setLoading] = useState(false)

  const extra = more?.search === location.search ? more : undefined
  const items = [...page.items, ...(extra?.items ?? [])]
  const next = extra ? extra.next : page.next_before_id

  async function loadMore() {
    if (next === null) return
    setLoading(true)
    try {
      const older = await adminApi.auditLog({ ...filters, before_id: next })
      setMore({ search: location.search, items: [...(extra?.items ?? []), ...older.items], next: older.next_before_id })
    } catch (err) {
      toast.error(messageOf(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Audit log"
        description="Every login, price change, approval and setting change. Entries can't be edited or deleted."
        icon={ScrollText}
      />

      <Card>
        <Form method="get" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[1fr_1fr_auto_auto_auto] xl:items-end">
          <Field label="Action" htmlFor="a-action">
            <select id="a-action" name="action" defaultValue={filters.action} className={inputClass}>
              {ACTION_GROUPS.map(({ value, label }) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Person (email contains)" htmlFor="a-actor">
            <input id="a-actor" name="actor" defaultValue={filters.actor} maxLength={254} className={inputClass} />
          </Field>
          <Field label="From" htmlFor="a-from">
            <input id="a-from" type="date" name="date_from" defaultValue={filters.date_from} className={inputClass} />
          </Field>
          <Field label="To" htmlFor="a-to">
            <input id="a-to" type="date" name="date_to" defaultValue={filters.date_to} className={inputClass} />
          </Field>
          <div className="flex gap-2 sm:col-span-2 xl:col-span-1">
            <Button type="submit" icon={Filter} className="flex-1 xl:flex-none">
              Filter
            </Button>
            {location.search && (
              <ButtonLink to="/admin/audit-log" variant="secondary" icon={X} className="flex-1 xl:flex-none">
                Clear
              </ButtonLink>
            )}
          </div>
        </Form>
      </Card>

      <Card className="p-2 sm:p-2">
        {items.length === 0 ? (
          <EmptyState icon={ScrollText} title="No entries match these filters" />
        ) : (
          <ol className="divide-y divide-line">
            {items.map((e) => {
              const Icon = iconFor(e.action)
              const summary = summarize(e.details)
              const failed = e.action.includes('failed') || e.action.includes('rejected') || e.action.includes('deleted')
              return (
                <li key={e.id} className="flex gap-3 px-3 py-3">
                  <span
                    className={`grid size-9 shrink-0 place-items-center rounded-xl ${
                      failed ? 'bg-danger-soft text-danger' : 'bg-brand-soft text-brand'
                    }`}
                  >
                    <Icon className="size-[18px]" aria-hidden />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                      <span className="font-mono text-xs font-medium">{e.action}</span>
                      <time className="text-xs text-muted tabular-nums" dateTime={e.created_at}>
                        {TIME_FORMAT.format(new Date(e.created_at))}
                      </time>
                    </div>
                    <p className="text-sm">
                      {e.actor_email ?? <span className="text-muted">anonymous</span>}
                      {e.ip && <span className="text-muted"> · {e.ip}</span>}
                    </p>
                    {summary && <p className="mt-0.5 text-sm break-words text-muted">{summary}</p>}
                    {Object.keys(e.details).length > 0 && (
                      <details className="group mt-1 text-xs text-muted">
                        <summary className="inline-flex cursor-pointer list-none items-center gap-1 hover:text-ink">
                          <ChevronDown className="size-3.5 transition group-open:rotate-180" aria-hidden />
                          Full details
                        </summary>
                        <pre className="mt-1 overflow-x-auto rounded-lg bg-surface-2 p-2">
                          {JSON.stringify({ entity: e.entity, entity_id: e.entity_id, ...e.details }, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                </li>
              )
            })}
          </ol>
        )}
        {next !== null && (
          <div className="p-3 text-center">
            <Button variant="secondary" icon={ChevronDown} loading={loading} onClick={loadMore}>
              Load more
            </Button>
          </div>
        )}
      </Card>
    </>
  )
}
