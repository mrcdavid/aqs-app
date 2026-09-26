import { Loader2 } from 'lucide-react'
import { useNavigation, useRevalidator } from 'react-router'

export function Spinner({ className = 'size-5', label }: { className?: string; label?: string }) {
  return (
    <>
      <Loader2 className={`animate-spin ${className}`} aria-hidden />
      {label && <span className="sr-only">{label}</span>}
    </>
  )
}

/** Thin gradient bar at the top of the window while a page is loading or refreshing. */
export function TopProgressBar() {
  const navigation = useNavigation()
  const revalidator = useRevalidator()
  const busy = navigation.state !== 'idle' || revalidator.state !== 'idle'
  if (!busy) return null
  return (
    <div
      className="fixed inset-x-0 top-0 z-50 h-0.5 overflow-hidden bg-brand-soft"
      role="progressbar"
      aria-label="Loading"
    >
      <div className="bg-brand-gradient h-full w-2/5 animate-progress" />
    </div>
  )
}
