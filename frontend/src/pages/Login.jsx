import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { homeFor, useAuth } from '../auth'
import { ErrorBox, Field } from '../components/ui'

const DEMO = [
  ['Admin', 'admin1'],
  ['Depot manager', 'manager_nsd'],
  ['Control room', 'control1'],
  ['Driver', 'driver1'],
  ['Executive', 'exec1'],
]

export default function Login() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const u = await login(username.trim(), password)
      nav(homeFor(u.role), { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <section className="login-art">
        <h1>
          Every feeder bus
          <br />
          on the NCR corridor.
        </h1>
        <p>Live tracking, duty rosters, incident handling and driver notices for NCRTC's feeder network, in one place.</p>
      </section>
      <section className="login-form">
        <form onSubmit={submit}>
          <h2>Log in</h2>
          <Field label="Username">
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username" required />
          </Field>
          <Field label="Password">
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </Field>
          <ErrorBox message={error} />
          <button className="btn btn-lg" disabled={busy}>{busy ? 'Signing in…' : 'LOG IN'}</button>
          <div>
            <small className="muted">Demo accounts (password: <b>password</b>)</small>
            <div className="demo-chips">
              {DEMO.map(([name, u]) => (
                <button type="button" key={u} className="chip" onClick={() => { setUsername(u); setPassword('password') }}>
                  {name}
                </button>
              ))}
            </div>
          </div>
        </form>
      </section>
    </div>
  )
}
