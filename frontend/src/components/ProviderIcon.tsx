


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

export default function ProviderIcon({ provider, className, alt }: ProviderIconProps & { providerType?: string }) {
  // 优先使用 providerType，如果未提供或未找到图标，则尝试使用 provider
  // 处理一些别名映射
  let type = (arguments[0].providerType || provider).toLowerCase()
  if (type === 'qwen') type = 'chatglm' // 暂时用 chatglm 图标或者如果有 qwen 图标
  if (type === 'siliconflow') type = 'siliconcloud'

  const filename = ICON_FILENAMES[type] || ICON_FILENAMES[provider.toLowerCase()]

  if (filename) {
    // file is located at frontend/icon/*.svg, this file is in frontend/src/components
    const src = new URL(`../../icon/${filename}`, import.meta.url).href
    return <img src={src} alt={alt || provider} className={className} />
  }

  // fallback emoji
  return <span className={`flex items-center justify-center bg-gray-100 rounded text-lg ${className}`}>🤖</span>
}


