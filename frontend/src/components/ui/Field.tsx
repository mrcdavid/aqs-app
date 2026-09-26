import type { ReactNode } from 'react'

interface FieldProps {
  label: string
  htmlFor: string
  error?: string
  hint?: string
  children: ReactNode
  className?: string
}

export function Field({ label, htmlFor, error, hint, children, className = '' }: FieldProps) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      <label htmlFor={htmlFor} className="block text-sm font-medium">
        {label}
      </label>
      {children}
      {hint && !error && <p className="text-xs text-muted">{hint}</p>}
      {error && (
        <p id={`${htmlFor}-error`} role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  )
}

/** Inputs/selects/textareas: clear focus ring so it's obvious which field is being edited. */
export const inputClass =
  'w-full rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm text-ink shadow-sm transition ' +
  'placeholder:text-muted/70 hover:border-muted focus:border-ring focus:ring-4 focus:ring-ring/20 focus:outline-none ' +
  'disabled:cursor-not-allowed disabled:bg-surface-2 disabled:opacity-70 ' +
  'aria-invalid:border-danger aria-invalid:focus:ring-danger/20 sm:py-2'

/** Segmented control (e.g. cm / inch): wrap radio inputs in labels with this class. */
export const segmentClass =
  'cursor-pointer rounded-lg px-4 py-2 text-sm font-medium text-muted transition hover:text-ink ' +
  'has-checked:bg-surface has-checked:text-ink has-checked:shadow-sm has-focus-visible:ring-2 has-focus-visible:ring-ring'
