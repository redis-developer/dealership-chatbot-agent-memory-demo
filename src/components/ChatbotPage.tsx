import { useState, useRef, useEffect } from 'react'
import { useChatbot } from '../contexts/ChatbotContext'
import { useAuth } from '../contexts/AuthContext'
import WorkflowVisualization from './WorkflowVisualization'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface SessionState {
  body: string | null
  seats_min: number | null
  fuel: string | null
  brand: string | null
  model: string | null
  stage: string | null
  test_drive_completed: boolean
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001'

const generateSessionId = (): string => {
  return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

const ChatbotPage = () => {
  const { closeChatbot } = useChatbot()
  const { userId } = useAuth()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>(() => {
    const stored = sessionStorage.getItem('autoemporium_session_id')
    return stored || generateSessionId()
  })
  const [state, setState] = useState<SessionState>({
    body: null,
    seats_min: null,
    fuel: null,
    brand: null,
    model: null,
    stage: null,
    test_drive_completed: false
  })
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (messages.length === 0) {
      sessionStorage.setItem('autoemporium_session_id', sessionId)
      setMessages([{
        role: 'assistant',
        content: 'Hello! I\'m your AutoEmporium assistant. How can I help you find your perfect car today?'
      }])
    }
  }, [messages.length, sessionId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const fetchState = async () => {
    if (!userId || !sessionId) return
    
    try {
      const response = await fetch(`${API_URL}/journey/${sessionId}?user_id=${userId}`)
      if (response.ok) {
        const data = await response.json()
        if (data.state) {
          setState(data.state)
        }
      }
    } catch (error) {
      console.error('Error fetching customer journey:', error)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || isLoading || !userId) return

    const userMessage = input.trim()
    setInput('')
    setIsLoading(true)

    const newMessages: Message[] = [...messages, { role: 'user', content: userMessage }]
    setMessages(newMessages)

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionId,
          user_id: userId,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to get response from chatbot')
      }

      const data = await response.json()
      
      if (data.session_id && data.session_id !== sessionId) {
        setSessionId(data.session_id)
        sessionStorage.setItem('autoemporium_session_id', data.session_id)
      }

      if (data.state) {
        setState(data.state)
      }

      setMessages([...newMessages, { role: 'assistant', content: data.response }])
      
      // Fetch updated state
      await fetchState()
    } catch (error) {
      console.error('Error sending message:', error)
      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: 'Sorry, I encountered an error. Please try again later.',
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  useEffect(() => {
    fetchState()
  }, [sessionId, userId])

  if (!userId) {
    return null
  }

  return (
    <div className="fixed inset-0 bg-gradient-to-br from-gray-50 via-white to-amber-50 z-50 flex flex-col">
      {/* Header */}
      <div className="bg-gradient-to-r from-amber-600 via-amber-500 to-amber-600 text-white p-5 flex items-center justify-between shadow-lg border-b-4 border-amber-700">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-sm">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">AutoEmporium Assistant</h1>
        </div>
        <button
          onClick={closeChatbot}
          className="text-white hover:bg-white/20 p-2 rounded-lg transition-all duration-200 hover:scale-110"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Chat Area - Left Side */}
        <div className="flex-1 flex flex-col border-r-2 border-gray-200 bg-gradient-to-b from-white to-gray-50">
          <div className="flex-1 p-6 overflow-y-auto bg-gradient-to-b from-transparent via-white to-gray-50/50">
            {messages.length === 0 ? (
              <div className="text-center mt-16">
                <div className="inline-block bg-gradient-to-r from-amber-500 to-amber-600 p-4 rounded-full mb-4 shadow-lg">
                  <svg className="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </div>
                <p className="text-xl font-semibold text-gray-700 mb-2">Welcome to AutoEmporium!</p>
                <p className="text-gray-500">Start a conversation with our assistant to find your perfect car.</p>
              </div>
            ) : (
              <div className="space-y-4 max-w-4xl mx-auto">
                {messages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}
                    style={{ animationDelay: `${idx * 0.1}s` }}
                  >
                    <div
                      className={`max-w-[70%] rounded-2xl px-5 py-3 shadow-lg transition-all duration-300 hover:scale-[1.02] ${
                        msg.role === 'user'
                          ? 'bg-gradient-to-br from-amber-600 to-amber-500 text-white shadow-amber-200'
                          : 'bg-white text-gray-800 border-2 border-gray-100 shadow-gray-200'
                      }`}
                    >
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex justify-start animate-fade-in">
                    <div className="bg-gradient-to-r from-white to-gray-50 text-gray-800 border-2 border-gray-200 rounded-2xl px-5 py-4 shadow-lg">
                      <div className="flex space-x-2">
                        <div className="w-3 h-3 bg-amber-500 rounded-full animate-bounce"></div>
                        <div className="w-3 h-3 bg-amber-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                        <div className="w-3 h-3 bg-amber-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
          <div className="border-t-2 border-gray-200 p-5 bg-gradient-to-r from-white via-gray-50 to-white shadow-lg">
            <div className="flex items-center space-x-3 max-w-4xl mx-auto">
              <input
                type="text"
                placeholder="Type your message..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={isLoading}
                className="flex-1 border-2 border-gray-300 rounded-xl px-5 py-3 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 disabled:opacity-50 transition-all duration-200 shadow-sm hover:shadow-md"
              />
              <button
                onClick={sendMessage}
                disabled={isLoading || !input.trim()}
                className="bg-gradient-to-r from-amber-600 to-amber-500 text-white px-8 py-3 rounded-xl hover:from-amber-700 hover:to-amber-600 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed font-semibold shadow-lg hover:shadow-xl hover:scale-105 active:scale-95 flex items-center space-x-2"
              >
                <span>Send</span>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Workflow Visualization - Right Side */}
        <div className="w-96 bg-gradient-to-b from-white via-gray-50 to-white border-l-2 border-gray-200 overflow-y-auto shadow-inner">
          <WorkflowVisualization state={state} />
        </div>
      </div>
    </div>
  )
}

export default ChatbotPage

