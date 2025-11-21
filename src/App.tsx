import Header from './components/Header'
import Hero from './components/Hero'
import Features from './components/Features'
import About from './components/About'
import Services from './components/Services'
import ChatbotButton from './components/ChatbotButton'
import { ChatbotProvider } from './contexts/ChatbotContext'

function App() {
  return (
    <ChatbotProvider>
      <div className="min-h-screen bg-white">
        <Header />
        <Hero />
        <Features />
        <About />
        <Services />
        <ChatbotButton />
      </div>
    </ChatbotProvider>
  )
}

export default App

