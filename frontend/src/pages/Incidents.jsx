import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, fmtDateTime, label } from '../api'
import { useAuth } from '../auth'
import { ErrorBox, Field, Modal, Pill, Spinner, useToast, usePoll } from '../components/ui'

export function Sla({ i }) {
  if (['resolved', 'closed'].includes(i.status)) return <span className={`sla ${i.sla_breached ? 'breach' : 'ok'}`}>{i.sla_breached ? 'Breached' : 'Met'}</span>
  const m = i.sla_remaining_min
  const txt = m < 0 ? `${Math.abs(m)}m overdue` : m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m left` : `${m}m left`
  return <span className={`sla ${m < 0 ? 'breach' : ''}`}>{txt}</span>
}

function RaiseModal({ onClose, onCreated, vehicles }) {
  const toast = useToast()
  const [f, setF] = useState({ type: 'breakdown', severity: 'P2', description: '', vehicle_id: '' })
  const [photo, setPhoto] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const i = await api.post('/incidents', { ...f, vehicle_id: f.vehicle_id ? Number(f.vehicle_id) : null })
      if (photo) await api.upload(`/incidents/${i.id}/photo`, photo)
      toast(`Incident #${i.id} raised`)
      onCreated(i)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return (
    <Modal title="Raise an incident" onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <Field label="Type">
            <select className="input" value={f.type} onChange={set('type')}>
              <option value="breakdown">Breakdown</option><option value="accident">Accident</option>
              <option value="complaint">Complaint</option><option value="other">Other</option>
            </select>
          </Field>
          <Field label="Severity">
            <select className="input" value={f.severity} onChange={set('severity')}>
              <option value="P1">P1 · resolve in 1 hour</option><option value="P2">P2 · 4 hours</option><option value="P3">P3 · 24 hours</option>
            </select>
          </Field>
          <Field label="Vehicle (optional)" className="full">
            <select className="input" value={f.vehicle_id} onChange={set('vehicle_id')}>
              <option value="">None</option>
              {vehicles.map((v) => <option key={v.id} value={v.id}>{v.reg_no}</option>)}
            </select>
          </Field>
          <Field label="What happened?" className="full">
            <textarea className="input" value={f.description} onChange={set('description')} required minLength={5} maxLength={2000} />
          </Field>
          <Field label="Photo (optional, max 5 MB)" className="full">
            <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setPhoto(e.target.files[0] || null)} />
          </Field>
        </div>
        <ErrorBox message={error} />
        <div className="actions">
          <button type="button" className="btn btn-plain" onClick={onClose}>Cancel</button>
          <button className="btn" disabled={busy}>Raise incident</button>
        </div>
      </form>
    </Modal>
  )
}

export default function Incidents() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [f, setF] = useState({ status: '', severity: '', depot_id: '', mine: false })
  const [depots, setDepots] = useState([])
  const [vehicles, setVehicles] = useState([])
  const [raising, setRaising] = useState(false)
  const canRaise = user.role !== 'executive'
  const global = ['admin', 'control_operator', 'executive'].includes(user.role)

  useEffect(() => { api.get('/depots').then(setDepots); api.get('/vehicles').then(setVehicles).catch(() => {}) }, [])
  const [rows, error, reload] = usePoll(() => api.get('/incidents', { ...f, mine: f.mine || undefined }), 15000, [f])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  return (
    <div className="page">
      <div className="page-title">
        <h1>Incidents</h1>
        {canRaise && <button className="btn" onClick={() => setRaising(true)}>+ Raise incident</button>}
      </div>
      <div className="card row" style={{ marginBottom: 12 }}>
        <select className="input" style={{ width: 160 }} value={f.status} onChange={set('status')} aria-label="Status">
          <option value="">All statuses</option>
          {['open', 'acknowledged', 'in_progress', 'resolved', 'closed'].map((s) => <option key={s} value={s}>{label(s)}</option>)}
        </select>
        <select className="input" style={{ width: 140 }} value={f.severity} onChange={set('severity')} aria-label="Severity">
          <option value="">All severities</option><option>P1</option><option>P2</option><option>P3</option>
        </select>
        {global && (
          <select className="input" style={{ width: 180 }} value={f.depot_id} onChange={set('depot_id')} aria-label="Depot">
            <option value="">All depots</option>
            {depots.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        )}
        <label className="row" style={{ gap: 6 }}><input type="checkbox" checked={f.mine} onChange={set('mine')} /> Mine only</label>
        <span className="spacer" />
        <span className="muted small">{rows ? `${rows.length} incidents` : ''}</span>
      </div>
      <ErrorBox message={error} />
      {!rows ? <Spinner /> : (
        <div className="tbl-wrap">
          <table className="tbl">
            <thead><tr><th>#</th><th>Severity</th><th>Type</th><th>Description</th><th>Vehicle</th><th>Depot</th><th>Status</th><th>Assigned</th><th>SLA</th><th>Raised</th></tr></thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan={10} className="muted">No incidents match these filters.</td></tr>}
              {rows.map((i) => (
                <tr key={i.id} className="clickable" onClick={() => nav(`/incidents/${i.id}`)}>
                  <td>{i.id}</td>
                  <td><Pill kind={i.severity} /></td>
                  <td>{label(i.type)}</td>
                  <td style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{i.description}</td>
                  <td>{i.vehicle_reg || '—'}</td>
                  <td>{i.depot_code}</td>
                  <td><Pill kind={i.status} /></td>
                  <td>{i.assigned_to_name || <span className="muted">Unassigned</span>}</td>
                  <td><Sla i={i} /></td>
                  <td className="muted">{fmtDateTime(i.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {raising && <RaiseModal vehicles={vehicles} onClose={() => setRaising(false)} onCreated={(i) => { setRaising(false); nav(`/incidents/${i.id}`) }} />}
    </div>
  )
}
