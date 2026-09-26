import { useState } from 'react'
import { Form, Link, useLoaderData, useLocation } from 'react-router'

import { adminApi, type AuditEntry } from '../../api/admin'
import { Card, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { buttonClass, Field, inputClass, secondaryButtonClass } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import type { auditLogLoader } from './loaders'

// Action prefixes written by the backend (services/audit.record callers).
const ACTION_GROUPS = [
  ['', 'All actions'],
  ['login', 'Logins'],
  ['user', 'Users'],
  ['profile', 'Profiles'],
  ['quotation', 'Quotations'],
  ['product', 'Products & templates'],
  ['material', 'Materials'],
  ['labor_rate', 'Labour rates'],
  ['pricing_settings', 'Settings'],
] as const

const TIME_FORMAT = new Intl.DateTimeFormat('en-PH', {
  dateStyle: 'medium',
  timeStyle: 'medium',
  timeZone: 'Asia/Manila',
})

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
  const [error, setError] = useState<string | null>(null)

  const extra = more?.search === location.search ? more : undefined
  const items = [...page.items, ...(extra?.items ?? [])]
  const next = extra ? extra.next : page.next_before_id

  async function loadMore() {
    if (next === null) return
    setLoading(true)
    setError(null)
    try {
      const older = await adminApi.auditLog({ ...filters, before_id: next })
      setMore({ search: location.search, items: [...(extra?.items ?? []), ...older.items], next: older.next_before_id })
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Audit log"
        description="Every login, price change, approval and setting change. Entries can't be edited or deleted."
      />

      <Card>
        <Form method="get" className="flex flex-wrap items-end gap-3">
          <Field label="Action" htmlFor="a-action">
            <select id="a-action" name="action" defaultValue={filters.action} className={inputClass}>
              {ACTION_GROUPS.map(([value, label]) => (
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
          <button type="submit" className={buttonClass}>
            Filter
          </button>
          {location.search && (
            <Link to="/admin/audit-log" className={secondaryButtonClass}>
              Clear
            </Link>
          )}
        </Form>
      </Card>

      <Card>
        <ErrorBanner message={error} />
        {items.length === 0 ? (
          <p className="text-muted">No entries match these filters.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-brand-100 text-muted">
                <tr>
                  <th className="py-2 pr-4 font-medium">When</th>
                  <th className="py-2 pr-4 font-medium">Who</th>
                  <th className="py-2 pr-4 font-medium">Action</th>
                  <th className="py-2 font-medium">Details</th>
                </tr>
              </thead>
              <tbody>
                {items.map((e) => {
                  const summary = summarize(e.details)
                  return (
                    <tr key={e.id} className="border-b border-brand-50 align-top last:border-0">
                      <td className="py-2 pr-4 whitespace-nowrap tabular-nums">
                        {TIME_FORMAT.format(new Date(e.created_at))}
                      </td>
                      <td className="py-2 pr-4">
                        <div>{e.actor_email ?? <span className="text-muted">anonymous</span>}</div>
                        {e.ip && <div className="text-xs text-muted">{e.ip}</div>}
                      </td>
                      <td className="py-2 pr-4 font-mono text-xs whitespace-nowrap">{e.action}</td>
                      <td className="py-2">
                        {summary && <div className="max-w-md break-words">{summary}</div>}
                        {Object.keys(e.details).length > 0 && (
                          <details className="text-xs text-muted">
                            <summary className="cursor-pointer">Full details</summary>
                            <pre className="mt-1 max-w-md overflow-x-auto rounded bg-brand-50 p-2">
                              {JSON.stringify({ entity: e.entity, entity_id: e.entity_id, ...e.details }, null, 2)}
                            </pre>
                          </details>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        {next !== null && (
          <div className="mt-4">
            <button type="button" onClick={loadMore} disabled={loading} className={secondaryButtonClass}>
              {loading ? 'Loading…' : 'Load more'}
            </button>
          </div>
        )}
      </Card>
    </>
  )
}
