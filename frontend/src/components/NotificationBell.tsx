import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import {
  Bell, Sparkles, Megaphone, AlertTriangle, FileBarChart, Check, Trash2, X
} from 'lucide-react'

const API = axios.create({ baseURL: (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000') })
API.interceptors.request.use(c => {
  const t = localStorage.getItem('token')
  if (t) c.headers.Authorization = `Bearer ${t}`
  return c
})

const TYPE_META: Record<string, { icon: any; color: string; bg: string }> = {
  lead:   { icon: Sparkles,      color: 'text-indigo-500',  bg: 'bg-indigo-50'  },
  camp:   { icon: Megaphone,     color: 'text-sky-500',     bg: 'bg-sky-50'     },
  risk:   { icon: AlertTriangle, color: 'text-rose-500',    bg: 'bg-rose-50'    },
  report: { icon: FileBarChart,  color: 'text-emerald-500', bg: 'bg-emerald-50' },
  info:   { icon: Bell,          color: 'text-gray-500',    bg: 'bg-gray-50'    },
}

function timeAgo(iso: string) {
  const d = new Date(iso).getTime()
  const diff = Math.floor((Date.now() - d) / 1000)
  if (diff < 60)    return "à l'instant"
  if (diff < 3600)  return `il y a ${Math.floor(diff / 60)} min`
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`
  return `il y a ${Math.floor(diff / 86400)} j`
}

function getPrefs(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem('notif_prefs')
    return raw ? JSON.parse(raw) : { lead: true, camp: true, risk: true, report: true }
  } catch { return { lead: true, camp: true, risk: true, report: true } }
}

export default function NotificationBell() {
  const [open, setOpen]   = useState(false)
  const [items, setItems] = useState<any[]>([])
  const [unread, setUnread] = useState(0)
  const ref = useRef<HTMLDivElement>(null)

  const fetchNotifs = async () => {
    try {
      const prefs = getPrefs()
      const res = await API.get('/notifications/', { params: { limit: 30 } })
      // Filtrer selon les préférences activées dans Paramètres
      const filtered = (res.data.items || []).filter((n: any) => prefs[n.type] !== false)
      setItems(filtered)
      setUnread(filtered.filter((n: any) => !n.is_read).length)
    } catch { /* backend indisponible */ }
  }

  // Polling toutes les 20 s
  useEffect(() => {
    fetchNotifs()
    const id = setInterval(fetchNotifs, 20000)
    return () => clearInterval(id)
  }, [])

  // Fermer au clic extérieur
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const markAllRead = async () => {
    await API.post('/notifications/read-all').catch(() => {})
    setItems(items.map(n => ({ ...n, is_read: true })))
    setUnread(0)
  }

  const clearAll = async () => {
    await API.delete('/notifications/').catch(() => {})
    setItems([]); setUnread(0)
  }

  const onItemClick = async (n: any) => {
    if (!n.is_read) {
      await API.post(`/notifications/${n.id}/read`).catch(() => {})
      setItems(items.map(x => x.id === n.id ? { ...x, is_read: true } : x))
      setUnread(u => Math.max(0, u - 1))
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="relative w-9 h-9 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
      >
        <Bell size={16} className="text-slate-200" />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[17px] h-[17px] px-1 bg-rose-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="fixed top-16 left-4 w-80 bg-white rounded-2xl shadow-2xl border border-gray-100 overflow-hidden animate-fade-in z-[60]">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-gray-900 text-sm">Notifications</h3>
              {unread > 0 && (
                <span className="text-[10px] font-bold bg-rose-50 text-rose-600 px-2 py-0.5 rounded-full">{unread} non lues</span>
              )}
            </div>
            <div className="flex items-center gap-1">
              {items.length > 0 && (
                <>
                  <button onClick={markAllRead} title="Tout marquer comme lu"
                    className="p-1.5 rounded-lg text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors">
                    <Check size={14} />
                  </button>
                  <button onClick={clearAll} title="Tout effacer"
                    className="p-1.5 rounded-lg text-gray-400 hover:text-rose-500 hover:bg-rose-50 transition-colors">
                    <Trash2 size={14} />
                  </button>
                </>
              )}
              <button onClick={() => setOpen(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100 transition-colors">
                <X size={14} />
              </button>
            </div>
          </div>

          {/* Liste */}
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-gray-300">
                <Bell size={28} className="mb-2 opacity-40" />
                <p className="text-sm font-medium text-gray-400">Aucune notification</p>
              </div>
            ) : (
              items.map(n => {
                const meta = TYPE_META[n.type] || TYPE_META.info
                const Icon = meta.icon
                return (
                  <div key={n.id} onClick={() => onItemClick(n)}
                    className={`flex gap-3 px-4 py-3 border-b border-gray-50 cursor-pointer transition-colors ${
                      n.is_read ? 'hover:bg-gray-50' : 'bg-indigo-50/40 hover:bg-indigo-50/70'
                    }`}>
                    <div className={`w-9 h-9 rounded-xl flex-shrink-0 flex items-center justify-center ${meta.bg}`}>
                      <Icon size={16} className={meta.color} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="font-semibold text-[13px] text-gray-900 truncate">{n.title}</p>
                        {!n.is_read && <span className="w-2 h-2 rounded-full bg-indigo-500 flex-shrink-0" />}
                      </div>
                      {n.message && <p className="text-[12px] text-gray-500 mt-0.5 leading-snug">{n.message}</p>}
                      <p className="text-[10px] text-gray-400 mt-1">{n.created_at ? timeAgo(n.created_at) : ''}</p>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
