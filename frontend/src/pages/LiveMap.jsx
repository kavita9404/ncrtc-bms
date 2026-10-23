import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, Polygon, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { Link, useSearchParams } from 'react-router-dom'
import { api, fmtTime, label, todayISO } from '../api'
import { useAuth } from '../auth'
import { Pill, usePoll } from '../components/ui'

export const STATUS_COLOR = { on_time: '#2e9d5b', late: '#e69a1c', idle: '#8a8a8a' }
const NCR = [28.62, 77.33]
const POLL_MS = 5000

function FlyTo({ target }) {
  const map = useMap()
  useEffect(() => {
    if (target) map.flyTo(target, Math.max(map.getZoom(), 14), { duration: 0.8 })
  }, [target, map])
  return null
}

export default function LiveMap() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const [depots, setDepots] = useState([])
  const [depotId, setDepotId] = useState(user.role === 'depot_manager' ? String(user.depot_id) : '')
  const [selected, setSelected] = useState(params.get('vehicle') ? Number(params.get('vehicle')) : null)
  const [fly, setFly] = useState(null)

  useEffect(() => { api.get('/depots').then(setDepots) }, [])

  const [live, error] = usePoll(() => api.get('/avls/live', { depot_id: depotId || undefined }), POLL_MS, [depotId])
  const [trail] = usePoll(
    () => (selected ? api.get(`/avls/vehicles/${selected}/trail`, { minutes: 30 }) : Promise.resolve(null)),
    POLL_MS, [selected]
  )

  const vehicles = live?.vehicles || []
  const sel = vehicles.find((v) => v.vehicle_id === selected)

  // when arriving via ?vehicle=, centre once the data is in
  useEffect(() => {
    if (sel && params.get('vehicle')) {
      setFly([sel.lat, sel.lng])
      setParams({}, { replace: true })
    }
  }, [sel, params, setParams])

  const counts = vehicles.reduce((a, v) => ({ ...a, [v.status]: (a[v.status] || 0) + 1 }), {})
  const trailPts = (trail?.pings || []).map((p) => [p.lat, p.lng])

  return (
    <div className={`map-shell ${sel ? '' : 'no-panel'}`}>
      <div className="map-area">
        <MapContainer center={NCR} zoom={11} scrollWheelZoom>
          <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <FlyTo target={fly} />
          {depots.map((d) => d.polygon && (
            <Polygon key={d.id} positions={d.polygon.coordinates[0].map(([lng, lat]) => [lat, lng])}
              pathOptions={{ color: '#d84e55', weight: 1, fillOpacity: 0.12 }}>
              <Tooltip sticky>{d.name} depot</Tooltip>
            </Polygon>
          ))}
          {trailPts.length > 1 && <Polyline positions={trailPts} pathOptions={{ color: '#d84e55', weight: 4, opacity: 0.8 }} />}
          {vehicles.map((v) => (
            <CircleMarker key={v.vehicle_id} center={[v.lat, v.lng]} radius={v.vehicle_id === selected ? 10 : 7}
              pathOptions={{ color: '#fff', weight: 2, fillColor: STATUS_COLOR[v.status], fillOpacity: 1 }}
              eventHandlers={{ click: () => setSelected(v.vehicle_id) }}>
              <Tooltip direction="top" offset={[0, -6]}>
                <b>{v.reg_no}</b><br />{v.speed_kmh} km/h{v.geofence_breach ? ' · outside depot!' : ''}
              </Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>

        <div className="map-toolbar">
          {user.role !== 'depot_manager' && (
            <select value={depotId} onChange={(e) => { setDepotId(e.target.value); setSelected(null) }} aria-label="Filter by depot">
              <option value="">All depots</option>
              {depots.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          )}
          <span className="legend">
            {Object.entries({ on_time: 'On time', late: 'Late / slow', idle: 'Idle' }).map(([k, t]) => (
              <span key={k}><i className="dot" style={{ background: STATUS_COLOR[k] }} />{t} ({counts[k] || 0})</span>
            ))}
          </span>
          <span className="muted small">Updated {live ? fmtTime(live.as_of) : '…'} · every {POLL_MS / 1000}s</span>
        </div>
        {error && <div className="alerts"><div className="error">{error}</div></div>}
        {live?.alerts?.length > 0 && (
          <div className="alerts" style={{ top: 64 }}>
            {live.alerts.map((a) => (
              <div className="banner-warn" key={a.vehicle_id}>
                <strong>Geofence breach:</strong> {a.message}{' '}
                <button className="linkbtn" onClick={() => { setSelected(a.vehicle_id); const v = vehicles.find((x) => x.vehicle_id === a.vehicle_id); v && setFly([v.lat, v.lng]) }}>Show</button>
              </div>
            ))}
          </div>
        )}
      </div>

      {sel && (
        <aside className="side-panel">
          <div className="row">
            <h2 style={{ margin: 0 }}>{sel.reg_no}</h2>
            <Pill kind={sel.status}>{label(sel.status)}</Pill>
            <span className="spacer" />
            <button className="btn btn-plain btn-sm" onClick={() => setSelected(null)}>Close</button>
          </div>
          <dl className="kv">
            <dt>Speed</dt><dd>{sel.speed_kmh} km/h {sel.ignition_on ? '' : '(ignition off)'}</dd>
            <dt>Depot</dt><dd>{sel.depot_code}</dd>
            <dt>Driver</dt><dd>{sel.driver ? <>{sel.driver.name}<br /><span className="muted small">{sel.driver.phone}</span></> : 'No duty today'}</dd>
            <dt>Route</dt><dd>{sel.route ? `${sel.route.code} · ${sel.route.name}` : '—'}</dd>
            <dt>Last ping</dt><dd>{fmtTime(sel.ts)}</dd>
            <dt>Trail</dt><dd>{trailPts.length} pings, last 30 min</dd>
          </dl>
          {sel.geofence_breach && <div className="banner-warn">This bus is outside its depot with no duty today.</div>}
          <Link className="btn btn-outline" to={`/history?vehicle=${sel.vehicle_id}&day=${todayISO()}`}>View today's path</Link>
        </aside>
      )}
    </div>
  )
}
