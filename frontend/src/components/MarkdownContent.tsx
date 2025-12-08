import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import 'github-markdown-css/github-markdown.css'

interface MarkdownContentProps {
  markdown: string
}

export default function MarkdownContent({ markdown }: MarkdownContentProps) {
  return (
    <div className="markdown-body prose max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
    </div>
  )
}

