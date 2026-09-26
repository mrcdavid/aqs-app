import { Monitor, Moon, Sun } from 'lucide-react'

import { useUiStore, type Theme } from '../../stores/ui'

const OPTIONS: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

/** Three-way switch: Light / Dark / follow the device. */
export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const theme = useUiStore((s) => s.theme)
  const setTheme = useUiStore((s) => s.setTheme)
  return (
    <div role="radiogroup" aria-label="Colour theme" className="inline-flex rounded-xl bg-surface-2 p-1">
      {OPTIONS.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={theme === value}
          title={`${label} theme`}
          onClick={() => setTheme(value)}
          className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition ${
            theme === value ? 'bg-surface text-ink shadow-sm' : 'text-muted hover:text-ink'
          }`}
        >
          <Icon className="size-4" aria-hidden />
          {!compact && label}
        </button>
      ))}
    </div>
  )
}
