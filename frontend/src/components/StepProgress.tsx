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
}

interface StepProgressProps {
  steps: Step[]
  currentStep?: number
}

export default function StepProgress({ steps, currentStep }: StepProgressProps) {
  const getStepIcon = (status: StepStatus) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-green-500" />
      case 'processing':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500" />
      case 'waiting_confirm':
        return <Play className="w-5 h-5 text-orange-500" />
      default:
        return <Circle className="w-5 h-5 text-gray-400" />
    }
  }

  const getStepColor = (status: StepStatus, isCurrent: boolean) => {
    if (isCurrent && status === 'processing') return 'border-blue-500 bg-blue-50'
    if (status === 'completed') return 'border-green-500 bg-green-50'
    if (status === 'failed') return 'border-red-500 bg-red-50'
    if (status === 'waiting_confirm') return 'border-orange-500 bg-orange-50'
    return 'border-gray-300 bg-white'
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {steps.map((step, index) => {
        const isCurrent = currentStep === index
        const isActive = step.status === 'processing' || isCurrent

        return (
          <div
            key={step.id}
            className={`border-2 rounded-lg p-4 transition-all ${getStepColor(
              step.status,
              isCurrent
            )} ${step.onClick ? 'cursor-pointer hover:shadow-md' : ''}`}
            onClick={step.onClick}
          >
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 mt-0.5">{getStepIcon(step.status)}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <h4
                    className={`font-medium ${isActive ? 'text-blue-900' : 'text-gray-700'
                      }`}
                  >
                    {index + 1}. {step.name}
                  </h4>
                  {step.status === 'processing' && (
                    <span className="text-xs text-blue-600 bg-blue-100 px-2 py-1 rounded">
                      进行中...
                    </span>
                  )}
                  {step.status === 'waiting_confirm' && (
                    <span className="text-xs text-orange-600 bg-orange-100 px-2 py-1 rounded">
                      等待确认
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-600 mt-1">{step.description}</p>

                {/* 显示结果 */}
                {step.result && step.status === 'completed' && (
                  <div className="mt-3 p-3 bg-white rounded border border-gray-200">
                    {step.result}
                  </div>
                )}

                {/* 确认按钮 */}
                {step.canConfirm && step.status === 'waiting_confirm' && step.onConfirm && (
                  <button
                    onClick={step.onConfirm}
                    className="mt-3 px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
                  >
                    <Play className="w-4 h-4" />
                    开始此步骤
                  </button>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}


