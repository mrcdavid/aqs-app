import { zodResolver } from '@hookform/resolvers/zod'
import { UserPlus } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Form, NavLink, useLoaderData, useRevalidator } from 'react-router'
import { z } from 'zod'

import { adminApi, type UserRow } from '../../api/admin'
import { Card, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { buttonClass, Field, inputClass, linkButtonClass, secondaryButtonClass } from '../../components/ui/Field'
import { messageOf } from '../../lib/errors'
import { formatDate } from '../../lib/format'
import type { usersLoader } from './loaders'

const TABS = [
  ['customers', 'Customers'],
  ['staff', 'Staff'],
  ['deleted', 'Deleted'],
  ['all', 'All'],
] as const

const ROLE_LABEL = { user: 'Customer', admin: 'Admin', super_admin: 'Super admin' } as const

const password = z.string().min(12, 'At least 12 characters').max(128)

const staffSchema = z
  .object({
    email: z.email('Enter a valid email'),
    role: z.enum(['admin', 'super_admin']),
    password,
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, { path: ['confirm'], message: "Passwords don't match" })
type StaffForm = z.input<typeof staffSchema>

function Status({ u }: { u: UserRow }) {
  const [label, cls] = u.deleted_at
    ? ['Deleted', 'bg-gray-100 text-gray-600']
    : !u.is_active
      ? ['Disabled', 'bg-red-50 text-red-700']
      : u.locked
        ? ['Locked', 'bg-amber-50 text-amber-800']
        : ['Active', 'bg-green-50 text-green-700']
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{label}</span>
}

function AddStaff({ onDone }: { onDone: () => void }) {
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState } = useForm<StaffForm>({
    resolver: zodResolver(staffSchema),
    defaultValues: { email: '', role: 'admin', password: '', confirm: '' },
  })
  const { errors, isSubmitting } = formState

  async function onSubmit(v: StaffForm) {
    setError(null)
    try {
      await adminApi.createStaff({ email: v.email, role: v.role, password: v.password })
      onDone()
    } catch (err) {
      setError(messageOf(err))
    }
  }

  return (
    <Card title="Add staff account">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <ErrorBanner message={error} />
        <p className="text-sm text-muted">
          Give the new staff member their password in person or by phone; they sign in at Staff login.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Email" htmlFor="s-email" error={errors.email?.message}>
            <input id="s-email" type="email" autoComplete="off" className={inputClass} {...register('email')} />
          </Field>
          <Field label="Role" htmlFor="s-role">
            <select id="s-role" className={inputClass} {...register('role')}>
              <option value="admin">Admin</option>
              <option value="super_admin">Super admin</option>
            </select>
          </Field>
          <Field label="Password" htmlFor="s-pw" hint="12+ characters, not a common password" error={errors.password?.message}>
            <input id="s-pw" type="password" autoComplete="new-password" className={inputClass} {...register('password')} />
          </Field>
          <Field label="Repeat password" htmlFor="s-pw2" error={errors.confirm?.message}>
            <input id="s-pw2" type="password" autoComplete="new-password" className={inputClass} {...register('confirm')} />
          </Field>
        </div>
        <button type="submit" disabled={isSubmitting} className={buttonClass}>
          Create account
        </button>
      </form>
    </Card>
  )
}

function ResetPassword({ user, onDone }: { user: UserRow; onDone: (error?: string) => void }) {
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const invalid = value.length > 0 && value.length < 12
  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={async (e) => {
        e.preventDefault()
        if (value.length < 12) return
        setBusy(true)
        try {
          await adminApi.resetPassword(user.id, value)
          onDone()
        } catch (err) {
          onDone(messageOf(err))
        } finally {
          setBusy(false)
        }
      }}
    >
      <label htmlFor={`pw-${user.id}`} className="sr-only">
        New password for {user.email}
      </label>
      <input
        id={`pw-${user.id}`}
        type="password"
        autoComplete="new-password"
        placeholder="New password (12+ characters)"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        aria-invalid={invalid}
        className={`${inputClass} w-64`}
      />
      <button type="submit" disabled={busy || value.length < 12} className={secondaryButtonClass}>
        Set password
      </button>
      <button type="button" onClick={() => onDone()} className={linkButtonClass}>
        Cancel
      </button>
    </form>
  )
}

