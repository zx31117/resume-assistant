import { Link, NavLink, Outlet } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: '生成工作台', end: true },
  { to: '/profile', label: '履历库' },
  { to: '/system', label: '本地系统' },
]

export default function AppShell() {
  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar__inner">
          <Link to="/" className="brand">
            <span className="brand__mark">Resume</span>
            <span className="brand__dot">.</span>
            <span className="brand__sub">AI 简历助手</span>
          </Link>
          <nav className="nav" aria-label="主导航">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  'nav__link' + (isActive ? ' is-active' : '')
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="shell__main">
        <Outlet />
      </main>
    </div>
  )
}