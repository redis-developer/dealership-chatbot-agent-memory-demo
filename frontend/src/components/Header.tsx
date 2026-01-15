import { useState } from 'react'
import { useChatbot } from '../contexts/ChatbotContext'
import { useAuth } from '../contexts/AuthContext'
import Login from './Login'

const Header = () => {
  const { openFullPageChatbot } = useChatbot()
  const { userId, logout, isLoggedIn } = useAuth()
  const [showLogin, setShowLogin] = useState(false)

  return (
    <>
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
            <div className="flex items-center space-x-4">
              {isLoggedIn ? (
                <>
                  <span className="text-sm text-gray-600">User: {userId}</span>
                  <button
                    onClick={logout}
                    className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                  >
                    Logout
                  </button>
                  <button
                    onClick={openFullPageChatbot}
                    className="bg-amber-600 hover:bg-amber-700 text-white px-6 py-2 rounded-lg font-medium transition-colors"
                  >
                    Start Now
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setShowLogin(true)}
                  className="bg-amber-600 hover:bg-amber-700 text-white px-6 py-2 rounded-lg font-medium transition-colors"
                >
                  Login
                </button>
              )}
            </div>
          </div>
        </div>
      </header>
      {showLogin && <Login onClose={() => setShowLogin(false)} />}
    </>
  )
}

export default Header