export function UsersPage() {
  const { me, kind, q, users } = useLoaderData<typeof usersLoader>()
  const { revalidate } = useRevalidator()
  const isOwner = me.role === 'super_admin'
  const [adding, setAdding] = useState(false)
  const [resetting, setResetting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function act(fn: () => Promise<unknown>, question?: string) {
    if (question && !window.confirm(question)) return
    setError(null)
    try {
      await fn()
      revalidate()
    } catch (err) {
      setError(messageOf(err))
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <PageHeader
          title="Users"
          description={isOwner ? 'Manage customers and staff accounts.' : 'Customers and staff (view only).'}
        />
        {isOwner && !adding && (
          <button type="button" className={buttonClass} onClick={() => setAdding(true)}>
            <UserPlus className="size-4" aria-hidden />
            Add staff account
          </button>
        )}
      </div>

      {adding && (
        <AddStaff
          onDone={() => {
            setAdding(false)
            revalidate()
          }}
        />
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <nav aria-label="User type" className="flex gap-1 overflow-x-auto">
          {TABS.map(([value, label]) => (
            <NavLink
              key={value}
              to={`/admin/users?kind=${value}`}
              className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm ${
                kind === value ? 'bg-brand-600 text-white' : 'bg-white hover:bg-brand-100'
              }`}
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <Form method="get" className="flex gap-2" role="search">
          <input type="hidden" name="kind" value={kind} />
          <label htmlFor="u-q" className="sr-only">
            Search name or email
          </label>
          <input id="u-q" name="q" defaultValue={q} placeholder="Search name or email" maxLength={254} className={`${inputClass} w-56`} />
          <button type="submit" className={secondaryButtonClass}>
            Search
          </button>
        </Form>
      </div>

      <Card>
        <ErrorBanner message={error} />
        {users.length === 0 ? (
          <p className="text-muted">No users here.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-brand-100 text-muted">
                <tr>
                  <th className="py-2 pr-4 font-medium">User</th>
                  <th className="py-2 pr-4 font-medium">Role</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 pr-4 font-medium">Last login</th>
                  {isOwner && (
                    <th className="py-2 font-medium">
                      <span className="sr-only">Actions</span>
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const self = u.id === me.id
                  const staff = u.auth_provider === 'password'
                  const editable = isOwner && !self && !u.deleted_at
                  return (
                    <tr key={u.id} className="border-b border-brand-50 align-top last:border-0">
                      <td className="py-2 pr-4">
                        <div className="font-medium">
                          {u.full_name ?? u.email} {self && <span className="text-xs text-muted">(you)</span>}
                        </div>
                        {u.full_name && <div className="text-xs text-muted">{u.email}</div>}
                        {u.city && <div className="text-xs text-muted">{u.city}</div>}
                      </td>
                      <td className="py-2 pr-4 whitespace-nowrap">{ROLE_LABEL[u.role]}</td>
                      <td className="py-2 pr-4 whitespace-nowrap">
                        <Status u={u} />
                        {u.active_sessions > 0 && (
                          <div className="mt-1 flex items-center gap-1 text-xs text-green-700">
                            <span className="size-2 rounded-full bg-green-600" aria-hidden /> Online
                          </div>
                        )}
                      </td>
                      <td className="py-2 pr-4 whitespace-nowrap">
                        {u.last_login_at ? formatDate(u.last_login_at) : <span className="text-muted">Never</span>}
                      </td>
                      {isOwner && (
                        <td className="py-2">
                          {resetting === u.id ? (
                            <ResetPassword
                              user={u}
                              onDone={(err) => {
                                setResetting(null)
                                if (err) setError(err)
                                else revalidate()
                              }}
                            />
                          ) : (
                            editable && (
                              <div className="flex flex-wrap justify-end gap-x-1">
                                <button
                                  type="button"
                                  className={linkButtonClass}
                                  onClick={() =>
                                    act(
                                      () => adminApi.updateUser(u.id, { is_active: !u.is_active }),
                                      u.is_active ? `Disable ${u.email}? They'll be signed out.` : undefined,
                                    )
                                  }
                                >
                                  {u.is_active ? 'Disable' : u.locked ? 'Enable & unlock' : 'Enable'}
                                </button>
                                {staff && (
                                  <button
                                    type="button"
                                    className={linkButtonClass}
                                    onClick={() =>
                                      act(
                                        () =>
                                          adminApi.updateUser(u.id, {
                                            role: u.role === 'admin' ? 'super_admin' : 'admin',
                                          }),
                                        `Change ${u.email} to ${u.role === 'admin' ? 'super admin' : 'admin'}?`,
                                      )
                                    }
                                  >
                                    {u.role === 'admin' ? 'Make super admin' : 'Make admin'}
                                  </button>
                                )}
                                {staff && (
                                  <button type="button" className={linkButtonClass} onClick={() => setResetting(u.id)}>
                                    Reset password
                                  </button>
                                )}
                                {u.active_sessions > 0 && (
                                  <button
                                    type="button"
                                    className={linkButtonClass}
                                    onClick={() => act(() => adminApi.signOutUser(u.id), `Sign ${u.email} out everywhere?`)}
                                  >
                                    Sign out
                                  </button>
                                )}
                                <button
                                  type="button"
                                  className={`${linkButtonClass} text-red-700`}
                                  onClick={() =>
                                    act(
                                      () => adminApi.deleteUser(u.id),
                                      `Delete ${u.email}? They won't be able to sign in. Their quotations and history are kept.`,
                                    )
                                  }
                                >
                                  Delete
                                </button>
                              </div>
                            )
                          )}
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
