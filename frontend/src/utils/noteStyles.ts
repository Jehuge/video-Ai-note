export interface NoteStyleDefinition {
  id: string
  name: string
  prompt: string
  built_in: boolean
  enabled: boolean
}

export interface NoteStyleSettings {
  version: number
  default_style_id: string
  styles: NoteStyleDefinition[]
}

export const FALLBACK_NOTE_STYLE_SETTINGS: NoteStyleSettings = {
  version: 1,
  default_style_id: 'simple',
  styles: [
    { id: 'simple', name: '简洁模式', prompt: '', built_in: true, enabled: true },
    { id: 'detailed', name: '详细模式', prompt: '', built_in: true, enabled: true },
    { id: 'academic', name: '学术模式', prompt: '', built_in: true, enabled: true },
    { id: 'creative', name: '创意模式', prompt: '', built_in: true, enabled: true },
  ],
}
