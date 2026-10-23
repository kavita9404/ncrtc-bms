import { useEffect, useState } from 'react'
import { api, fmtDateTime, label } from '../api'
import { useAuth } from '../auth'
import { ErrorBox, Field, Modal, Pill, Spinner, useToast } from '../components/ui'

const ROLE_OPTIONS = ['driver', 'conductor', 'depot_manager', 'control_operator']

function audienceText(a, depots) {
  if (a.type === 'all') return 'Everyone'
  if (a.type === 'depot') return `Depot: ${depots.find((d) => d.id === a.depot_id)?.name || a.depot_id}`
  return `Role: ${label(a.role)}s`
}

function CreateModal({ depots, onClose, onCreated }) {
  const toast = useToast()
  const [f, setF] = useState({ title: '', body: '', type: 'role', depot_id: '', role: 'driver', requires_ack: false })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  async function submit(e) {
    e.preventDefault()
    setBusy(true); setError('')
    const audience = f.type === 'all' ? { type: 'all' } : f.type === 'depot' ? { type: 'depot', depot_id: Number(f.depot_id) } : { type: 'role', role: f.role }
    try {
      await api.post('/notices', { title: f.title, body: f.body, audience, requires_ack: f.requires_ack })
      toast('Notice published')
      onCreated()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return (
    <Modal title="New notice" onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <Field label="Title" className="full"><input className="input" value={f.title} onChange={set('title')} required minLength={3} /></Field>
          <Field label="Message" className="full"><textarea className="input" style={{ minHeight: 120 }} value={f.body} onChange={set('body')} required /></Field>
          <Field label="Send to">
            <select className="input" value={f.type} onChange={set('type')}>
              <option value="role">A role</option><option value="depot">A depot</option><option value="all">Everyone</option>
            </select>
          </Field>
          {f.type === 'role' && (
            <Field label="Role"><select className="input" value={f.role} onChange={set('role')}>{ROLE_OPTIONS.map((r) => <option key={r} value={r}>{label(r)}</option>)}</select></Field>
          )}
          {f.type === 'depot' && (
            <Field label="Depot">
              <select className="input" value={f.depot_id} onChange={set('depot_id')} required>
                <option value="">Select…</option>{depots.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </Field>
          )}
          <label className="row full" style={{ gap: 8 }}><input type="checkbox" checked={f.requires_ack} onChange={set('requires_ack')} /> Require acknowledgement (reader must tap Confirm)</label>
        </div>
        <ErrorBox message={error} />
        <div className="actions">
          <button type="button" className="btn btn-plain" onClick={onClose}>Cancel</button>
          <button className="btn" disabled={busy}>Publish now</button>
        </div>
      </form>
    </Modal>
  )
}

function Receipts({ notice, onClose }) {
  const [data, setData] = useState(null)
  const [filter, setFilter] = useState('all')
  useEffect(() => { api.get(`/notices/${notice.id}/receipts`).then(setData) }, [notice.id])
  const rows = (data?.recipients || []).filter((r) => filter === 'all' || (filter === 'read' ? r.read_at : !r.read_at))
  return (
    <Modal title={`Read receipts: ${notice.title}`} onClose={onClose}>
      {!data ? <Spinner /> : (
        <>
          <div className="row" style={{ marginBottom: 10 }}>
            <b>{data.read}/{data.total} read</b>
            {data.requires_ack && <span>· <b>{data.acknowledged}</b> acknowledged</span>}
            <span className="spacer" />
            <select className="input" style={{ width: 140 }} value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="all">Everyone</option><option value="read">Read</option><option value="unread">Not read</option>
            </select>
          </div>
          <div className="tbl-wrap" style={{ maxHeight: 360, overflow: 'auto' }}>
            <table className="tbl">
              <thead><tr><th>Name</th><th>Role</th><th>Read</th>{data.requires_ack && <th>Ack</th>}</tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.user_id}>
                    <td>{r.full_name}</td><td>{label(r.role)}</td>
                    <td>{r.read_at ? fmtDateTime(r.read_at) : <Pill kind="grey">Not read</Pill>}</td>
                    {data.requires_ack && <td>{r.ack_at ? <Pill kind="green">Done</Pill> : '—'}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <div className="actions"><button className="btn btn-plain" onClick={onClose}>Close</button></div>
    </Modal>
  )
}

export default function Notices() {
  const { user } = useAuth()
  const isAdmin = user.role === 'admin'
  const [rows, setRows] = useState(null)
  const [depots, setDepots] = useState([])
  const [creating, setCreating] = useState(false)
  const [viewing, setViewing] = useState(null)
  const [error, setError] = useState('')
  const load = () => api.get('/notices').then(setRows).catch((e) => setError(e.message))
  useEffect(() => { load(); api.get('/depots').then(setDepots) }, [])

  return (
    <div className="page">
      <div className="page-title">
        <h1>Notices</h1>
        {isAdmin && <button className="btn" onClick={() => setCreating(true)}>+ New notice</button>}
      </div>
      <ErrorBox message={error} />
      {!rows ? <Spinner /> : rows.length === 0 ? <div className="card muted">No notices yet.</div> : rows.map((n) => (
        <article className="result-card" key={n.id}>
          <div className="row">
            <div className="rc-title">{n.title}</div>
            {n.requires_ack && <Pill kind="amber">Ack required</Pill>}
            <span className="spacer" />
            <span className="muted small">{audienceText(n.audience, depots)} · {fmtDateTime(n.publish_at)} · {n.author_name}</span>
          </div>
          <p style={{ whiteSpace: 'pre-wrap', margin: '10px 0' }}>{n.body}</p>
          {isAdmin && <button className="btn btn-outline btn-sm" onClick={() => setViewing(n)}>Read receipts</button>}
        </article>
      ))}
      {creating && <CreateModal depots={depots} onClose={() => setCreating(false)} onCreated={() => { setCreating(false); load() }} />}
      {viewing && <Receipts notice={viewing} onClose={() => setViewing(null)} />}
    </div>
  )
}
