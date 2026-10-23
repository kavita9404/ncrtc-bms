import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, fmtDateTime, label } from '../api'
import { useAuth } from '../auth'
import { ErrorBox, Field, Pill, Spinner, useToast } from '../components/ui'
import { Sla } from './Incidents'

const NEXT = {
  open: ['acknowledged'],
  acknowledged: ['in_progress'],
  in_progress: ['resolved'],
  resolved: ['closed', 'in_progress'],
  closed: [],
}

export default function IncidentDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const toast = useToast()
  const [inc, setInc] = useState(null)
  const [people, setPeople] = useState([])
  const [error, setError] = useState('')
  const [to, setTo] = useState('')
  const [note, setNote] = useState('')
  const [freeNote, setFreeNote] = useState('')

  const canManage = ['admin', 'control_operator', 'depot_manager'].includes(user.role)
  const load = () => api.get(`/incidents/${id}`).then((i) => { setInc(i); setTo(NEXT[i.status][0] || '') }).catch((e) => setError(e.message))
  useEffect(() => { load() }, [id]) // eslint-disable-line
  useEffect(() => {
    if (canManage) api.get('/users').then((u) => setPeople(u.filter((x) => ['admin', 'control_operator', 'depot_manager'].includes(x.role)))).catch(() => {})
  }, [canManage])

  async function act(fn, ok) {
    setError('')
    try { setInc(await fn()); toast(ok); return true } catch (e) { setError(e.message); return false }
  }
  async function changeStatus(e) {
    e.preventDefault()
    if (await act(() => api.post(`/incidents/${id}/transition`, { to_status: to, note }), `Moved to ${label(to)}`)) {
      setNote('')
      load()
    }
  }

  if (!inc) return <div className="page">{error ? <ErrorBox message={error} /> : <Spinner />}</div>
  const next = NEXT[inc.status]
  const day = inc.created_at.slice(0, 10)

  return (
    <div className="page">
      <p><Link to="/incidents">‹ All incidents</Link></p>
      <div className="page-title">
        <h1>#{inc.id} · {label(inc.type)}</h1>
        <div className="row"><Pill kind={inc.severity} /><Pill kind={inc.status} /></div>
      </div>
      <ErrorBox message={error} />
      <div className="grid-2" style={{ alignItems: 'start' }}>
        <section className="card">
          <p style={{ marginTop: 0, fontSize: 16 }}>{inc.description}</p>
          {inc.photo_url && <a href={inc.photo_url} target="_blank" rel="noreferrer"><img src={inc.photo_url} alt="Incident" style={{ maxWidth: '100%', borderRadius: 8, marginBottom: 8 }} /></a>}
          <dl className="kv">
            <dt>Raised by</dt><dd>{inc.raised_by_name}</dd>
            <dt>Raised at</dt><dd>{fmtDateTime(inc.created_at)}</dd>
            <dt>Vehicle</dt><dd>{inc.vehicle_reg || '—'}</dd>
            <dt>Depot</dt><dd>{inc.depot_code}</dd>
            <dt>Assigned to</dt><dd>{inc.assigned_to_name || 'Unassigned'}</dd>
            <dt>SLA</dt><dd><Sla i={inc} /> <span className="muted small">due {fmtDateTime(inc.sla_due_at)}</span></dd>
            {inc.lat && <><dt>Location</dt><dd><a href={`https://www.openstreetmap.org/?mlat=${inc.lat}&mlon=${inc.lng}#map=16/${inc.lat}/${inc.lng}`} target="_blank" rel="noreferrer">{inc.lat.toFixed(4)}, {inc.lng.toFixed(4)}</a></dd></>}
          </dl>
          {inc.vehicle_id && canManage && (
            <Link className="btn btn-outline btn-sm" to={`/history?vehicle=${inc.vehicle_id}&day=${day}`}>Show this vehicle's path</Link>
          )}

          {canManage && (
            <>
              <hr style={{ border: 0, borderTop: '1px solid var(--line)', margin: '16px 0' }} />
              <h3>Assign</h3>
              <div className="row">
                <select className="input" style={{ flex: 1 }} value={inc.assigned_to || ''} onChange={(e) => e.target.value && act(() => api.post(`/incidents/${id}/assign`, { assignee_id: Number(e.target.value) }), 'Assigned')} aria-label="Assignee">
                  <option value="">Choose a person…</option>
                  {people.map((p) => <option key={p.id} value={p.id}>{p.full_name} ({label(p.role)})</option>)}
                </select>
                <button className="btn btn-plain" onClick={() => act(() => api.post(`/incidents/${id}/assign`, { assignee_id: user.id }), 'Assigned to you')}>Assign to me</button>
              </div>
            </>
          )}
        </section>

        <section className="card">
          {canManage && next.length > 0 && (
            <form onSubmit={changeStatus} style={{ marginBottom: 16 }}>
              <h3>Update status</h3>
              <div className="form-grid">
                <Field label="Move to">
                  <select className="input" value={to} onChange={(e) => setTo(e.target.value)}>
                    {next.map((s) => <option key={s} value={s}>{label(s)}</option>)}
                  </select>
                </Field>
                <Field label="Note (required)">
                  <input className="input" value={note} onChange={(e) => setNote(e.target.value)} required minLength={3} placeholder="What was done?" />
                </Field>
              </div>
              <div className="actions"><button className="btn">Update</button></div>
            </form>
          )}
          <h3>Timeline</h3>
          <ul className="events">
            {inc.events.map((e) => (
              <li key={e.id}>
                <div>
                  {e.from_status && e.from_status !== e.to_status ? <><Pill kind={e.from_status} /> → <Pill kind={e.to_status} /></> : <Pill kind={e.to_status} />}{' '}
                  <span className="muted small">{e.actor_name} · {fmtDateTime(e.ts)}</span>
                </div>
                {e.note && <div>{e.note}</div>}
              </li>
            ))}
          </ul>
          {user.role !== 'executive' && (
            <form className="row" style={{ marginTop: 12 }} onSubmit={async (e) => { e.preventDefault(); if (await act(() => api.post(`/incidents/${id}/notes`, { note: freeNote }), 'Note added')) setFreeNote('') }}>
              <input className="input" style={{ flex: 1 }} placeholder="Add a note…" value={freeNote} onChange={(e) => setFreeNote(e.target.value)} required />
              <button className="btn btn-plain">Add</button>
            </form>
          )}
        </section>
      </div>
    </div>
  )
}
