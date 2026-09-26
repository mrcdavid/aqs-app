import { AlertTriangle, CheckCircle2, HelpCircle, Info, X, XCircle } from 'lucide-react'

import { useFeedbackStore } from '../../stores/feedback'
import { Button } from './Button'
import { Modal } from './Modal'

const TOAST_STYLE = {
  success: { icon: CheckCircle2, cls: 'text-success' },
  error: { icon: XCircle, cls: 'text-danger' },
  info: { icon: Info, cls: 'text-brand' },
}

/** Toast stack (bottom-right; bottom-center on phones). Mounted once in AppLayout. */
export function Toaster() {
  const toasts = useFeedbackStore((s) => s.toasts)
  const dismiss = useFeedbackStore((s) => s.dismiss)
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 sm:inset-x-auto sm:right-4 sm:bottom-4 sm:items-end"
    >
      {toasts.map((t) => {
        const { icon: Icon, cls } = TOAST_STYLE[t.kind]
        return (
          <div
            key={t.id}
            role={t.kind === 'error' ? 'alert' : 'status'}
            className="pointer-events-auto flex w-full max-w-sm animate-fade-up items-start gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-sm shadow-card"
          >
            <Icon className={`mt-0.5 size-5 shrink-0 ${cls}`} aria-hidden />
            <p className="flex-1">{t.message}</p>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss"
              className="-m-1 rounded p-1 text-muted hover:text-ink"
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>
        )
      })}
    </div>
  )
}

/** Renders the dialog for confirmAction(). Mounted once in AppLayout. */
export function ConfirmHost() {
  const request = useFeedbackStore((s) => s.confirm)
  const settle = useFeedbackStore((s) => s.settleConfirm)
  const r = request
  const danger = r?.tone === 'danger'

  return (
    <Modal
      open={request !== null}
      onClose={() => settle(false)}
      title={r?.title ?? ''}
      icon={danger ? AlertTriangle : HelpCircle}
      tone={danger ? 'danger' : 'brand'}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={() => settle(false)}>
            {r?.cancelLabel ?? 'Cancel'}
          </Button>
          <Button variant={danger ? 'danger' : 'primary'} onClick={() => settle(true)}>
            {r?.confirmLabel ?? 'Confirm'}
          </Button>
        </>
      }
    >
      <p className="text-sm leading-relaxed">{r?.message}</p>
    </Modal>
  )
}
