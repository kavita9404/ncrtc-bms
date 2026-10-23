import { useState } from 'react'
import { api, addDays, todayISO } from '../api'
import { ErrorBox, Field, Spinner, usePoll } from '../components/ui'

const COLS = [
  ['duties', 'Duties'], ['acknowledged', 'Acknowledged'], ['distance_km', 'Distance (km)'],
  ['incidents_raised', 'Incidents'], ['p1', 'P1'], ['incidents_resolved', 'Resolved'], ['sla_breaches', 'SLA breaches'],
]

export default function Reports() {
  const [day, setDay] = useState(addDays(todayISO(), -1))
  const [rep, error] = usePoll(() => api.get('/reports/daily', { day }), 0, [day])

  return (
    <div className="page">
      <div className="page-title">
        <h1>Daily operations report</h1>
        <div className="row no-print">
          <Field label="Date"><input className="input" type="date" value={day} max={todayISO()} onChange={(e) => setDay(e.target.value)} /></Field>
          <button className="btn" onClick={() => window.print()}>Download PDF</button>
        </div>
      </div>
      <ErrorBox message={error} />
      {!rep ? <Spinner /> : (
        <>
          <div className="tiles">
            <div className="tile"><b>{rep.total.duties}</b><span>Duties run</span></div>
            <div className="tile"><b>{Math.round(rep.total.distance_km)}</b><span>Km travelled (tracked buses)</span></div>
            <div className="tile alert"><b>{rep.total.incidents_raised}</b><span>Incidents raised ({rep.total.p1} P1)</span></div>
            <div className="tile alert"><b>{rep.total.sla_breaches}</b><span>SLA breaches</span></div>
          </div>
          <div className="tbl-wrap">
            <table className="tbl">
              <thead><tr><th>Depot</th>{COLS.map(([, t]) => <th key={t}>{t}</th>)}</tr></thead>
              <tbody>
                {rep.depots.map((d) => (
                  <tr key={d.depot_code}><td><b>{d.depot_name}</b></td>{COLS.map(([k]) => <td key={k}>{d[k]}</td>)}</tr>
                ))}
                <tr style={{ fontWeight: 800 }}><td>Total</td>{COLS.map(([k]) => <td key={k}>{Math.round(rep.total[k] * 10) / 10}</td>)}</tr>
              </tbody>
            </table>
          </div>
          <p className="muted small">
            Distance is measured only for the buses that have GPS data for that day. Report for {rep.date}.
          </p>
        </>
      )}
    </div>
  )
}
