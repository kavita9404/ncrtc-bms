import { useEffect, useMemo, useState } from 'react'
import { api, addDays, mondayOf, todayISO } from '../api'
import { useAuth } from '../auth'
import { ErrorBox, Field, Modal, Pill, Spinner, useToast } from '../components/ui'

const dayLabel = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short', timeZone: 'UTC' })

function DutyModal({ depotId, data, driver, date, duty, onClose, onSaved }) {
  const toast = useToast()
  const [f, setF] = useState({
    vehicle_id: duty?.vehicle_id || '', route_id: duty?.route_id || '', conductor_id: duty?.conductor_id || '',
    start_time: duty?.start_time || '06:00', end_time: duty?.end_time || '14:00',
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const locked = duty?.ack_at

  async function save(e) {
    e.preventDefault()
    setBusy(true); setError('')
    const body = {
      date, driver_id: driver.id, vehicle_id: Number(f.vehicle_id), route_id: Number(f.route_id),
      conductor_id: f.conductor_id ? Number(f.conductor_id) : null, start_time: f.start_time, end_time: f.end_time,
    }
    try {
      duty ? await api.put(`/duties/${duty.id}`, body) : await api.post('/duties', body)
      toast('Duty saved as draft. Publish to notify the driver.')
      onSaved()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  async function remove() {
    try { await api.del(`/duties/${duty.id}`); toast('Duty removed'); onSaved() } catch (err) { setError(err.message) }
  }

  return (
    <Modal title={`${driver.full_name} · ${dayLabel(date)}`} onClose={onClose}>
      <form onSubmit={save}>
        <div className="form-grid">
          <Field label="Vehicle">
            <select className="input" value={f.vehicle_id} onChange={set('vehicle_id')} required disabled={locked}>
              <option value="">Select…</option>
              {data.vehicles.filter((v) => v.status === 'active').map((v) => <option key={v.id} value={v.id}>{v.reg_no}</option>)}
            </select>
          </Field>
          <Field label="Route">
            <select className="input" value={f.route_id} onChange={set('route_id')} required disabled={locked}>
              <option value="">Select…</option>
              {data.routes.map((r) => <option key={r.id} value={r.id}>{r.code} · {r.name}</option>)}
            </select>
          </Field>
          <Field label="Start"><input className="input" type="time" value={f.start_time} onChange={set('start_time')} required disabled={locked} /></Field>
          <Field label="End"><input className="input" type="time" value={f.end_time} onChange={set('end_time')} required disabled={locked} /></Field>
          <Field label="Conductor (optional)" className="full">
            <select className="input" value={f.conductor_id} onChange={set('conductor_id')} disabled={locked}>
              <option value="">None</option>
              {data.conductors.map((c) => <option key={c.id} value={c.id}>{c.full_name}</option>)}
            </select>
          </Field>
        </div>
        {locked && <div className="banner-warn" style={{ marginTop: 10 }}>The driver has acknowledged this duty, so it can no longer be edited.</div>}
        <ErrorBox message={error} />
        <div className="actions">
          {duty && !locked && <button type="button" className="btn btn-outline" onClick={remove}>Remove</button>}
          <span className="spacer" />
          <button type="button" className="btn btn-plain" onClick={onClose}>Cancel</button>
          {!locked && <button className="btn" disabled={busy}>{duty ? 'Save changes' : 'Assign duty'}</button>}
        </div>
      </form>
    </Modal>
  )
}

export default function Roster() {
  const { user } = useAuth()
  const toast = useToast()
  const [depots, setDepots] = useState([])
  const [depotId, setDepotId] = useState(user.depot_id ? String(user.depot_id) : '')
  const [week, setWeek] = useState(mondayOf(todayISO()))
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [modal, setModal] = useState(null)
  const today = todayISO()

  useEffect(() => {
    api.get('/depots').then((d) => { setDepots(d); if (!depotId && d.length) setDepotId(String(d[0].id)) })
  }, []) // eslint-disable-line

  async function load() {
    if (!depotId) return
    try { setData(await api.get('/roster', { depot_id: depotId, week_start: week })); setError('') }
    catch (e) { setError(e.message) }
  }
  useEffect(() => { setData(null); load() }, [depotId, week]) // eslint-disable-line

  const grid = useMemo(() => {
    const m = {}
    data?.duties.forEach((d) => { m[`${d.driver_id}|${d.date}`] = d })
    return m
  }, [data])
  const drafts = data?.duties.filter((d) => d.status === 'draft').length || 0

  async function publish() {
    try {
      const r = await api.post('/duties/publish', { depot_id: Number(depotId), date_from: week, date_to: addDays(week, 6) })
      toast(`${r.published} duties published. Drivers can now see them.`)
      load()
    } catch (e) { toast(e.message, 'err') }
  }
  async function copyLast() {
    try {
      const r = await api.post('/roster/copy-last-week', { depot_id: Number(depotId), week_start: week })
      toast(`Copied ${r.created} duties${r.skipped ? `, skipped ${r.skipped} that clashed` : ''}. They are drafts.`)
      load()
    } catch (e) { toast(e.message, 'err') }
  }

  return (
    <div className="page" style={{ maxWidth: 1400 }}>
      <div className="page-title">
        <h1>Weekly roster</h1>
        <div className="row">
          {user.role === 'admin' && (
            <select className="input" style={{ width: 200 }} value={depotId} onChange={(e) => setDepotId(e.target.value)} aria-label="Depot">
              {depots.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          )}
          <button className="btn btn-plain" onClick={() => setWeek(addDays(week, -7))}>‹ Prev</button>
          <b>{dayLabel(week)} – {dayLabel(addDays(week, 6))}</b>
          <button className="btn btn-plain" onClick={() => setWeek(addDays(week, 7))}>Next ›</button>
          <button className="btn btn-outline" onClick={copyLast}>Copy last week</button>
          <button className="btn" onClick={publish} disabled={!drafts}>Publish {drafts ? `(${drafts})` : ''}</button>
        </div>
      </div>
      <div className="row small muted" style={{ marginBottom: 10 }}>
        <Pill kind="draft">Draft</Pill> not visible to drivers <Pill kind="published">Published</Pill> <Pill kind="acknowledged">Acknowledged</Pill> Click an empty cell to assign a driver.
      </div>
      <ErrorBox message={error} />
      {!data ? <Spinner /> : (
        <div className="roster">
          <table>
            <thead>
              <tr>
                <th>Driver</th>
                {data.days.map((d) => <th key={d} className={d === today ? 'today' : ''}>{dayLabel(d)}</th>)}
              </tr>
            </thead>
            <tbody>
              {data.drivers.map((drv) => (
                <tr key={drv.id}>
                  <td><b>{drv.full_name}</b><br /><span className="muted small">{drv.username}</span></td>
                  {data.days.map((day) => {
                    const duty = grid[`${drv.id}|${day}`]
                    return (
                      <td key={day}>
                        {duty ? (
                          <div className={`cell-duty ${duty.status}`} onClick={() => setModal({ driver: drv, date: day, duty })} title={`${duty.route_name} · ${duty.status}`}>
                            <b>{duty.vehicle_reg}</b>{duty.route_code} · {duty.start_time}
                          </div>
                        ) : (
                          <button className="cell-empty" aria-label={`Assign ${drv.full_name} on ${day}`} onClick={() => setModal({ driver: drv, date: day })}>+</button>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {modal && <DutyModal depotId={depotId} data={data} {...modal} onClose={() => setModal(null)} onSaved={() => { setModal(null); load() }} />}
    </div>
  )
}
