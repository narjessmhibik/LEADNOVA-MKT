import { useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Users, Globe, Megaphone,
  Workflow, BarChart3, Settings, LogOut, Search, Sparkles,
  ChevronLeft, ChevronRight,
} from 'lucide-react'
import { useState, useEffect } from 'react'
import NotificationBell from './NotificationBell'

const NAV_GROUPS = [
  {
    label: 'Pilotage',
    items: [
      { icon: LayoutDashboard, label: 'Dashboard',  href: '/dashboard' },
      { icon: Users,           label: 'Prospects',  href: '/leads' },
      { icon: Globe,           label: 'Scraping',   href: '/scraping' },
    ],
  },
  {
    label: 'Marketing',
    items: [
      { icon: Megaphone, label: 'Campagnes',  href: '/campaigns' },
      { icon: Workflow,  label: 'Automation', href: '/automation' },
    ],
  },
  {
    label: 'Analyse',
    items: [
      { icon: BarChart3, label: 'Analytics', href: '/rapports' },
      { icon: Settings,  label: 'Réglages',  href: '/parametres' },
    ],
  },
]

const SIDEBAR_EXPANDED = '15rem'
const SIDEBAR_COLLAPSED = '3.5rem'

export default function Sidebar() {
  const location = useLocation()
  const [search, setSearch] = useState('')
  const [searchFocused, setSearchFocused] = useState(false)
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem('sidebar-collapsed') === '1'
  )

  // Sync CSS variable whenever collapsed state changes (and on first mount)
  useEffect(() => {
    document.documentElement.style.setProperty(
      '--sidebar-w',
      collapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED
    )
  }, [collapsed])

  const toggle = () => {
    const next = !collapsed
    setCollapsed(next)
    localStorage.setItem('sidebar-collapsed', next ? '1' : '0')
  }

  const handleLogout = () => {
    localStorage.clear()
    sessionStorage.clear()
    window.location.href = '/'
  }

  const avatar      = localStorage.getItem('avatar')  || sessionStorage.getItem('avatar')
  const prenom      = localStorage.getItem('prenom')  || sessionStorage.getItem('prenom') || ''
  const nom         = localStorage.getItem('nom')     || sessionStorage.getItem('nom')    || ''
  const email       = localStorage.getItem('email')   || sessionStorage.getItem('email')  || ''
  const displayName = prenom || nom ? `${prenom} ${nom}`.trim() : 'Utilisateur'
  const initials    = `${prenom?.[0] || ''}${nom?.[0] || ''}`.trim() || 'U'

  const allItems = NAV_GROUPS.flatMap(g => g.items)
  const filtered = !collapsed && search
    ? allItems.filter(i => i.label.toLowerCase().includes(search.toLowerCase()))
    : null

  return (
    <>
    <aside
      className={`flex h-screen flex-col fixed left-0 top-0 z-30 bg-white border-r border-[var(--border)] transition-[width] duration-200 overflow-hidden ${
        collapsed ? 'w-14' : 'w-60'
      }`}
    >
      {/* Logo */}
      <div className={`flex items-center border-b border-[var(--border)] ${collapsed ? 'justify-center py-4 px-2' : 'justify-between px-5 pt-6 pb-4'}`}>
        {collapsed ? (
          <a href="/dashboard" className="nova-mark w-9 h-9 rounded-[13px] flex items-center justify-center flex-shrink-0">
            <Sparkles size={17} className="text-white" />
          </a>
        ) : (
          <a href="/dashboard" className="flex items-center gap-2.5">
            <div className="nova-mark w-9 h-9 rounded-[13px] flex items-center justify-center flex-shrink-0">
              <Sparkles size={17} className="text-white" />
            </div>
            <div className="leading-none">
              <h1 className="text-[19px] font-extrabold tracking-tight font-display text-[var(--ink)]">
                Lead<span className="nova-text">nova</span>
              </h1>
              <p className="text-[9px] font-semibold text-[var(--ink-muted)] tracking-[0.18em] uppercase mt-0.5">
                AI Sales Engine
              </p>
            </div>
          </a>
        )}
        {!collapsed && <NotificationBell />}
      </div>

      {/* Search — masquée quand réduit */}
      {!collapsed && (
        <div className="px-3 pb-3 pt-3">
          <div className="flex items-center bg-[var(--surface-3)] border border-transparent focus-within:border-[var(--nova-300)] focus-within:bg-white rounded-xl px-3 py-2 gap-2 transition-colors">
            <Search size={14} className="text-[var(--ink-faint)] flex-shrink-0" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Rechercher…"
              type="search"
              name="leadpilot-nav-search"
              autoComplete="off"
              readOnly={!searchFocused}
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setSearchFocused(false)}
              className="bg-transparent text-[12.5px] text-[var(--ink)] outline-none w-full placeholder:text-[var(--ink-faint)]"
            />
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className={`flex-1 overflow-y-auto pb-3 ${collapsed ? 'px-2 pt-3 space-y-1' : 'px-3 space-y-5'}`}>
        {collapsed ? (
          /* Mode réduit : icônes uniquement avec tooltip */
          NAV_GROUPS.flatMap(g => g.items).map(({ icon: Icon, label, href }) => {
            const active = location.pathname === href
            return (
              <a
                key={href}
                href={href}
                title={label}
                className={`flex items-center justify-center w-10 h-10 rounded-xl mx-auto mb-0.5 transition-all relative ${
                  active
                    ? 'text-[var(--nova-700)] bg-[var(--nova-50)]'
                    : 'text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-3)]'
                }`}
              >
                {active && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 rounded-r-full"
                    style={{ background: 'var(--nova-grad-2)' }} />
                )}
                <Icon size={17} className={active ? 'text-[var(--nova-500)]' : ''} />
              </a>
            )
          })
        ) : (
          /* Mode étendu : groupes avec labels */
          (filtered
            ? [{ label: 'Résultats', items: filtered }]
            : NAV_GROUPS
          ).map(group => (
            <div key={group.label}>
              <p className="text-[10px] font-bold text-[var(--ink-faint)] uppercase tracking-[0.14em] px-3 mb-1.5">
                {group.label}
              </p>
              {group.items.map(({ icon: Icon, label, href }) => {
                const active = location.pathname === href
                return (
                  <a
                    key={href}
                    href={href}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-xl mb-0.5 text-[13.5px] font-semibold transition-all group relative ${
                      active
                        ? 'text-[var(--nova-700)] bg-[var(--nova-50)]'
                        : 'text-[var(--ink-soft)] hover:text-[var(--ink)] hover:bg-[var(--surface-3)]'
                    }`}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 rounded-r-full"
                        style={{ background: 'var(--nova-grad-2)' }} />
                    )}
                    <Icon size={17} className={active ? 'text-[var(--nova-500)]' : 'text-[var(--ink-muted)] group-hover:text-[var(--ink-soft)]'} />
                    <span>{label}</span>
                  </a>
                )
              })}
            </div>
          ))
        )}
      </nav>

      {/* User */}
      <div className={`pb-4 pt-3 border-t border-[var(--border)] ${collapsed ? 'px-2' : 'px-3'}`}>
        {collapsed ? (
          <div className="flex flex-col items-center gap-2">
            <div className="w-9 h-9 rounded-full flex-shrink-0 overflow-hidden flex items-center justify-center text-white text-xs font-bold nova-mark">
              {avatar
                ? <img src={avatar} alt="" className="w-full h-full object-cover" />
                : <span>{initials}</span>
              }
            </div>
            <button
              onClick={handleLogout}
              title="Déconnexion"
              className="text-[var(--ink-faint)] hover:text-[var(--danger)] transition-colors"
            >
              <LogOut size={14} />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-3 px-2 py-2 rounded-xl hover:bg-[var(--surface-3)] transition-colors cursor-pointer group">
            <div className="w-9 h-9 rounded-full flex-shrink-0 overflow-hidden flex items-center justify-center text-white text-xs font-bold nova-mark">
              {avatar
                ? <img src={avatar} alt="" className="w-full h-full object-cover" />
                : <span>{initials}</span>
              }
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[12.5px] font-bold text-[var(--ink)] truncate">{displayName}</p>
              <p className="text-[10.5px] text-[var(--ink-muted)] truncate">{email}</p>
            </div>
            <button
              onClick={handleLogout}
              title="Déconnexion"
              className="text-[var(--ink-faint)] hover:text-[var(--danger)] transition-colors opacity-0 group-hover:opacity-100"
            >
              <LogOut size={15} />
            </button>
          </div>
        )}
      </div>
    </aside>

    {/* Toggle button — fixed outside aside so it's never clipped by overflow-hidden */}
    <button
      onClick={toggle}
      title={collapsed ? 'Ouvrir le menu' : 'Réduire le menu'}
      style={{
        left: collapsed ? '3.5rem' : '15rem',
        transform: 'translateX(-50%)',
        transition: 'left 200ms',
      }}
      className="fixed top-[52px] z-50 w-6 h-6 bg-white border border-[var(--border)] rounded-full flex items-center justify-center shadow-sm hover:bg-[var(--nova-50)] hover:border-[var(--nova-300)]"
    >
      {collapsed
        ? <ChevronRight size={12} className="text-gray-500" />
        : <ChevronLeft  size={12} className="text-gray-500" />
      }
    </button>
    </>
  )
}
