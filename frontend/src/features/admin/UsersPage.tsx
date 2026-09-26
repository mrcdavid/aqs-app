import { zodResolver } from '@hookform/resolvers/zod'
import {
  KeyRound,
  LogOut,
  Search,
  Shield,
  ShieldCheck,
  ShieldMinus,
  ShieldPlus,
  Trash2,
  UserCheck,
  UserPlus,
  UserRound,
  Users,
  UserX,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Form, Link, useLoaderData, useRevalidator } from 'react-router'
import { z } from 'zod'

import { adminApi, type UserRow } from '../../api/admin'
import { AccountBadge, Badge, OnlineDot } from '../../components/ui/Badge'
import { Button, IconButton } from '../../components/ui/Button'
import { Card, EmptyState, ErrorBanner, PageHeader } from '../../components/ui/Card'
import { Field, inputClass } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { messageOf } from '../../lib/errors'
import { formatDate } from '../../lib/format'
import { confirmAction, toast } from '../../stores/feedback'
import type { usersLoader } from './loaders'

const TABS = [
  { kind: 'customers', label: 'Customers', icon: UserRound },
  { kind: 'staff', label: 'Staff', icon: ShieldCheck },
  { kind: 'deleted', label: 'Deleted', icon: Trash2 },
  { kind: 'all', label: 'All', icon: Users },
] as const

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

const resetSchema = z
  .object({ password, confirm: z.string() })
  .refine((v) => v.password === v.confirm, { path: ['confirm'], message: "Passwords don't match" })
type ResetForm = z.input<typeof resetSchema>

function RoleBadge({ role }: { role: UserRow['role'] }) {
  if (role === 'super_admin')
    return (
      <Badge tone="brand" icon={ShieldCheck}>
        Super admin
      </Badge>
    )
  if (role === 'admin')
    return (
      <Badge tone="brand" icon={Shield}>
        Admin
      </Badge>
    )
  return (
    <Badge tone="neutral" icon={UserRound}>
      Customer
    </Badge>
  )
}

