import { useEffect, useState } from 'react'
import { api, fmtDuration } from '../api'
import { ErrorBox, Field, Modal, Spinner, StopTimeline, useToast } from '../components/ui'

function RouteEditor({ route, depots, stops, onClose, onSaved, onStopCreated }) {
  const toast = useToast()
  const [f, setF] = useState({ code: route?.code || '', name: route?.name || '', depot_id: route?.depot_id || depots[0]?.id || '' })
  const [rows, setRows] = useState(route ? route.stops.map((s) => ({ stop_id: s.stop_id, planned_offset_min: s.planned_offset_min })) : [
    { stop_id: '', planned_offset_min: 0 }, { stop_id: '', planned_offset_min: 15 },
  ])
  const [newStop, setNewStop] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const upd = (i, patch) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const move = (i, d) => {
    const j = i + d
    if (j < 0 || j >= rows.length) return
    const next = [...rows];[next[i], next[j]] = [next[j], next[i]]
    setRows(next)
  }

  async function addStop(e) {
    e.preventDefault()
    try {
      const s = await api.post('/stops', { name: newStop.name, lat: Number(newStop.lat), lng: Number(newStop.lng) })
      onStopCreated(s)
      setNewStop(null)
      toast(`Stop "${s.name}" created. Pick it in a row below.`)
    } catch (err) { setError(err.message) }
  }

  async function save(e) {
    e.preventDefault()
    setBusy(true); setError('')
    const body = { ...f, depot_id: Number(f.depot_id), stops: rows.map((r) => ({ stop_id: Number(r.stop_id), planned_offset_min: Number(r.planned_offset_min) })) }
    try {
      route ? await api.put(`/routes/${route.id}`, body) : await api.post('/routes', body)
      toast('Route saved')
      onSaved()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <Modal title={route ? `Edit ${route.code}` : 'New route'} onClose={onClose}>
      <form onSubmit={save}>
        <div className="form-grid">
          <Field label="Code"><input className="input" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} required minLength={2} /></Field>
          <Field label="Depot">
            <select className="input" value={f.depot_id} onChange={(e) => setF({ ...f, depot_id: e.target.value })}>
              {depots.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
          <Field label="Name" className="full"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required minLength={3} /></Field>
        </div>
        <h3 style={{ marginTop: 16 }}>Stops, in order</h3>
        {rows.map((r, i) => (
          <div key={i} className="row" style={{ marginBottom: 6, flexWrap: 'nowrap' }}>
            <span className="muted" style={{ width: 20 }}>{i + 1}</span>
            <select className="input" value={r.stop_id} onChange={(e) => upd(i, { stop_id: e.target.value })} required>
              <option value="">Choose stop…</option>
              {stops.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <input className="input" type="number" min={0} max={600} style={{ width: 80 }} value={r.planned_offset_min}
              onChange={(e) => upd(i, { planned_offset_min: e.target.value })} aria-label="Minutes after start" title="Minutes after trip start" />
            <button type="button" className="btn btn-plain btn-sm" onClick={() => move(i, -1)} aria-label="Move up">↑</button>
            <button type="button" className="btn btn-plain btn-sm" onClick={() => move(i, 1)} aria-label="Move down">↓</button>
            <button type="button" className="btn btn-plain btn-sm" onClick={() => setRows(rows.filter((_, j) => j !== i))} disabled={rows.length <= 2} aria-label="Remove stop">✕</button>
          </div>
        ))}
        <div className="row">
          <button type="button" className="btn btn-outline btn-sm" onClick={() => setRows([...rows, { stop_id: '', planned_offset_min: (Number(rows[rows.length - 1]?.planned_offset_min) || 0) + 10 }])}>+ Add stop</button>
          <button type="button" className="btn btn-plain btn-sm" onClick={() => setNewStop({ name: '', lat: '', lng: '' })}>Create a new stop</button>
        </div>
        {newStop && (
          <div className="card" style={{ marginTop: 10, background: '#fafafa' }}>
            <div className="form-grid">
              <Field label="Stop name" className="full"><input className="input" value={newStop.name} onChange={(e) => setNewStop({ ...newStop, name: e.target.value })} /></Field>
              <Field label="Latitude"><input className="input" type="number" step="any" value={newStop.lat} onChange={(e) => setNewStop({ ...newStop, lat: e.target.value })} /></Field>
              <Field label="Longitude"><input className="input" type="number" step="any" value={newStop.lng} onChange={(e) => setNewStop({ ...newStop, lng: e.target.value })} /></Field>
            </div>
            <div className="actions"><button type="button" className="btn btn-sm" onClick={addStop}>Save stop</button></div>
          </div>
        )}
        <ErrorBox message={error} />
        <div className="actions">
          <button type="button" className="btn btn-plain" onClick={onClose}>Cancel</button>
          <button className="btn" disabled={busy}>Save route</button>
        </div>
      </form>
    </Modal>
  )
}

export default function RoutesAdmin() {
  const toast = useToast()
  const [routes, setRoutes] = useState(null)
  const [depots, setDepots] = useState([])
  const [stops, setStops] = useState([])
  const [editing, setEditing] = useState(null) // route | {} for new
  const [filter, setFilter] = useState('')
  const [error, setError] = useState('')

  const load = () => api.get('/routes').then(setRoutes).catch((e) => setError(e.message))
  useEffect(() => { load(); api.get('/depots').then(setDepots); api.get('/stops').then(setStops) }, [])

  async function remove(r) {
    if (!confirm(`Delete route ${r.code}?`)) return
    try { await api.del(`/routes/${r.id}`); toast('Route deleted'); load() } catch (e) { toast(e.message, 'err') }
  }

  const shown = (routes || []).filter((r) => `${r.code} ${r.name}`.toLowerCase().includes(filter.toLowerCase()))
  const depotName = (id) => depots.find((d) => d.id === id)?.name

  return (
    <div className="page">
      <div className="page-title">
        <h1>Routes</h1>
        <div className="row">
          <input className="input" style={{ width: 220 }} placeholder="Search routes…" value={filter} onChange={(e) => setFilter(e.target.value)} />
          <button className="btn" onClick={() => setEditing({})}>+ New route</button>
        </div>
      </div>
      <ErrorBox message={error} />
      {!routes ? <Spinner /> : shown.map((r) => (
        <article className="result-card" key={r.id}>
          <div className="row">
            <div>
              <div className="rc-title">{r.code} · {r.name}</div>
              <div className="rc-sub">{depotName(r.depot_id)} · {r.stops.length} stops · {fmtDuration(r.duration_min)} end to end</div>
            </div>
            <span className="spacer" />
            <button className="btn btn-outline btn-sm" onClick={() => setEditing(r)}>Edit</button>
            <button className="btn btn-plain btn-sm" onClick={() => remove(r)}>Delete</button>
          </div>
          <details style={{ marginTop: 8 }}>
            <summary className="linkbtn">Stops and planned timings</summary>
            <StopTimeline stops={r.stops} />
          </details>
        </article>
      ))}
      {editing && (
        <RouteEditor route={editing.id ? editing : null} depots={depots} stops={stops}
          onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }}
          onStopCreated={(s) => setStops((x) => [...x, s].sort((a, b) => a.name.localeCompare(b.name)))} />
      )}
    </div>
  )
}
