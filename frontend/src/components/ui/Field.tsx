import type { ReactNode } from 'react'

interface FieldProps {
  label: string
  htmlFor: string
  error?: string
  hint?: string
  children: ReactNode
}

export function Field({ label, htmlFor, error, hint, children }: FieldProps) {
  return (
    <div className="space-y-1">
      <label htmlFor={htmlFor} className="block text-sm font-medium">
        {label}
      </label>
      {children}
      {hint && !error && <p className="text-xs text-muted">{hint}</p>}
      {error && (
        <p id={`${htmlFor}-error`} role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  )
}

export const inputClass =
  'w-full rounded-lg border border-brand-100 bg-white px-3 py-2 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 aria-invalid:border-red-500'

export const buttonClass =
  'inline-flex items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-60'

export const secondaryButtonClass =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-brand-100 bg-white px-3 py-1.5 text-sm font-medium hover:bg-brand-50 disabled:opacity-60'

export const linkButtonClass =
  'inline-flex items-center gap-1 rounded px-1.5 py-1 text-sm text-brand-600 hover:bg-brand-50 disabled:opacity-60'
