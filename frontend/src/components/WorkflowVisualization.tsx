import { useState, useRef, useEffect } from 'react'

interface SessionState {
  body: string | null
  seats_min: number | null
  fuel: string | null
  brand: string | null
  model: string | null
  stage: string | null
  test_drive_completed: boolean
}

interface WorkflowVisualizationProps {
  state: SessionState
}

const WorkflowVisualization = ({ state }: WorkflowVisualizationProps) => {
  const [isHighlighted, setIsHighlighted] = useState(true)
  const trackerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Highlight the progress tracker when component mounts
    setIsHighlighted(true)
    const timer = setTimeout(() => {
      setIsHighlighted(false)
    }, 3000) // Highlight for 3 seconds

    return () => clearTimeout(timer)
  }, [])

  const stages = [
    {
      id: 'brand',
      title: 'The Brand',
      description: 'The luxury brand that caught your eye',
      completed: !!state.brand,
      value: state.brand,
      witty: state.brand ? `You've got your eyes on ${state.brand}! Classy choice!` : 'Still window shopping?'
    },
    {
      id: 'model',
      title: 'The Model',
      description: 'The specific model you fell for',
      completed: !!state.model,
      value: state.model,
      witty: state.model ? `${state.model} it is! Your dream ride awaits!` : 'Which beauty calls to you?'
    },
    {
      id: 'test_drive',
      title: 'The Test Drive',
      description: 'Scheduled your joyride',
      completed: state.test_drive_completed || state.stage === 'test_drive',
      value: state.test_drive_completed ? 'Completed' : state.stage === 'test_drive' ? 'Scheduled' : null,
      witty: state.test_drive_completed 
        ? 'You\'ve taken it for a spin! How was the ride?' 
        : state.stage === 'test_drive' 
        ? 'Test drive locked in! Get ready to feel the power!'
        : 'Ready to feel the road beneath you?'
    },
    {
      id: 'deal',
      title: 'The Deal',
      description: 'Finalizing your purchase',
      completed: state.stage === 'financing',
      value: state.stage === 'financing' ? 'In Progress' : null,
      witty: state.stage === 'financing' 
        ? 'Let\'s make this dream financially fabulous!' 
        : 'Almost there! Let\'s talk numbers!'
    },
    {
      id: 'delivery',
      title: 'The Delivery',
      description: 'Your luxury ride journey',
      completed: false,
      value: null,
      witty: 'The finish line awaits!'
    }
  ]

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold text-gray-800 mb-6">Our Journey</h2>
      
      {/* Workflow Stages */}
      <div 
        ref={trackerRef}
        className={`transition-all duration-500 ${
          isHighlighted ? 'bg-amber-100 p-4 rounded-lg border-2 border-amber-400 shadow-lg' : ''
        }`}
      >
        <h3 className={`text-lg font-semibold mb-6 transition-colors ${
          isHighlighted ? 'text-amber-700' : 'text-gray-700'
        }`}>
          Progress Tracker
        </h3>
        <div className="space-y-0">
          {stages.map((stage, idx) => {
            const isActive = stage.completed
            const isNext = !stage.completed && idx > 0 && stages[idx - 1].completed
            const isPending = !isActive && !isNext
            
            return (
              <div key={stage.id} className="relative">
                {/* Connector Line */}
                {idx < stages.length - 1 && (
                  <div className={`absolute left-5 top-10 w-0.5 ${
                    isActive ? 'bg-purple-600 h-12' : 'bg-gray-300 h-12'
                  }`} />
                )}
                
                {/* Stage Item */}
                <div className={`relative flex items-start space-x-4 py-2 transition-all ${
                  isNext ? 'bg-gray-50 rounded-lg px-4 py-3 -mx-2 shadow-sm' : ''
                }`}>
                  {/* Status Icon */}
                  <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-all ${
                    isActive 
                      ? 'bg-purple-600 text-white' 
                      : isPending
                      ? 'bg-white border-2 border-gray-300'
                      : 'bg-white border-2 border-purple-600'
                  }`}>
                    {isActive ? (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <span className={`text-sm font-bold ${
                        isPending ? 'text-gray-400' : 'text-purple-600'
                      }`}>
                        {idx + 1}
                      </span>
                    )}
                  </div>
                  
                  {/* Content */}
                  <div className="flex-1 pt-0.5">
                    <h4 className={`font-semibold mb-0.5 ${
                      isActive || isNext ? 'text-gray-800' : 'text-gray-400'
                    }`}>
                      {stage.title}
                    </h4>
                    {stage.value && (
                      <p className={`text-sm mb-1 ${
                        isActive || isNext ? 'text-gray-600' : 'text-gray-400'
                      }`}>
                        {stage.value}
                      </p>
                    )}
                    <p className={`text-xs ${
                      isActive || isNext ? 'text-gray-500' : 'text-gray-400'
                    }`}>
                      {stage.witty}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default WorkflowVisualization

