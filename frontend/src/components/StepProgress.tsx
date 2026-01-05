import { CheckCircle2, Circle, Loader2, XCircle, Play } from 'lucide-react'

export type StepStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'waiting_confirm'

interface Step {
  id: string
  name: string
  description: string
  status: StepStatus
  canConfirm?: boolean
  onConfirm?: () => void
  result?: any
  onClick?: () => void
  customControl?: React.ReactNode
  completedControl?: React.ReactNode
}

interface StepProgressProps {
  steps: Step[]
  currentStep?: number
}

export default function StepProgress({ steps, currentStep }: StepProgressProps) {
  const getStepIcon = (status: StepStatus) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-white" />
      case 'processing':
        return <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
      case 'failed':
        return <XCircle className="w-5 h-5 text-white" />
      case 'waiting_confirm':
        return <Play className="w-5 h-5 text-white ml-0.5" /> // ml-0.5 for visual centering
      default:
        return <Circle className="w-5 h-5 text-slate-400" />
    }
  }

  const getStepIconBg = (status: StepStatus) => {
    switch (status) {
      case 'completed': return 'bg-emerald-500 shadow-emerald-200'
      case 'processing': return 'bg-blue-50 ring-2 ring-blue-500/20'
      case 'failed': return 'bg-red-500 shadow-red-200'
      case 'waiting_confirm': return 'bg-amber-500 shadow-amber-200'
      default: return 'bg-slate-100'
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      {steps.map((step, index) => {
        const isCurrent = currentStep === index
        const isActive = step.status === 'processing' || isCurrent

        return (
          <div
            key={step.id}
            className={`
              relative overflow-hidden rounded-xl border transition-all duration-300 ease-out p-5
              ${isActive
                ? 'bg-white border-blue-500/30 shadow-lg shadow-blue-500/5 ring-1 ring-blue-500/10 scale-[1.01]'
                : 'bg-white border-slate-200 shadow-sm hover:shadow-md hover:border-blue-200'
              }
              ${step.onClick ? 'cursor-pointer' : ''}
            `}
            onClick={step.onClick}
          >
            {/* Progress Bar Background (Optional Visual Flair) */}
            {step.status === 'processing' && (
              <div className="absolute top-0 left-0 w-full h-1 bg-blue-50">
                <div className="h-full bg-blue-500/50 animate-pulse w-1/3 rounded-r-full" />
              </div>
            )}

            <div className="flex gap-4">
              {/* Icon Container */}
              <div className={`
                flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300
                ${getStepIconBg(step.status)}
                ${step.status === 'completed' || step.status === 'failed' || step.status === 'waiting_confirm' ? 'shadow-lg ring-2 ring-white' : ''}
              `}>
                {getStepIcon(step.status)}
              </div>

              <div className="flex-1 min-w-0 pt-1">
                <div className="flex items-center justify-between mb-1">
                  <h4 className={`text-base font-semibold tracking-tight ${isActive ? 'text-slate-900' : 'text-slate-700'}`}>
                    {index + 1}. {step.name}
                  </h4>

                  {/* Status Badges */}
                  {step.status === 'processing' && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 ring-1 ring-blue-700/10">
                      进行中
                    </span>
                  )}
                  {step.status === 'waiting_confirm' && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 ring-1 ring-amber-700/10 animate-pulse">
                      需确认
                    </span>
                  )}
                </div>

                <p className="text-sm text-slate-500 leading-relaxed line-clamp-2">
                  {step.description}
                </p>

                {/* Content Area */}
                <div className="mt-4 space-y-3">
                  {/* Result Display */}
                  {step.result && step.status === 'completed' && (
                    <div className="p-3 bg-slate-50/80 rounded-lg border border-slate-100/50 backdrop-blur-sm">
                      {step.result}
                    </div>
                  )}

                  {/* Controls */}
                  {step.status === 'waiting_confirm' && (
                    step.customControl ? (
                      <div className="pt-1">{step.customControl}</div>
                    ) : step.canConfirm && step.onConfirm ? (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          step.onConfirm?.()
                        }}
                        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white text-sm font-medium rounded-lg transition-colors shadow-sm shadow-blue-600/20"
                      >
                        <Play className="w-4 h-4 fill-current" />
                        开始处理
                      </button>
                    ) : null
                  )}

                  {/* Completed Controls */}
                  {step.status === 'completed' && step.completedControl && (
                    <div className="pt-1">{step.completedControl}</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}


