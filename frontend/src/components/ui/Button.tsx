import type { LucideIcon } from 'lucide-react'
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router'

import { buttonStyles, type ButtonSize, type ButtonVariant } from './buttonStyles'
import { Spinner } from './Spinner'

interface Common {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: LucideIcon
  children?: ReactNode
}

function Content({ icon: Icon, loading, children }: { icon?: LucideIcon; loading?: boolean; children?: ReactNode }) {
  return (
    <>
      {loading ? <Spinner className="size-4" /> : Icon && <Icon className="size-4 shrink-0" aria-hidden />}
      {children}
    </>
  )
}

export function Button({
  variant,
  size,
  icon,
  loading,
  children,
  className = '',
  type = 'button',
  disabled,
  ...rest
}: Common & ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }) {
  return (
    <button
      type={type}
      className={buttonStyles(variant, size, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      <Content icon={icon} loading={loading}>
        {children}
      </Content>
    </button>
  )
}

export function ButtonLink({ variant, size, icon, children, className = '', ...rest }: Common & LinkProps) {
  return (
    <Link className={buttonStyles(variant, size, className)} {...rest}>
      <Content icon={icon}>{children}</Content>
    </Link>
  )
}

/** For plain links that must leave the SPA (PDF downloads, Google sign-in). */
export function ButtonAnchor({
  variant,
  size,
  icon,
  children,
  className = '',
  ...rest
}: Common & AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a className={buttonStyles(variant, size, className)} {...rest}>
      <Content icon={icon}>{children}</Content>
    </a>
  )
}

/** Icon-only button. `label` becomes the accessible name and the hover tooltip. */
export function IconButton({
  icon: Icon,
  label,
  tone = 'default',
  loading,
  className = '',
  type = 'button',
  disabled,
  ...rest
}: {
  icon: LucideIcon
  label: string
  tone?: 'default' | 'danger' | 'brand'
  loading?: boolean
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const tones = {
    default: 'text-muted hover:bg-surface-2 hover:text-ink',
    brand: 'text-brand hover:bg-brand-soft',
    danger: 'text-danger hover:bg-danger-soft',
  }
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      disabled={disabled || loading}
      className={`inline-flex size-10 shrink-0 items-center justify-center rounded-xl transition disabled:opacity-50 sm:size-9 ${tones[tone]} ${className}`}
      {...rest}
    >
      {loading ? <Spinner className="size-4" /> : <Icon className="size-[18px]" aria-hidden />}
    </button>
  )
}
