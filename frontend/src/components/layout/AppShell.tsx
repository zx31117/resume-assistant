import { NavLink, Outlet } from 'react-router-dom'

function IconDoc() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M8 13h8M8 17h6" />
    </svg>
  )
}

function IconList() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 9h18" />
      <path d="M8 14h8M8 17h5" />
    </svg>
  )
}

function IconShield() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <path d="M12 2 4 5v6c0 5 3.5 9.4 8 11 4.5-1.6 8-6 8-11V5z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  )
}

const NAV_ITEMS = [
  { to: '/', label: '生成简历', end: true, icon: <IconDoc /> },
  { to: '/profile', label: '我的经历', end: false, icon: <IconList /> },
  { to: '/privacy', label: '个人与隐私', end: false, icon: <IconShield /> },
]

export default function AppShell() {
  return (
    <div className="shell">
      <aside className="app-sidebar" aria-label="主导航">
        <div className="app-brand">
          <div className="logo" aria-hidden="true">
            简
          </div>
          <div className="app-brand__text">
            <div className="name">简历助手</div>
            <div className="sub">本地预览版</div>
          </div>
        </div>
        <nav className="app-nav" aria-label="主要页面">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => 'nav-item' + (isActive ? ' is-active' : '')}
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="app-sidebar__foot">
          <NavLink
            to="/system"
            className="dev-link"
            aria-label="开发者后台（隐藏入口）"
          >
            开发者后台 ›
          </NavLink>
        </div>
      </aside>
      <main id="main" className="app-main">
        <Outlet />
      </main>
    </div>
  )
}
