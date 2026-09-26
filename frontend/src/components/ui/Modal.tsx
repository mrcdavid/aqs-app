import { X, type LucideIcon } from 'lucide-react'
import { useEffect, useId, useRef, type ReactNode } from 'react'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  description?: ReactNode
  icon?: LucideIcon
  tone?: 'brand' | 'danger' | 'success'
  size?: 'sm' | 'md' | 'lg'
  children: ReactNode
  /** Buttons row; rendered in a sticky footer. */
  footer?: ReactNode
}

const TONES = {
  brand: 'bg-brand-soft text-brand',
  danger: 'bg-danger-soft text-danger',
  success: 'bg-success-soft text-success',
}
const SIZES = { sm: 'sm:max-w-md', md: 'sm:max-w-lg', lg: 'sm:max-w-2xl' }

/**
 * Native <dialog> shown with showModal(): the browser traps focus, closes on Esc, marks the rest
 * of the page inert, and returns focus to the button that opened it. Full-screen on phones.
 * Content is only mounted while open, so forms start fresh each time.
 */
export function Modal({ open, onClose, title, description, icon: Icon, tone = 'brand', size = 'md', children, footer }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const pressedBackdrop = useRef(false)
  const titleId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) {
      dialog.showModal()
      // Focus a marked field, else the first field, else Cancel (never a destructive button).
      const target =
        dialog.querySelector<HTMLElement>('[data-autofocus]') ??
        dialog.querySelector<HTMLElement>(
          '[data-modal-body] :is(input, select, textarea):not([disabled]):not([type="hidden"])',
        ) ??
        dialog.querySelector<HTMLElement>('[data-modal-footer] button')
      target?.focus()
    }
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault() // Esc: let the parent decide (it closes via `open`)
        onClose()
      }}
      // Close on a click that starts AND ends on the backdrop (not when dragging out of an input).
      onMouseDown={(e) => {
        pressedBackdrop.current = e.target === ref.current
      }}
      onClick={(e) => {
        if (pressedBackdrop.current && e.target === ref.current) onClose()
      }}
      className={`bg-surface p-0 text-ink shadow-2xl ${
        size === 'sm'
          ? // small (confirmations): a centred card on every screen
            'm-auto h-fit max-h-[88vh] w-[calc(100%-2rem)] rounded-2xl border border-line'
          : // forms: full screen on phones, centred card from `sm` up
            'm-0 h-dvh max-h-none w-full max-w-none sm:m-auto sm:h-fit sm:max-h-[88vh] sm:w-[calc(100%-2rem)] sm:rounded-2xl sm:border sm:border-line'
      } ${SIZES[size]}`}
    >
      {open && (
        <div className="flex h-full max-h-[inherit] animate-fade-up flex-col">
          <header className="flex items-start gap-3 border-b border-line px-5 py-4">
            {Icon && (
              <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${TONES[tone]}`}>
                <Icon className="size-5" aria-hidden />
              </span>
            )}
            <div className="min-w-0 flex-1">
              <h2 id={titleId} className="text-lg font-semibold leading-tight">
                {title}
              </h2>
              {description && <div className="mt-1 text-sm text-muted">{description}</div>}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              title="Close"
              className="-mr-1 grid size-9 shrink-0 place-items-center rounded-lg text-muted hover:bg-surface-2 hover:text-ink"
            >
              <X className="size-5" aria-hidden />
            </button>
          </header>
          <div data-modal-body className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            {children}
          </div>
          {footer && (
            <footer data-modal-footer className="flex flex-col-reverse gap-2 border-t border-line bg-surface-2/60 px-5 py-3 sm:flex-row sm:justify-end">
              {footer}
            </footer>
          )}
        </div>
      )}
    </dialog>
  )
}
