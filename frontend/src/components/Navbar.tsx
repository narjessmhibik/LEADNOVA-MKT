import { useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Target, Globe, Megaphone,
  TrendingUp, Zap, BarChart2, Settings,
  LogOut, Search, ChevronRight, Sparkles
} from 'lucide-react'
import { useState } from 'react'
import NotificationBell from './NotificationBell'

const NAV_GROUPS = [
  {
    label: 'Principal',
    items: [
      { icon: LayoutDashboard, label: 'Dashboard',  href: '/dashboard' },
      { icon: Target,          label: 'Leads',       href: '/leads' },
      { icon: Globe,           label: 'Scraping',    href: '/scraping' },
    ],
  },
  {
    label: 'CRM & Ventes',
    items: [
      { icon: Megaphone,  label: 'Campagnes',   href: '/campaigns' },
      { icon: TrendingUp, label: 'Ventes',       href: '/ventes' },
      { icon: Zap,        label: 'Automation',   href: '/automation' },
    ],
  },
  {
    label: 'Analytics',
    items: [
      { icon: BarChart2, label: 'Rapports',    href: '/rapports' },
      { icon: Settings,  label: 'Paramètres',  href: '/parametres' },
    ],
  },
]

export default function Sidebar() {
  const location = useLocation()
  const [search, setSearch] = useState('')

  const handleLogout = () => {
    localStorage.clear()
    sessionStorage.clear()
    window.location.href = '/'
  }

  const avatar = localStorage.getItem('avatar') || sessionStorage.getItem('avatar')
  const prenom = localStorage.getItem('prenom') || sessionStorage.getItem('prenom') || ''
  const nom    = localStorage.getItem('nom')    || sessionStorage.getItem('nom')    || ''
  const email  = localStorage.getItem('email')  || sessionStorage.getItem('email')  || ''
  const displayName = prenom || nom ? `${prenom} ${nom}`.trim() : 'Utilisateur'
  const initials = `${prenom?.[0] || ''}${nom?.[0] || ''}` || 'U'

  const allItems = NAV_GROUPS.flatMap(g => g.items)
  const filtered = search
    ? allItems.filter(i => i.label.toLowerCase().includes(search.toLowerCase()))
    : null

  return (
    <>
    <NotificationBell />
    <aside className="flex h-screen w-56 flex-col fixed left-0 top-0 z-30"
      style={{ background: 'linear-gradient(180deg, #0f172a 0%, #1e1b4b 100%)' }}>

      {/* Logo */}
      <div className="px-5 pt-6 pb-5 border-b border-white/10">
        <div className="flex items-center justify-center">
          <h1 className="text-[22px] font-extrabold tracking-tight"
            style={{ background: 'linear-gradient(135deg, #fff 40%, #93c5fd)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            LeadPilot
          </h1>
        </div>
      </div>

      {/* Search */}
      <div className="px-3 py-3">
        <div className="flex items-center bg-white/8 border border-white/10 rounded-xl px-3 py-2 gap-2">
          <Search size={13} className="text-slate-400 flex-shrink-0" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Rechercher..."
            className="bg-transparent text-[12px] text-slate-300 outline-none w-full placeholder:text-slate-500"
          />
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 overflow-y-auto pb-3 space-y-5">
        {(filtered
          ? [{ label: 'Résultats', items: filtered }]
          : NAV_GROUPS
        ).map(group => (
          <div key={group.label}>
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest px-2 mb-2">
              {group.label}
            </p>
            {group.items.map(({ icon: Icon, label, href }) => {
              const active = location.pathname === href
              return (
                <a
                  key={href}
                  href={href}
                  className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl mb-0.5 text-[13px] font-medium transition-all group relative ${
                    active
                      ? 'text-white'
                      : 'text-slate-400 hover:text-white hover:bg-white/8'
                  }`}
                  style={active ? {
                    background: 'linear-gradient(135deg, rgba(59,130,246,.25), rgba(139,92,246,.15))',
                    border: '1px solid rgba(99,102,241,.3)',
                  } : {}}
                >
                  {active && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-blue-400 rounded-r-full" />
                  )}
                  <Icon size={16} className={active ? 'text-blue-400' : 'text-slate-500 group-hover:text-slate-300'} />
                  <span>{label}</span>
                  {active && <ChevronRight size={12} className="ml-auto text-blue-400 opacity-60" />}
                </a>
              )
            })}
          </div>
        ))}
      </nav>


      {/* User */}
      <div className="px-3 pb-4 border-t border-white/10 pt-3">
        <div className="flex items-center gap-3 px-2 py-2 rounded-xl hover:bg-white/8 transition-colors cursor-pointer group">
          <div className="w-8 h-8 rounded-full flex-shrink-0 overflow-hidden bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white text-xs font-bold">
            {avatar
              ? <img src={avatar} alt="" className="w-full h-full object-cover" />
              : <span>{initials}</span>
            }
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[12px] font-semibold text-white truncate">{displayName}</p>
            <p className="text-[10px] text-slate-500 truncate">{email}</p>
          </div>
          <button
            onClick={handleLogout}
            title="Déconnexion"
            className="text-slate-600 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
    </>
  )
}
