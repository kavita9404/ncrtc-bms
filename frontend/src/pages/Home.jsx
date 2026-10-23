import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtDuration, label, minutesBetween, todayISO } from '../api'
import { useAuth } from '../auth'
import { ErrorBox, Pill, Spinner, StopTimeline, usePoll } from '../components/ui'

const SHIFTS = { morning: [0, 10], midday: [10, 14], evening: [14, 24] }

function ResultCard({ d }) {
  const [open, setOpen] = useState(false)
  const first = d.stops[0], last = d.stops[d.stops.length - 1]
  return (
    <article className={`result-card s-${d.status}`}>
      <div className="rc-top">
        <div>
          <div className="rc-title">{d.route_code} · {d.route_name}</div>
          <div className="rc-sub">Bus {d.vehicle_reg}</div>
        </div>
        <div className="rc-times">
          <div>
            <div className="t">{first.time}</div>
            <div className="rc-sub">{first.name}</div>
          </div>
          <div className="dur"><span>{fmtDuration(minutesBetween(first.time, last.time))}</span></div>
          <div style={{ textAlign: 'right' }}>
            <div className="t">{last.time}</div>
            <div className="rc-sub">{last.name}</div>
          </div>
        </div>
        <div className="rc-right">
          <Pill kind={d.status} />
          <Link className="btn btn-sm" to={`/live?vehicle=${d.vehicle_id}`}>Track live</Link>
        </div>
      </div>
      <div className="rc-bottom">
        <span className="muted">
          Driver <b>{d.driver_name}</b>
          {d.conductor_name && <> · Conductor <b>{d.conductor_name}</b></>}
          {d.ack_at && <> · acknowledged</>}
        </span>
        <span className="row">
          <Link to={`/history?vehicle=${d.vehicle_id}&day=${d.date}`} className="small">Trip history</Link>
          <button className="linkbtn" onClick={() => setOpen(!open)}>{open ? 'Hide stops' : `View ${d.stops.length} stops`}</button>
        </span>
      </div>
      {open && <StopTimeline stops={d.stops} />}
    </article>
  )
}

export default function Home() {
  const { user } = useAuth()
  const global = user.role !== 'depot_manager'
  const [depots, setDepots] = useState([])
  const [routes, setRoutes] = useState([])
  const [q, setQ] = useState({ depot_id: user.depot_id || '', route_id: '', day: todayISO() })
  const [submitted, setSubmitted] = useState(q)
  const [statuses, setStatuses] = useState({ draft: true, published: true, acknowledged: true })
  const [shifts, setShifts] = useState({ morning: true, midday: true, evening: true })
  const [sort, setSort] = useState('time')

  const [summary] = usePoll(() => api.get('/reports/summary'), 15000, [])
  const [results, error] = usePoll(() => api.get('/duties/search', { ...submitted }), 0, [submitted])

  useEffect(() => { api.get('/depots').then(setDepots) }, [])
  useEffect(() => {
    api.get('/routes', { depot_id: q.depot_id || undefined }).then(setRoutes)
  }, [q.depot_id])

  const shown = useMemo(() => {
    const list = (results || []).filter((d) => {
      if (!statuses[d.status]) return false
      const h = Number(d.start_time.slice(0, 2))
      return Object.entries(SHIFTS).some(([k, [a, b]]) => shifts[k] && h >= a && h < b)
    })
    return list.sort((a, b) => sort === 'time' ? a.start_time.localeCompare(b.start_time) : a.route_code.localeCompare(b.route_code))
  }, [results, statuses, shifts, sort])

  const set = (k) => (e) => setQ({ ...q, [k]: e.target.value, ...(k === 'depot_id' ? { route_id: '' } : {}) })
  const toggle = (setter, state, key) => () => setter({ ...state, [key]: !state[key] })

  return (
    <>
      <section className="hero">
        <div className="hero-inner">
          <h1>Find a bus duty. Track it live.</h1>
          <form className="search-box" onSubmit={(e) => { e.preventDefault(); setSubmitted({ ...q }) }}>
            <div className="cell">
              <small>Depot</small>
              <select value={q.depot_id} onChange={set('depot_id')} disabled={!global}>
                {global && <option value="">All depots</option>}
                {depots.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
            <div className="cell">
              <small>Route</small>
              <select value={q.route_id} onChange={set('route_id')}>
                <option value="">All routes</option>
                {routes.map((r) => <option key={r.id} value={r.id}>{r.code} · {r.name}</option>)}
              </select>
            </div>
            <div className="cell">
              <small>Date</small>
              <input type="date" value={q.day} onChange={set('day')} required />
            </div>
            <div className="go"><button className="btn btn-lg">SEARCH BUSES</button></div>
          </form>
        </div>
      </section>

      <div className="page" style={{ paddingTop: 8 }}>
        {summary && (
          <div className="tiles">
            <div className="tile"><b>{summary.duties_today}</b><span>Buses on duty today</span></div>
            <div className="tile"><b>{summary.vehicles_total}</b><span>Buses in fleet</span></div>
            <div className="tile alert"><b>{summary.open_incidents}</b><span>Open incidents ({summary.open_p1} P1)</span></div>
            <div className="tile alert"><b>{summary.sla_breached}</b><span>SLA breaches</span></div>
          </div>
        )}
        <ErrorBox message={error} />
        <div className="results">
          <aside className="card filters">
            <h3>Status</h3>
            {Object.keys(statuses).map((s) => (
              <label key={s}><input type="checkbox" checked={statuses[s]} onChange={toggle(setStatuses, statuses, s)} /> {label(s)}</label>
            ))}
            <h3>Departure</h3>
            {Object.entries({ morning: 'Before 10:00', midday: '10:00 – 14:00', evening: 'After 14:00' }).map(([k, t]) => (
              <label key={k}><input type="checkbox" checked={shifts[k]} onChange={toggle(setShifts, shifts, k)} /> {t}</label>
            ))}
            <h3>Sort by</h3>
            <select className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="time">Departure time</option>
              <option value="route">Route code</option>
            </select>
          </aside>
          <section>
            <p className="muted" style={{ marginTop: 0 }}>
              <b>{shown.length}</b> duties found
            </p>
            {!results ? <Spinner /> : shown.length === 0 ? (
              <div className="card muted">No duties match. Try another date or depot.</div>
            ) : shown.map((d) => <ResultCard key={d.id} d={d} />)}
          </section>
        </div>
      </div>
    </>
  )
}
