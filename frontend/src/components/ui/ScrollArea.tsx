import { ReactNode } from 'react'

interface ScrollAreaProps {
  children: ReactNode
  className?: string
}

export function ScrollArea({ children, className = '' }: ScrollAreaProps) {
  return (
    <div className={`overflow-y-auto ${className}`} style={{ maxHeight: '100%' }}>
      {children}
    </div>
  )
}



