import { PropsWithChildren, createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { getNoteStyleSettings } from '../services/api'
import { FALLBACK_NOTE_STYLE_SETTINGS, NoteStyleSettings } from '../utils/noteStyles'

interface NoteStylesContextValue {
  settings: NoteStyleSettings
  enabledStyles: NoteStyleSettings['styles']
  defaultStyleId: string
  loaded: boolean
  replaceSettings: (settings: NoteStyleSettings) => void
}

const NoteStylesContext = createContext<NoteStylesContextValue | null>(null)

export function NoteStylesProvider({ children }: PropsWithChildren) {
  const [settings, setSettings] = useState<NoteStyleSettings>(FALLBACK_NOTE_STYLE_SETTINGS)
  const [loaded, setLoaded] = useState(false)

  const load = useCallback(async () => {
    try {
      const response = await getNoteStyleSettings()
      if (response.data.code === 200 && response.data.data) {
        setSettings(response.data.data)
      }
    } catch (error) {
      console.warn('加载笔记模式失败，使用内置模式:', error)
    } finally {
      setLoaded(true)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const enabledStyles = useMemo(
    () => settings.styles.filter((style) => style.enabled),
    [settings.styles]
  )
  const defaultStyleId = enabledStyles.some((style) => style.id === settings.default_style_id)
    ? settings.default_style_id
    : enabledStyles[0]?.id || 'simple'
  const value = useMemo(
    () => ({ settings, enabledStyles, defaultStyleId, loaded, replaceSettings: setSettings }),
    [settings, enabledStyles, defaultStyleId, loaded]
  )

  return <NoteStylesContext.Provider value={value}>{children}</NoteStylesContext.Provider>
}

export function useNoteStyles() {
  const context = useContext(NoteStylesContext)
  if (!context) {
    throw new Error('useNoteStyles must be used within NoteStylesProvider')
  }
  return context
}
