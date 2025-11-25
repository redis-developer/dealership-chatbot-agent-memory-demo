import { createContext, useContext, useState, ReactNode, useEffect } from 'react'

interface AuthContextType {
  userId: string | null
  login: (userId: string) => void
  logout: () => void
  isLoggedIn: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [userId, setUserId] = useState<string | null>(() => {
    // Check localStorage for existing user_id
    return localStorage.getItem('autoemporium_user_id')
  })

  useEffect(() => {
    // Persist user_id to localStorage whenever it changes
    if (userId) {
      localStorage.setItem('autoemporium_user_id', userId)
    } else {
      localStorage.removeItem('autoemporium_user_id')
    }
  }, [userId])

  const login = (newUserId: string) => {
    setUserId(newUserId)
  }

  const logout = () => {
    setUserId(null)
    // Clear session data on logout
    sessionStorage.removeItem('autoemporium_session_id')
  }

  return (
    <AuthContext.Provider value={{ userId, login, logout, isLoggedIn: !!userId }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

