// Shared button classes (also used for links styled as buttons).

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'danger-soft'
export type ButtonSize = 'sm' | 'md'

const BASE =
  'inline-flex items-center justify-center gap-2 rounded-xl font-medium whitespace-nowrap transition ' +
  'disabled:pointer-events-none disabled:opacity-55 active:scale-[0.98] select-none'

const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-brand-gradient text-white shadow-sm shadow-indigo-500/25 hover:brightness-110',
  secondary: 'border border-line-strong bg-surface text-ink hover:bg-surface-2',
  ghost: 'text-ink hover:bg-surface-2',
  danger: 'bg-danger text-white hover:brightness-110 dark:text-slate-950',
  'danger-soft': 'bg-danger-soft text-danger hover:brightness-95',
}

const SIZES: Record<ButtonSize, string> = {
  sm: 'h-9 px-3 text-sm',
  md: 'h-11 px-4 text-sm sm:h-10',
}

export function buttonStyles(variant: ButtonVariant = 'primary', size: ButtonSize = 'md', extra = '') {
  return `${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${extra}`
}
