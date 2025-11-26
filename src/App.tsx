import Header from './components/Header'
import Hero from './components/Hero'
import Features from './components/Features'
import About from './components/About'
import Services from './components/Services'
import ChatbotButton from './components/ChatbotButton'
import ChatbotPage from './components/ChatbotPage'
import { ChatbotProvider, useChatbot } from './contexts/ChatbotContext'
import { AuthProvider } from './contexts/AuthContext'

function AppContent() {
  const { isOpen, isFullPage } = useChatbot()

  if (isOpen && isFullPage) {
    return <ChatbotPage />
  }

  return (
    <div className="min-h-screen bg-white">
      <Header />
      <Hero />
      <Features />
      <About />
      <Services />
      <ChatbotButton />
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <ChatbotProvider>
        <AppContent />
      </ChatbotProvider>
    </AuthProvider>
  )
}

export default App

