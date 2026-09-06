declare module 'markdown-it-texmath' {
  import type MarkdownIt from 'markdown-it'
  function texmath(md: MarkdownIt, options?: Record<string, unknown>): void
  export default texmath
}
