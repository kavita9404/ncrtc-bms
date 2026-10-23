import { useEffect, useRef, useState } from 'react'
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { useSearchParams } from 'react-router-dom'
import { api, addDays, fmtTime, todayISO } from '../api'
import { useAuth } from '../auth'
import { ErrorBox, Field } from '../components/ui'

function Fit({ points }) {
  const map = useMap()
  useEffect(() => {
    if (points.length > 1) map.fitBounds(points, { padding: [40, 40] })
  }, [points, map])
  return null
}

export default function History() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const [vehicles, setVehicles] = useState([])
  const [vehicleId, setVehicleId] = useState(params.get('vehicle') || '')
  const [day, setDay] = useState(params.get('day') || addDays(todayISO(), -1))
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  // replay
  const [idx, setIdx] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(5)
  const timer = useRef(null)

  useEffect(() => { api.get('/vehicles').then(setVehicles) }, [])

  async function load(v = vehicleId, d = day) {
    if (!v) return
    setLoading(true); setError(''); setPlaying(false); setIdx(0)
    try { setData(await api.get(`/avls/vehicles/${v}/history`, { day: d })) }
    catch (e) { setError(e.message); setData(null) }
    finally { setLoading(false) }
  }
  useEffect(() => { if (params.get('vehicle')) load(params.get('vehicle'), day) }, []) // eslint-disable-line

  const pings = data?.pings || []
  const pts = pings.map((p) => [p.lat, p.lng])

  useEffect(() => {
    clearInterval(timer.current)
    if (playing) {
      timer.current = setInterval(() => {
        setIdx((i) => {
          if (i >= pings.length - 1) { setPlaying(false); return i }
          return Math.min(pings.length - 1, i + speed)
        })
      }, 250)
    }
    return () => clearInterval(timer.current)
  }, [playing, speed, pings.length])

  const cur = pings[idx]

  return (
    <div className="hist-layout">
      <form className="hist-bar" onSubmit={(e) => { e.preventDefault(); load() }}>
        <Field label="Vehicle">
          <select className="input" value={vehicleId} onChange={(e) => setVehicleId(e.target.value)} required>
            <option value="">Select a bus…</option>
            {vehicles.map((v) => <option key={v.id} value={v.id}>{v.reg_no}</option>)}
          </select>
        </Field>
        <Field label="Date">
          <input className="input" type="date" value={day} max={todayISO()} onChange={(e) => setDay(e.target.value)} required />
        </Field>
        <button className="btn" disabled={loading}>{loading ? 'Loading…' : 'Show path'}</button>
        {data && (
          <span className="muted">
            <b>{data.summary.distance_km} km</b> · {data.summary.pings} pings · max {data.summary.max_speed_kmh} km/h
            {data.summary.first_ts && <> · {fmtTime(data.summary.first_ts)}–{fmtTime(data.summary.last_ts)}</>}
          </span>
        )}
      </form>
      <ErrorBox message={error} />
      <div className="map-area" style={{ flex: 1 }}>
        <MapContainer center={[28.62, 77.33]} zoom={11}>
          <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <Fit points={pts} />
          {pts.length > 1 && <Polyline positions={pts} pathOptions={{ color: '#d84e55', weight: 4 }} />}
          {pts.length > 1 && <CircleMarker center={pts[0]} radius={8} pathOptions={{ color: '#fff', fillColor: '#2e9d5b', fillOpacity: 1 }}><Tooltip>Start {fmtTime(pings[0].ts)}</Tooltip></CircleMarker>}
          {pts.length > 1 && <CircleMarker center={pts[pts.length - 1]} radius={8} pathOptions={{ color: '#fff', fillColor: '#333', fillOpacity: 1 }}><Tooltip>End {fmtTime(pings[pings.length - 1].ts)}</Tooltip></CircleMarker>}
          {cur && <CircleMarker center={[cur.lat, cur.lng]} radius={10} pathOptions={{ color: '#fff', weight: 3, fillColor: '#2b6cb0', fillOpacity: 1 }} />}
        </MapContainer>
        {data && pings.length === 0 && (
          <div className="alerts"><div className="banner-warn">No GPS data for this bus on {day}. Seeded history exists for 12 buses on yesterday's date.</div></div>
        )}
      </div>
      {pings.length > 1 && (
        <div className="scrubber">
          <button className="btn btn-sm" onClick={() => { if (idx >= pings.length - 1) setIdx(0); setPlaying(!playing) }}>{playing ? 'Pause' : 'Play'}</button>
          <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="input" style={{ width: 80 }} aria-label="Replay speed">
            <option value={1}>1×</option><option value={5}>5×</option><option value={20}>20×</option>
          </select>
          <input type="range" min={0} max={pings.length - 1} value={idx} onChange={(e) => { setPlaying(false); setIdx(Number(e.target.value)) }} aria-label="Trip position" />
          <span className="muted small" style={{ minWidth: 130 }}>{cur && `${fmtTime(cur.ts)} · ${cur.speed_kmh} km/h`}</span>
        </div>
      )}
    </div>
  )
}
