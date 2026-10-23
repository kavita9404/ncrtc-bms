import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { label } from '../api'

const LINKS = [
  { to: '/', text: 'Search', roles: ['admin', 'control_operator', 'depot_manager'], end: true },
  { to: '/live', text: 'Live map', roles: ['admin', 'control_operator', 'depot_manager', 'executive'] },
  { to: '/history', text: 'Trip history', roles: ['admin', 'control_operator', 'depot_manager', 'executive'] },
  { to: '/roster', text: 'Roster', roles: ['admin', 'depot_manager'] },
  { to: '/routes', text: 'Routes', roles: ['admin'] },
  { to: '/incidents', text: 'Incidents', roles: ['admin', 'control_operator', 'depot_manager', 'executive'] },
  { to: '/notices', text: 'Notices', roles: ['admin', 'control_operator', 'depot_manager', 'executive'] },
  { to: '/reports', text: 'Reports', roles: ['admin', 'control_operator', 'executive'] },
]

export function Logo() {
  return (
    <svg className="brand-logo" viewBox="0 0 512 512" aria-hidden="true">
      <rect width="512" height="512" rx="110" fill="#fff" />
      <rect x="96" y="120" width="320" height="230" rx="40" fill="#d84e55" />
      <rect x="128" y="154" width="256" height="90" rx="16" fill="#fff" />
      <circle cx="170" cy="392" r="34" fill="#d84e55" />
      <circle cx="342" cy="392" r="34" fill="#d84e55" />
    </svg>
  )
}

export default function Navbar() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  return (
    <header className="nav no-print">
      <NavLink to="/" className="brand">
        <Logo /> NCRTC Bus
      </NavLink>
      <nav className="nav-links">
        {LINKS.filter((l) => l.roles.includes(user.role)).map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end}>
            {l.text}
          </NavLink>
        ))}
      </nav>
      <div className="who">
        <span>
          {user.full_name}
          <small>{label(user.role)}</small>
        </span>
        <button className="btn-ghost-light" onClick={() => { logout(); nav('/login') }}>
          Log out
        </button>
      </div>
    </header>
  )
}
