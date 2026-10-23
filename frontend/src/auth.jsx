import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, getToken, setToken, setUnauthorizedHandler } from './api'

const AuthCtx = createContext(null)
export const useAuth = () => useContext(AuthCtx)

export const CREW = ['driver', 'conductor']
export const homeFor = (role) => (CREW.includes(role) ? '/driver' : role === 'executive' ? '/reports' : '/')

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(!getToken())

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    if (getToken()) {
      api.get('/auth/me').then(setUser).catch(logout).finally(() => setReady(true))
    }
  }, [logout])

  const login = useCallback(async (username, password) => {
    const res = await api.login(username, password)
    setToken(res.access_token)
    setUser(res.user)
    return res.user
  }, [])

  const value = useMemo(() => ({ user, ready, login, logout }), [user, ready, login, logout])
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>
}
