import React, { useState } from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, Upload, Film, Menu, X, Flame, Shield } from 'lucide-react'
import styles from './Layout.module.css'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Дашборд', exact: true },
  { to: '/upload', icon: Upload, label: 'Загрузка видео' },
  { to: '/videos', icon: Film, label: 'Архив видео' },
]

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()

  return (
    <div className={styles.root}>
      {/* Sidebar */}
      <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`}>
        <div className={styles.sidebarTop}>
          <div className={styles.logo}>
            <Flame size={22} className={styles.logoIcon} />
            {!collapsed && (
              <span className={styles.logoText}>
                FIRE<span>WATCH</span>
              </span>
            )}
          </div>
          <button className={styles.collapseBtn} onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? <Menu size={16} /> : <X size={16} />}
          </button>
        </div>

        <div className={styles.sidebarDivider} />

        <nav className={styles.nav}>
          {NAV.map(({ to, icon: Icon, label, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) =>
                `${styles.navItem} ${isActive ? styles.navActive : ''}`
              }
            >
              <Icon size={18} className={styles.navIcon} />
              {!collapsed && <span className={styles.navLabel}>{label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className={styles.sidebarBottom}>
          <div className={styles.statusIndicator}>
            <span className={styles.statusDot} />
            {!collapsed && (
              <span className={styles.statusText}>СИСТЕМА АКТИВНА</span>
            )}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className={styles.main}>
        {/* Top bar */}
        <header className={styles.topbar}>
          <div className={styles.topbarLeft}>
            <Shield size={14} className={styles.topbarIcon} />
            <span className={styles.topbarPath}>
              {location.pathname === '/' ? 'ДАШБОРД' :
               location.pathname.startsWith('/videos/') ? 'АНАЛИЗ ВИДЕО' :
               location.pathname === '/upload' ? 'ЗАГРУЗКА' :
               location.pathname === '/videos' ? 'АРХИВ' : ''}
            </span>
          </div>
          <div className={styles.topbarRight}>
            <span className={styles.topbarTime} id="clock">
              {new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          </div>
        </header>

        <main className={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
