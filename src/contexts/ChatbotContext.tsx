import { createContext, useContext, useState, ReactNode } from 'react'

interface ChatbotContextType {
  isOpen: boolean
  isFullPage: boolean
  openChatbot: () => void
  openFullPageChatbot: () => void
  closeChatbot: () => void
}

const ChatbotContext = createContext<ChatbotContextType | undefined>(undefined)

export const ChatbotProvider = ({ children }: { children: ReactNode }) => {
  const [isOpen, setIsOpen] = useState(false)
  const [isFullPage, setIsFullPage] = useState(false)

  const openChatbot = () => {
    setIsOpen(true)
    setIsFullPage(false)
  }
  
  const openFullPageChatbot = () => {
    setIsOpen(true)
    setIsFullPage(true)
  }
  
  const closeChatbot = () => {
    setIsOpen(false)
    setIsFullPage(false)
  }

  return (
    <ChatbotContext.Provider value={{ isOpen, isFullPage, openChatbot, openFullPageChatbot, closeChatbot }}>
      {children}
    </ChatbotContext.Provider>
  )
}

export const useChatbot = () => {
  const context = useContext(ChatbotContext)
  if (context === undefined) {
    throw new Error('useChatbot must be used within a ChatbotProvider')
  }
  return context
}

