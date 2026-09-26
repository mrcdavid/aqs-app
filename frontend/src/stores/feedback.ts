import { create } from 'zustand'

// Toast notifications and confirmation dialogs. UI state only.

export type ToastKind = 'success' | 'error' | 'info'

interface Toast {
  id: number
  kind: ToastKind
  message: string
}

export interface ConfirmOptions {
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  tone?: 'default' | 'danger'
}

interface PendingConfirm extends ConfirmOptions {
  resolve: (ok: boolean) => void
}

interface FeedbackState {
  toasts: Toast[]
  dismiss: (id: number) => void
  confirm: PendingConfirm | null
  settleConfirm: (ok: boolean) => void
}

let nextId = 1

export const useFeedbackStore = create<FeedbackState>((set, get) => ({
  toasts: [],
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  confirm: null,
  settleConfirm: (ok) => {
    get().confirm?.resolve(ok)
    set({ confirm: null })
  },
}))

function push(kind: ToastKind, message: string) {
  const id = nextId++
  useFeedbackStore.setState((s) => ({ toasts: [...s.toasts.slice(-3), { id, kind, message }] }))
  window.setTimeout(() => useFeedbackStore.getState().dismiss(id), kind === 'error' ? 7000 : 4000)
}

export const toast = {
  success: (message: string) => push('success', message),
  error: (message: string) => push('error', message),
  info: (message: string) => push('info', message),
}

/** Ask the user to confirm; resolves true (confirmed) or false (cancelled / closed). */
export function confirmAction(options: ConfirmOptions): Promise<boolean> {
  useFeedbackStore.getState().confirm?.resolve(false)
  return new Promise((resolve) => useFeedbackStore.setState({ confirm: { ...options, resolve } }))
}
