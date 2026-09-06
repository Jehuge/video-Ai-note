import { useEffect, useState } from 'react'
import { getNoteStyles, NoteStyle } from '../services/api'

const FALLBACK_STYLES: NoteStyle[] = [
  { id: 'simple', name: '简洁模式', icon: '✨', builtin: true, prompt: '' },
  { id: 'detailed', name: '详细模式', icon: '📋', builtin: true, prompt: '' },
  { id: 'academic', name: '学术模式', icon: '🎓', builtin: true, prompt: '' },
  { id: 'creative', name: '创意模式', icon: '🎨', builtin: true, prompt: '' },
]

/**
 * 加载笔记风格列表（内置 + 用户自定义），后端不可用时退回内置风格
 */
export function useNoteStyles() {
  const [styles, setStyles] = useState<NoteStyle[]>(FALLBACK_STYLES)

  useEffect(() => {
    let cancelled = false
    getNoteStyles()
      .then((list) => {
        if (!cancelled && list && list.length > 0) setStyles(list)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  return styles
}
