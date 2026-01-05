import React from 'react'
import { CheckCircle2, Circle, Loader2, Play, XCircle } from 'lucide-react'

export type StepStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'waiting_confirm'

export interface Step {
  id: string
  name: string
  description: string
  status: StepStatus
  canConfirm?: boolean
  onConfirm?: () => void
  customControl?: React.ReactNode
  completedControl?: React.ReactNode
  result?: React.ReactNode
  onClick?: () => void
}

interface StepProgressProps {
  steps: Step[]
  currentStep: number
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
        return <Play className="w-5 h-5 text-white ml-0.5" />
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
    <div className="relative max-w-2xl mx-auto pb-12">
      {steps.map((step, index) => {
        const isLast = index === steps.length - 1
        const isCurrent = currentStep === index
        const isActive = step.status === 'processing' || isCurrent

        return (
          <div key={step.id} className="relative flex gap-6 pb-12 last:pb-0 group">
            {/* Timeline Line */}
            {!isLast && (
              <div className="absolute left-[1.25rem] top-10 bottom-0 w-0.5 bg-slate-100 group-hover:bg-slate-200 transition-colors" />
            )}

            {/* Left Column: Icon */}
            <div className="relative flex-shrink-0 pt-0.5">
              <div className={`
                w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300 relative z-10
                ${getStepIconBg(step.status)}
                ${isActive || step.status === 'completed' || step.status === 'waiting_confirm'
                  ? 'shadow-lg ring-4 ring-white'
                  : 'bg-white border-2 border-slate-100'}
              `}>
                {getStepIcon(step.status)}
              </div>
            </div>

            {/* Right Column: Content Card */}
            <div className="flex-1 min-w-0">
              <div
                className={`
                  relative overflow-hidden rounded-2xl border transition-all duration-300 ease-out
                  ${isActive
                    ? 'bg-white border-blue-500/30 shadow-lg shadow-blue-500/5 ring-1 ring-blue-500/10'
                    : 'bg-white border-slate-200/60 shadow-sm hover:shadow-md hover:border-blue-200/50'
                  }
                  ${step.onClick ? 'cursor-pointer hover:-translate-y-0.5' : ''}
                `}
                onClick={step.onClick}
              >
                {/* Progress Bar Flair */}
                {step.status === 'processing' && (
                  <div className="absolute top-0 left-0 w-full h-1 bg-blue-50">
                    <div className="h-full bg-blue-500/50 animate-pulse w-1/3 rounded-r-full" />
                  </div>
                )}

                <div className="p-5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                    <h4 className={`text-base font-bold tracking-tight leading-snug ${isActive ? 'text-slate-900' : 'text-slate-700'}`}>
                      {step.name}
                    </h4>

                    {/* Status Badges - Pushed to right on desktop, inline/stacked on mobile */}
                    <div className="flex-shrink-0">
                      {step.status === 'processing' && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-600 ring-1 ring-blue-600/10">
                          进行中
                        </span>
                      )}
                      {step.status === 'waiting_confirm' && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-600 ring-1 ring-amber-600/10 animate-pulse">
                          需确认
                        </span>
                      )}
                      {step.status === 'completed' && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-600 ring-1 ring-emerald-600/10">
                          已完成
                        </span>
                      )}
                    </div>
                  </div>

                  <p className="text-sm text-slate-500 leading-relaxed mb-4">
                    {step.description}
                  </p>

                  {/* Content Area */}
                  <div className="space-y-4">
                    {/* Result Display */}
                    {step.result && step.status === 'completed' && (
                      <div className="p-4 bg-slate-50/50 rounded-xl border border-slate-100">
                        {step.result}
                      </div>
                    )}

                    {/* Controls Container */}
                    {(step.status === 'waiting_confirm' || (step.status === 'completed' && step.completedControl)) && (
                      <div className="pt-2">
                        {/* Waiting Confirmation Controls */}
                        {step.status === 'waiting_confirm' && (
                          step.customControl ? (
                            step.customControl
                          ) : step.canConfirm && step.onConfirm ? (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                step.onConfirm?.()
                              }}
                              className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white text-sm font-medium rounded-lg transition-all shadow-sm shadow-blue-600/20 hover:shadow-blue-600/30"
                            >
                              <Play className="w-4 h-4 fill-current" />
                              开始处理
                            </button>
                          ) : null
                        )}

                        {/* Completed Controls */}
                        {step.status === 'completed' && step.completedControl && (
                          step.completedControl
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
