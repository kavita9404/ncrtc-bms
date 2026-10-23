import { useEffect, useRef, useState } from 'react'
import { api, fmtDateTime, fmtDuration, label, minutesBetween, todayISO } from '../api'
import { useAuth } from '../auth'
import { ErrorBox, Pill, StopTimeline, useToast } from '../components/ui'

function DutyTicket({ d, onAck }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const first = d.stops[0], last = d.stops[d.stops.length - 1]
  const isToday = d.date === todayISO()

  async function ack() {
    setBusy(true)
    try { await api.post(`/duties/${d.id}/ack`); toast('Duty acknowledged'); onAck() }
    catch (e) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  return (
    <div className="ticket">
      <div className="t-top">
        <div className="row"><Pill kind={d.status} /><span className="muted small">{isToday ? 'Today' : d.date}</span></div>
        <div className="t-route">{d.route_code} · {d.route_name}</div>
        <div className="t-times">
          <div><b>{first.time}</b><div className="muted small">{first.name}</div></div>
          <div className="rc-times" style={{ flex: 1 }}><div className="dur"><span>{fmtDuration(minutesBetween(first.time, last.time))}</span></div></div>
          <div style={{ textAlign: 'right' }}><b>{last.time}</b><div className="muted small">{last.name}</div></div>
        </div>
        <dl className="kv" style={{ margin: 0 }}>
          <dt>Bus</dt><dd>{d.vehicle_reg}</dd>
          <dt>Duty hours</dt><dd>{d.start_time} – {d.end_time}</dd>
          {d.conductor_name && <><dt>Conductor</dt><dd>{d.conductor_name}</dd></>}
        </dl>
      </div>
      <div className="tear" />
      <div className="t-bottom">
        {d.ack_at ? <p style={{ margin: 0 }} className="muted">Acknowledged at {fmtDateTime(d.ack_at)}</p>
          : <button className="btn btn-lg" style={{ width: '100%' }} onClick={ack} disabled={busy}>ACKNOWLEDGE DUTY</button>}
        <details style={{ marginTop: 10 }}>
          <summary className="linkbtn">Stops and timings</summary>
          <StopTimeline stops={d.stops} />
        </details>
      </div>
    </div>
  )
}

function Panic({ onSent }) {
  const toast = useToast()
  const [armed, setArmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const t = useRef(null)
  useEffect(() => () => clearTimeout(t.current), [])

  const position = () => new Promise((res) => {
    if (!navigator.geolocation) return res({})
    navigator.geolocation.getCurrentPosition(
      (p) => res({ lat: p.coords.latitude, lng: p.coords.longitude }), () => res({}), { timeout: 3000, maximumAge: 30000 })
  })

  async function press() {
    if (!armed) {
      setArmed(true)
      t.current = setTimeout(() => setArmed(false), 4000)
      return
    }
    clearTimeout(t.current)
    setBusy(true)
    try {
      const inc = await api.post('/incidents/panic', await position())
      toast(`Alert sent. Incident #${inc.id} raised as P1. Help is on the way.`)
      onSent()
    } catch (e) { toast(e.message, 'err') } finally { setBusy(false); setArmed(false) }
  }
  return (
    <>
      <button className={`panic ${armed ? 'armed' : ''}`} onClick={press} disabled={busy}>
        {busy ? 'SENDING…' : armed ? 'TAP AGAIN TO SEND ALERT' : 'PANIC / EMERGENCY'}
      </button>
      <p className="muted small" style={{ textAlign: 'center', margin: '8px 0 0' }}>Tap twice to raise a P1 incident with your bus and location.</p>
    </>
  )
}

export default function DriverApp() {
  const { user, logout } = useAuth()
  const toast = useToast()
  const [tab, setTab] = useState('duty')
  const [duties, setDuties] = useState(null)
  const [notices, setNotices] = useState([])
  const [mine, setMine] = useState([])
  const [error, setError] = useState('')

  const load = () => {
    api.get('/me/duties').then(setDuties).catch((e) => setError(e.message))
    api.get('/notices').then(setNotices).catch(() => {})
    api.get('/incidents').then(setMine).catch(() => {})
  }
  useEffect(() => { load() }, [])

  const unread = notices.filter((n) => !n.read_at).length

  async function open(n) {
    if (n.read_at) return
    try {
      const upd = await api.post(`/notices/${n.id}/read`)
      setNotices((all) => all.map((x) => (x.id === n.id ? upd : x)))
    } catch { /* ignore */ }
  }
  async function ackNotice(n) {
    try {
      const upd = await api.post(`/notices/${n.id}/ack`)
      setNotices((all) => all.map((x) => (x.id === n.id ? upd : x)))
      toast('Confirmed')
    } catch (e) { toast(e.message, 'err') }
  }

  return (
    <div className="driver">
      <header className="d-head">
        <div>
          <h1>Hi, {user.full_name.split(' ')[0]}</h1>
          <small>{label(user.role)}</small>
        </div>
        <button className="btn-ghost-light" onClick={logout}>Log out</button>
      </header>
      <main className="d-body">
        <ErrorBox message={error} />
        {tab === 'duty' && (
          <>
            {!duties ? <p className="muted">Loading…</p> : duties.length === 0 ? (
              <div className="card"><b>No published duty</b><p className="muted">Your depot manager has not published a duty for the next 3 days.</p></div>
            ) : duties.map((d) => <DutyTicket key={d.id} d={d} onAck={load} />)}
            <div className="card"><Panic onSent={load} /></div>
          </>
        )}
        {tab === 'notices' && (
          notices.length === 0 ? <div className="card muted">No notices.</div> : notices.map((n) => (
            <article key={n.id} className={`notice-item ${n.read_at ? '' : 'unread'}`} onClick={() => open(n)}>
              <h3>{!n.read_at && <i className="unread-dot" />} {n.title}</h3>
              <div className="muted small">{fmtDateTime(n.publish_at)} · {n.author_name}</div>
              <div className="body">{n.body}</div>
              {n.requires_ack && (n.ack_at ? <Pill kind="green">Confirmed</Pill>
                : <button className="btn" style={{ marginTop: 10 }} onClick={(e) => { e.stopPropagation(); ackNotice(n) }}>I have read and understood</button>)}
            </article>
          ))
        )}
        {tab === 'alerts' && (
          mine.length === 0 ? <div className="card muted">You have not raised any incidents.</div> : mine.map((i) => (
            <article key={i.id} className="notice-item">
              <h3>#{i.id} <Pill kind={i.severity} /> <Pill kind={i.status} /></h3>
              <div>{i.description}</div>
              <div className="muted small">{fmtDateTime(i.created_at)}</div>
            </article>
          ))
        )}
      </main>
      <nav className="d-tabs">
        <div className="inner">
          <button className={tab === 'duty' ? 'active' : ''} onClick={() => setTab('duty')}>My duty</button>
          <button className={tab === 'notices' ? 'active' : ''} onClick={() => setTab('notices')}>Notices{unread > 0 && <span className="badge">{unread}</span>}</button>
          <button className={tab === 'alerts' ? 'active' : ''} onClick={() => setTab('alerts')}>My alerts</button>
        </div>
      </nav>
    </div>
  )
}
