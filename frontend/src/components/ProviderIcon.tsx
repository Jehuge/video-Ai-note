import React from 'react'

interface ProviderIconProps {
  provider: string
  className?: string
  alt?: string
}

const ICON_FILENAMES: Record<string, string> = {
  openai: 'openai-svgrepo-com.svg',
  deepseek: 'deepseek-color.svg',
  claude: 'claude-color.svg',
  gemini: 'gemini-color.svg',
  ollama: 'ollama.svg',
  chatglm: 'chatglm-color.svg',
  siliconcloud: 'siliconcloud-color.svg',
  deepseek_color: 'deepseek-color.svg',
}

export default function ProviderIcon({ provider, className, alt }: ProviderIconProps) {
  const filename = ICON_FILENAMES[provider]
  if (filename) {
    // file is located at frontend/icon/*.svg, this file is in frontend/src/components
    const src = new URL(`../../icon/${filename}`, import.meta.url).href
    return <img src={src} alt={alt || provider} className={className} />
  }

  // fallback emoji
  return <span className={className}>🤖</span>
}