export function UsersPage() {
  const { me, kind, q, users } = useLoaderData<typeof usersLoader>()
  const { revalidate } = useRevalidator()
  const isOwner = me.role === 'super_admin'
  const [adding, setAdding] = useState(false)
  const [resetting, setResetting] = useState<UserRow | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  async function act(u: UserRow, confirm: Parameters<typeof confirmAction>[0] | null, fn: () => Promise<unknown>, done: string) {
    if (confirm && !(await confirmAction(confirm))) return
    setBusyId(u.id)
    try {
      await fn()
      toast.success(done)
      revalidate()
    } catch (err) {
      toast.error(messageOf(err))
    } finally {
      setBusyId(null)
    }
  }

  function actions(u: UserRow) {
    const staff = u.auth_provider === 'password'
    const busy = busyId === u.id
    const promote = u.role === 'admin'
    return (
      <div className="flex flex-wrap justify-end gap-1">
        {u.is_active ? (
          <IconButton
            icon={UserX}
            label={`Disable ${u.email}`}
            loading={busy}
            onClick={() =>
              act(
                u,
                { title: `Disable ${u.email}?`, message: 'They will be signed out right away and cannot sign in until you enable the account again.', confirmLabel: 'Disable account', tone: 'danger' },
                () => adminApi.updateUser(u.id, { is_active: false }),
                `${u.email} disabled.`,
              )
            }
          />
        ) : (
          <IconButton
            icon={UserCheck}
            tone="brand"
            label={u.locked ? `Enable and unlock ${u.email}` : `Enable ${u.email}`}
            loading={busy}
            onClick={() => act(u, null, () => adminApi.updateUser(u.id, { is_active: true }), `${u.email} enabled.`)}
          />
        )}
        {staff && (
          <IconButton
            icon={promote ? ShieldPlus : ShieldMinus}
            label={promote ? `Make ${u.email} a super admin` : `Make ${u.email} an admin`}
            disabled={busy}
            onClick={() =>
              act(
                u,
                {
                  title: promote ? 'Make super admin?' : 'Change to admin?',
                  message: promote
                    ? `${u.email} will be able to manage staff accounts and see active sessions. They will be signed out once.`
                    : `${u.email} will lose super admin powers. They will be signed out once.`,
                  confirmLabel: promote ? 'Make super admin' : 'Change to admin',
                },
                () => adminApi.updateUser(u.id, { role: promote ? 'super_admin' : 'admin' }),
                `${u.email} is now ${promote ? 'a super admin' : 'an admin'}.`,
              )
            }
          />
        )}
        {staff && <IconButton icon={KeyRound} label={`Reset password for ${u.email}`} disabled={busy} onClick={() => setResetting(u)} />}
        {u.active_sessions > 0 && (
          <IconButton
            icon={LogOut}
            label={`Sign ${u.email} out everywhere`}
            disabled={busy}
            onClick={() =>
              act(
                u,
                { title: 'Sign out everywhere?', message: `${u.email} will be signed out on all devices.`, confirmLabel: 'Sign out' },
                () => adminApi.signOutUser(u.id),
                `${u.email} signed out.`,
              )
            }
          />
        )}
        <IconButton
          icon={Trash2}
          tone="danger"
          label={`Delete ${u.email}`}
          disabled={busy}
          onClick={() =>
            act(
              u,
              {
                title: `Delete ${u.email}?`,
                message: "They won't be able to sign in any more. Their quotations and history are kept for your records.",
                confirmLabel: 'Delete account',
                tone: 'danger',
              },
              () => adminApi.deleteUser(u.id),
              `${u.email} deleted.`,
            )
          }
        />
      </div>
    )
  }

  return (
    <>
      <PageHeader
        title="Users"
        description={isOwner ? 'Manage customers and staff accounts.' : 'Customers and staff (view only).'}
        icon={Users}
        actions={
          isOwner && (
            <Button icon={UserPlus} onClick={() => setAdding(true)} className="w-full sm:w-auto">
              Add staff account
            </Button>
          )
        }
      />

      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <nav aria-label="User type" className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none]">
          {TABS.map(({ kind: k, label, icon: Icon }) => (
            <Link
              key={k}
              to={`/admin/users?kind=${k}`}
              aria-current={kind === k ? 'page' : undefined}
              className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-3.5 py-2 text-sm font-medium transition ${
                kind === k ? 'bg-brand-gradient text-white shadow-sm shadow-indigo-500/25' : 'border border-line bg-surface text-muted hover:text-ink'
              }`}
            >
              <Icon className="size-4" aria-hidden />
              {label}
            </Link>
          ))}
        </nav>
        <Form method="get" role="search" className="flex gap-2">
          <input type="hidden" name="kind" value={kind} />
          <div className="relative flex-1 xl:w-64">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input name="q" defaultValue={q} placeholder="Search name or email" aria-label="Search name or email" maxLength={254} className={`${inputClass} pl-9`} />
          </div>
          <Button type="submit" variant="secondary" icon={Search}>
            Search
          </Button>
        </Form>
      </div>

      <Card className="p-2 sm:p-2">
        {users.length === 0 ? (
          <EmptyState icon={Users} title="No users here" text={q ? 'Try a different search.' : undefined} />
        ) : (
          <ul className="divide-y divide-line">
            {users.map((u) => {
              const self = u.id === me.id
              return (
                <li key={u.id} className="flex flex-col gap-3 px-3 py-3 sm:flex-row sm:items-center">
                  <div className="flex min-w-0 flex-1 items-start gap-3">
                    <span
                      className={`grid size-10 shrink-0 place-items-center rounded-full text-xs font-semibold ${
                        u.role === 'user' ? 'bg-surface-2 text-muted' : 'bg-brand-gradient text-white'
                      }`}
                      aria-hidden
                    >
                      {(u.full_name ?? u.email).slice(0, 2).toUpperCase()}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate font-medium">
                        {u.full_name ?? u.email} {self && <span className="text-xs font-normal text-muted">(you)</span>}
                      </p>
                      {u.full_name && <p className="truncate text-xs text-muted">{u.email}</p>}
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        <RoleBadge role={u.role} />
                        <AccountBadge deleted={!!u.deleted_at} active={u.is_active} locked={u.locked} />
                        {u.active_sessions > 0 && <OnlineDot />}
                      </div>
                      <p className="mt-1 text-xs text-muted">
                        {u.city && `${u.city} · `}Last login {u.last_login_at ? formatDate(u.last_login_at) : 'never'}
                      </p>
                    </div>
                  </div>
                  {isOwner && !self && !u.deleted_at && actions(u)}
                </li>
              )
            })}
          </ul>
        )}
      </Card>

      <AddStaffModal
        open={adding}
        onClose={() => setAdding(false)}
        onCreated={(email) => {
          setAdding(false)
          toast.success(`Staff account created for ${email}.`)
          revalidate()
        }}
      />
      <ResetPasswordModal
        user={resetting}
        onClose={() => setResetting(null)}
        onDone={(email) => {
          setResetting(null)
          toast.success(`New password set for ${email}. They have been signed out.`)
          revalidate()
        }}
      />
    </>
  )
}

function AddStaffModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (email: string) => void }) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      icon={UserPlus}
      title="Add staff account"
      description="Give the new staff member their password in person or by phone. They sign in at Staff login."
      footer={
        <>
          <Button variant="secondary" icon={X} onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="staff-form" icon={UserPlus}>
            Create account
          </Button>
        </>
      }
    >
      <StaffFormBody onCreated={onCreated} />
    </Modal>
  )
}

function StaffFormBody({ onCreated }: { onCreated: (email: string) => void }) {
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState } = useForm<StaffForm>({
    resolver: zodResolver(staffSchema),
    defaultValues: { email: '', role: 'admin', password: '', confirm: '' },
  })
  const { errors, isSubmitting } = formState
  return (
    <form
      id="staff-form"
      noValidate
      className="space-y-4"
      onSubmit={handleSubmit(async (v) => {
        setError(null)
        try {
          await adminApi.createStaff({ email: v.email, role: v.role, password: v.password })
          onCreated(v.email)
        } catch (err) {
          setError(messageOf(err))
        }
      })}
    >
      <ErrorBanner message={error} />
      <fieldset disabled={isSubmitting} className="grid gap-4 sm:grid-cols-2">
        <Field label="Email" htmlFor="s-email" error={errors.email?.message}>
          <input id="s-email" type="email" autoFocus autoComplete="off" className={inputClass} aria-invalid={!!errors.email} {...register('email')} />
        </Field>
        <Field label="Role" htmlFor="s-role">
          <select id="s-role" className={inputClass} {...register('role')}>
            <option value="admin">Admin</option>
            <option value="super_admin">Super admin</option>
          </select>
        </Field>
        <Field label="Password" htmlFor="s-pw" hint="12+ characters, not a common password" error={errors.password?.message}>
          <input id="s-pw" type="password" autoComplete="new-password" className={inputClass} aria-invalid={!!errors.password} {...register('password')} />
        </Field>
        <Field label="Repeat password" htmlFor="s-pw2" error={errors.confirm?.message}>
          <input id="s-pw2" type="password" autoComplete="new-password" className={inputClass} aria-invalid={!!errors.confirm} {...register('confirm')} />
        </Field>
      </fieldset>
      {isSubmitting && <p className="text-sm text-muted">Creating account…</p>}
    </form>
  )
}

function ResetPasswordModal({ user, onClose, onDone }: { user: UserRow | null; onClose: () => void; onDone: (email: string) => void }) {
  return (
    <Modal
      open={user !== null}
      onClose={onClose}
      icon={KeyRound}
      title={`Reset password`}
      description={user ? `Set a new password for ${user.email}. They will be signed out and the account unlocked.` : undefined}
      footer={
        <>
          <Button variant="secondary" icon={X} onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="reset-form" icon={KeyRound}>
            Set password
          </Button>
        </>
      }
    >
      {user && <ResetFormBody user={user} onDone={onDone} />}
    </Modal>
  )
}

function ResetFormBody({ user, onDone }: { user: UserRow; onDone: (email: string) => void }) {
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState } = useForm<ResetForm>({
    resolver: zodResolver(resetSchema),
    defaultValues: { password: '', confirm: '' },
  })
  const { errors, isSubmitting } = formState
  return (
    <form
      id="reset-form"
      noValidate
      className="space-y-4"
      onSubmit={handleSubmit(async (v) => {
        setError(null)
        try {
          await adminApi.resetPassword(user.id, v.password)
          onDone(user.email)
        } catch (err) {
          setError(messageOf(err))
        }
      })}
    >
      <ErrorBanner message={error} />
      <fieldset disabled={isSubmitting} className="grid gap-4 sm:grid-cols-2">
        <Field label="New password" htmlFor="r-pw" hint="12+ characters" error={errors.password?.message}>
          <input id="r-pw" type="password" autoFocus autoComplete="new-password" className={inputClass} aria-invalid={!!errors.password} {...register('password')} />
        </Field>
        <Field label="Repeat password" htmlFor="r-pw2" error={errors.confirm?.message}>
          <input id="r-pw2" type="password" autoComplete="new-password" className={inputClass} aria-invalid={!!errors.confirm} {...register('confirm')} />
        </Field>
      </fieldset>
      {isSubmitting && <p className="text-sm text-muted">Saving…</p>}
    </form>
  )
}
