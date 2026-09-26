import { create } from 'zustand'

// UI-only state. Never put auth tokens or user data here.

export type Theme = 'light' | 'dark' | 'system'

const THEME_KEY = 'aqs-theme'
const darkQuery = () => window.matchMedia('(prefers-color-scheme: dark)')

function readTheme(): Theme {
  try {
    const saved = localStorage.getItem(THEME_KEY)
    return saved === 'light' || saved === 'dark' ? saved : 'system'
  } catch {
    return 'system' // storage blocked (private mode etc.)
  }
}

function applyTheme(theme: Theme) {
  const dark = theme === 'dark' || (theme === 'system' && darkQuery().matches)
  document.documentElement.classList.toggle('dark', dark)
}

interface UiState {
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
  toggleSidebar: () => void
  theme: Theme
  setTheme: (theme: Theme) => void
}

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: false,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  theme: readTheme(),
  setTheme: (theme) => {
    try {
      localStorage.setItem(THEME_KEY, theme)
    } catch {
      // preference just won't persist
    }
    applyTheme(theme)
    set({ theme })
  },
}))

/** Apply the saved theme and follow the OS setting while the theme is "system". */
export function initTheme() {
  applyTheme(useUiStore.getState().theme)
  darkQuery().addEventListener('change', () => {
    if (useUiStore.getState().theme === 'system') applyTheme('system')
  })
}
