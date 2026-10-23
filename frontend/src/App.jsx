import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { CREW, homeFor, useAuth } from './auth'
import Navbar from './components/Navbar'
import Login from './pages/Login'
import Home from './pages/Home'
import LiveMap from './pages/LiveMap'
import History from './pages/History'
import Roster from './pages/Roster'
import RoutesAdmin from './pages/RoutesAdmin'
import Incidents from './pages/Incidents'
import IncidentDetail from './pages/IncidentDetail'
import Notices from './pages/Notices'
import Reports from './pages/Reports'
import DriverApp from './pages/DriverApp'

/** Gate: must be logged in, and (optionally) hold one of `roles`. */
function Guard({ roles }) {
  const { user, ready } = useAuth()
  if (!ready) return <p className="page muted">Loading…</p>
  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />
  return <Outlet />
}

function Shell() {
  return (
    <>
      <Navbar />
      <Outlet />
    </>
  )
}

const OPS = ['admin', 'control_operator', 'depot_manager']
const VIEW = [...OPS, 'executive']

export default function App() {
  const { user } = useAuth()
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={homeFor(user.role)} replace /> : <Login />} />

      <Route element={<Guard roles={CREW} />}>
        <Route path="/driver" element={<DriverApp />} />
      </Route>

      <Route element={<Guard roles={VIEW} />}>
        <Route element={<Shell />}>
          <Route path="/" element={<Home />} />
          <Route path="/live" element={<LiveMap />} />
          <Route path="/history" element={<History />} />
          <Route path="/incidents" element={<Incidents />} />
          <Route path="/incidents/:id" element={<IncidentDetail />} />
          <Route path="/notices" element={<Notices />} />
          <Route path="/reports" element={<Reports />} />
        </Route>
      </Route>

      <Route element={<Guard roles={['admin', 'depot_manager']} />}>
        <Route element={<Shell />}>
          <Route path="/roster" element={<Roster />} />
        </Route>
      </Route>
      <Route element={<Guard roles={['admin']} />}>
        <Route element={<Shell />}>
          <Route path="/routes" element={<RoutesAdmin />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to={user ? homeFor(user.role) : '/login'} replace />} />
    </Routes>
  )
}
