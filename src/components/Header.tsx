import { useChatbot } from '../contexts/ChatbotContext'

const Header = () => {
  const { openChatbot } = useChatbot()

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center">
            <h1 className="text-2xl font-bold text-black">// AutoEmporium</h1>
          </div>
          <nav className="hidden md:flex items-center space-x-8">
            <a href="#shop" className="text-black hover:text-gray-600 transition-colors">
              Shop
            </a>
            <a href="#compare" className="text-black hover:text-gray-600 transition-colors">
              Compare
            </a>
            <a href="#blog" className="text-black hover:text-gray-600 transition-colors">
              Blog
            </a>
            <a href="#about" className="text-black hover:text-gray-600 transition-colors">
              About Us
            </a>
          </nav>
          <button
            onClick={openChatbot}
            className="bg-amber-600 hover:bg-amber-700 text-white px-6 py-2 rounded-lg font-medium transition-colors"
          >
            Start Now
          </button>
        </div>
      </div>
    </header>
  )
}

export default Header

