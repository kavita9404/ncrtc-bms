import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { label } from '../api'

export function Pill({ kind, children }) {
  return <span className={`pill ${kind || ''}`}>{children ?? label(kind)}</span>
}

export function Modal({ title, onClose, children }) {
  useEffect(() => {
    const h = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-label={title}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  )
}

export function Field({ label: text, children, className = '' }) {
  return (
    <label className={`field ${className}`}>
      {text}
      {children}
    </label>
  )
}

export function StopTimeline({ stops }) {
  return (
    <ul className="timeline">
      {stops.map((s, i) => (
        <li key={i}>
          <span className="tm">{s.time ?? `+${s.planned_offset_min}m`}</span>
          <span>{s.name}</span>
        </li>
      ))}
    </ul>
  )
}

const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)

export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const id = useRef(0)
  const push = useCallback((text, kind = 'ok') => {
    const n = ++id.current
    setItems((x) => [...x, { n, text, kind }])
    setTimeout(() => setItems((x) => x.filter((i) => i.n !== n)), 4000)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => (
          <div key={t.n} className={`toast ${t.kind}`}>{t.text}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

/** Run `fn` now and then every `ms`. Re-runs when deps change. Returns [data, error, reload]. */
export function usePoll(fn, ms, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const fnRef = useRef(fn)
  fnRef.current = fn
  const reload = useCallback(async () => {
    try {
      setData(await fnRef.current())
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [])
  useEffect(() => {
    let stop = false
    setData(null)
    reload()
    if (!ms) return
    const t = setInterval(() => !stop && !document.hidden && reload(), ms)
    return () => {
      stop = true
      clearInterval(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return [data, error, reload]
}

export const Spinner = () => <p className="muted">Loading…</p>
export const ErrorBox = ({ message }) => (message ? <div className="error">{message}</div> : null)
