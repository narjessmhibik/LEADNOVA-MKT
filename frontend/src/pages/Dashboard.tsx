import { useEffect, useState, useRef } from 'react'
import Sidebar from '../components/Navbar'
import { getLeadStats } from '../services/api'
import API from '../services/api'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line, Area, AreaChart,
} from 'recharts'
import {
  Users, Mail, Phone, Sparkles, ArrowUpRight,
  ArrowDownRight, RefreshCw, Activity,
  AlertTriangle, Clock, Zap, TrendingDown, CheckCircle,
} from 'lucide-react'

//  Types
interface Stats {
  total: number; with_email: number; with_phone: number; with_website: number
  email_rate: number; avg_score: number; enriched: number; stale_leads: number
  segments: { Chaud: number; 'Prêts à Acheter': number; Froid: number; 'A Risque': number }
  sectors: { sector: string; count: number }[]
  sources:  { source: string; count: number }[]
  enrichment_coverage: { field: string; count: number; rate: number }[]
  leads_per_week: { week: string; count: number }[]
  scraped_today: number; scraped_week: number; scraped_month: number
  sources_conversion: { source: string; total: number; contacted: number; opened: number; contact_rate: number; open_rate: number }[]
  status_distribution: { status: string; count: number }[]
}
interface Feature { feature: string; importance: number }

//  Design constants
const SEG_CONFIG = {
  Chaud:            { color: '#e11d48', bg: '#fff1f2', label: 'Chaud'           },
  'Prêts à Acheter':{ color: '#ea580c', bg: '#fff7ed', label: 'Prêts à Acheter' },
  Froid:            { color: '#6366f1', bg: '#eef2ff', label: 'Froid'           },
  'A Risque':       { color: '#d97706', bg: '#fffbeb', label: 'À Risque'        },
}
const CHART_COLORS = ['#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#e11d48', '#7c3aed', '#f97316', '#64748b']

//  Animated counter
function useCountUp(target: number, duration = 900) {
  const [val, setVal] = useState(0)
  const raf = useRef<number>()
  useEffect(() => {
    if (!target) return
    const start = performance.now()
    const animate = (now: number) => {
      const p = Math.min((now - start) / duration, 1)
      const ease = 1 - Math.pow(1 - p, 3)
      setVal(Math.round(ease * target))
      if (p < 1) raf.current = requestAnimationFrame(animate)
    }
    raf.current = requestAnimationFrame(animate)
    return () => { if (raf.current) cancelAnimationFrame(raf.current) }
  }, [target, duration])
  return val
}

//  KPI Card
function KpiCard({ label, rawValue, suffix = '', sub, icon: Icon, color, trend }: {
  label: string; rawValue: number; suffix?: string; sub?: string
  icon: any; color: string; trend?: { val: number; positive: boolean }
}) {
  const animated = useCountUp(rawValue)
  return (
    <div className="card card-hover p-5 animate-fade-up">
      <div className="flex items-start justify-between mb-4">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
          <Icon size={18} className="opacity-80" />
        </div>
        {trend && (
          <div className={`flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full ${
            trend.positive ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-500'
          }`}>
            {trend.positive ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}
            {trend.val}%
          </div>
        )}
      </div>
      <p className="text-2xl font-extrabold text-gray-900 kpi-number tabular-nums">
        {animated.toLocaleString('fr')}{suffix}
      </p>
      <p className="text-[13px] font-medium text-gray-500 mt-0.5">{label}</p>
      {sub && <p className="text-[11px] text-gray-400 mt-1">{sub}</p>}
    </div>
  )
}

//  Chart card wrapper
function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="card p-6 animate-fade-up">
      <h3 className="font-bold text-gray-900 text-[15px]">{title}</h3>
      {subtitle && <p className="text-[12px] text-gray-400 mt-0.5 mb-5">{subtitle}</p>}
      {!subtitle && <div className="mb-5" />}
      {children}
    </div>
  )
}

//  Custom Tooltip
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-100 shadow-lg rounded-xl px-4 py-3">
      {label && <p className="text-xs text-gray-500 mb-1 font-medium">{label}</p>}
      {payload.map((p: any, i: number) => (
        <p key={i} className="text-sm font-bold" style={{ color: p.color || p.fill || '#1f2937' }}>
          {p.value?.toLocaleString('fr')} {p.name && <span className="font-normal text-gray-500">{p.name}</span>}
        </p>
      ))}
    </div>
  )
}

//  Skeleton
function DashboardSkeleton() {
  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />
      <div className="ml-56 flex-1 overflow-auto p-8">
        <div className="skeleton h-8 w-64 mb-2" />
        <div className="skeleton h-4 w-48 mb-8" />
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-6 stagger">
          {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-32 animate-fade-up" />)}
        </div>
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-6 stagger">
          {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-24 animate-fade-up" />)}
        </div>
        <div className="grid xl:grid-cols-2 gap-6">
          <div className="skeleton h-72 animate-fade-up" />
          <div className="skeleton h-72 animate-fade-up" />
        </div>
      </div>
    </div>
  )
}

//  Main
export default function Dashboard() {
  const [stats, setStats]     = useState<Stats | null>(null)

  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(new Date())

  const fetchData = () => {
    setLoading(true)
    Promise.all([getLeadStats()])
      .then(([s]) => { setStats(s.data); setLastUpdate(new Date()) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchData() }, [])

  if (loading) return <DashboardSkeleton />

  const total = stats?.total ?? 0
  const segData = stats ? Object.entries(stats.segments).map(([name, value]) => ({ name, value })) : []
  const enrichedPct = stats ? Math.round((stats.enriched / total) * 100) : 0

  //  Funnel data
  const statusMap = Object.fromEntries(
    (stats?.status_distribution ?? []).map(s => [s.status, s.count])
  )
  const contacted = (statusMap['contacté'] ?? 0) + (statusMap['qualifié'] ?? 0) + (statusMap['converti'] ?? 0)
  const qualified  = (statusMap['qualifié'] ?? 0) + (statusMap['converti'] ?? 0)
  const converted  = statusMap['converti'] ?? 0
  const funnelSteps = [
    { label: 'Leads Scrapés', sublabel: 'Total collecté', value: total, color: '#6366f1', pct: 100 },
    { label: 'Contactés (MQL)', sublabel: 'Email envoyé', value: contacted, color: '#7c3aed', pct: total ? Math.round(contacted / total * 100) : 0 },
    { label: 'Qualifiés (SQL)', sublabel: 'Statut qualifié', value: qualified, color: '#f59e0b', pct: total ? Math.round(qualified / total * 100) : 0 },
    { label: 'Clients', sublabel: 'Convertis', value: converted, color: '#10b981', pct: total ? Math.round(converted / total * 100) : 0 },
  ]

  //  Alertes IA
  const alerts: { type: 'warning' | 'info' | 'success'; msg: string; Icon: any }[] = []
  const aRisque = stats?.segments?.['A Risque'] ?? 0
  const chauds  = stats?.segments?.Chaud ?? 0
  if (aRisque > 300)
    alerts.push({ type: 'warning', msg: `${aRisque.toLocaleString('fr')} leads "À Risque" détectés — lancez une campagne de réactivation`, Icon: AlertTriangle })
  if ((stats?.stale_leads ?? 0) > 200)
    alerts.push({ type: 'info', msg: `${(stats?.stale_leads ?? 0).toLocaleString('fr')} leads sans mise à jour depuis 6 mois — re-scraping recommandé`, Icon: Clock })
  if (chauds > 100 && contacted < chauds)
    alerts.push({ type: 'success', msg: `${chauds.toLocaleString('fr')} leads "Chauds" prêts à être contactés — opportunité commerciale immédiate`, Icon: Zap })

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />

      <div className="ml-56 flex-1 overflow-auto min-w-0">

        {/* Header */}
        <header className="sticky top-0 z-20 bg-white/80 backdrop-blur-md border-b border-gray-100 px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-gray-900">Vue d'ensemble</h1>
              <p className="text-[12px] text-gray-400 mt-0.5">
                Mis à jour {lastUpdate.toLocaleTimeString('fr', { hour: '2-digit', minute: '2-digit' })}
                {stats?.stale_leads ? (
                  <span className="ml-3 text-amber-500 font-semibold">
                    · {stats.stale_leads.toLocaleString()} leads à rafraîchir
                  </span>
                ) : null}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 bg-green-50 border border-green-200 text-green-700 text-xs font-semibold px-3 py-1.5 rounded-full">
                <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                Système actif
              </div>
              <button
                onClick={fetchData}
                className="btn btn-secondary text-xs"
                title="Rafraîchir"
              >
                <RefreshCw size={13} />
                Rafraîchir
              </button>
            </div>
          </div>
        </header>

        <div className="p-8 space-y-6">

          {/* KPI row */}
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 stagger">
            <KpiCard
              label="Leads Totaux"
              rawValue={total}
              sub={`${enrichedPct}% enrichis`}
              icon={Users}
              color="bg-blue-50 text-blue-600"
              trend={{ val: 12, positive: true }}
            />
            <KpiCard
              label="Score IA Moyen"
              rawValue={stats?.avg_score ?? 0}
              suffix="/100"
              sub="Modèle de scoring ML"
              icon={Sparkles}
              color="bg-violet-50 text-violet-600"
              trend={{ val: 3, positive: true }}
            />
            <KpiCard
              label="Avec Email"
              rawValue={stats?.email_rate ?? 0}
              suffix="%"
              sub={`${(stats?.with_email ?? 0).toLocaleString('fr')} contacts`}
              icon={Mail}
              color="bg-green-50 text-green-600"
            />
            <KpiCard
              label="Avec Téléphone"
              rawValue={stats ? Math.round((stats.with_phone / total) * 100) : 0}
              suffix="%"
              sub={`${(stats?.with_phone ?? 0).toLocaleString('fr')} contacts`}
              icon={Phone}
              color="bg-cyan-50 text-cyan-600"
            />
          </div>

          {/* Segments */}
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 stagger">
            {segData.map(({ name, value }) => {
              const cfg = SEG_CONFIG[name as keyof typeof SEG_CONFIG]
              if (!cfg) return null
              const pct  = total ? Math.round((value / total) * 100) : 0
              return (
                <div key={name} className="card p-5 animate-fade-up">
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-3 h-3 rounded-full" style={{ background: cfg.color }} />
                    <span className="badge" style={{ background: cfg.bg, color: cfg.color }}>{pct}%</span>
                  </div>
                  <p className="text-2xl font-extrabold tabular-nums" style={{ color: cfg.color }}>
                    {value.toLocaleString('fr')}
                  </p>
                  <p className="text-[12px] font-medium text-gray-500 mt-0.5">{cfg.label}</p>
                  <div className="progress-bar mt-3">
                    <div className="progress-fill" style={{ width: `${pct}%`, background: cfg.color }} />
                  </div>
                </div>
              )
            })}
          </div>

          {/* Charts row 1 */}
          <div className="grid xl:grid-cols-2 gap-6">

            {/* Pie segmentation */}
            <ChartCard title="Segmentation K-Means" subtitle="Répartition intelligente par IA">
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie data={segData} cx="50%" cy="50%" innerRadius={55} outerRadius={90}
                    dataKey="value" paddingAngle={3}>
                    {segData.map(({ name }) => (
                      <Cell key={name} fill={SEG_CONFIG[name as keyof typeof SEG_CONFIG]?.color ?? '#94a3b8'} />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="grid grid-cols-2 gap-2 mt-2">
                {segData.map(({ name, value }) => {
                  const cfg = SEG_CONFIG[name as keyof typeof SEG_CONFIG]
                  return (
                    <div key={name} className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: cfg?.color }} />
                      <span className="text-[11px] text-gray-500 truncate">{name}</span>
                      <span className="text-[11px] font-bold text-gray-800 ml-auto">{value.toLocaleString('fr')}</span>
                    </div>
                  )
                })}
              </div>
            </ChartCard>

            {/* Area leads/semaine */}
            <ChartCard title="Leads par semaine" subtitle="12 dernières semaines">
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={stats?.leads_per_week ?? []} margin={{ left: -10 }}>
                  <defs>
                    <linearGradient id="leadGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0}   />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="week" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="count" name="Leads" stroke="#6366f1" strokeWidth={2.5}
                    fill="url(#leadGrad)" dot={{ r: 3, fill: '#6366f1' }} activeDot={{ r: 5 }} />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          {/* Charts row 2 */}
          <div className="grid xl:grid-cols-2 gap-6">

            {/* Top secteurs */}
            <ChartCard title="Top Secteurs" subtitle="Distribution par activité">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={stats?.sectors?.slice(0, 8) ?? []} layout="vertical" margin={{ left: 10, right: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <YAxis dataKey="sector" type="category" tick={{ fontSize: 10, fill: '#64748b' }} width={130} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="count" name="Leads" radius={[0, 6, 6, 0]}>
                    {(stats?.sectors?.slice(0, 8) ?? []).map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* Couverture contacts */}
            <ChartCard title="Couverture des Contacts" subtitle="Qualité des données collectées">
              <div className="space-y-5 pt-2">
                {[
                  { label: 'Email',     value: stats?.with_email   ?? 0, color: '#10b981', icon: Mail     },
                  { label: 'Téléphone', value: stats?.with_phone   ?? 0, color: '#7c3aed', icon: Phone    },
                  { label: 'Site Web',  value: stats?.with_website ?? 0, color: '#0ea5e9', icon: Activity },
                  { label: 'Enrichis',  value: stats?.enriched     ?? 0, color: '#f59e0b', icon: Sparkles },
                ].map(({ label, value, color, icon: Icon }) => {
                  const pct = total ? Math.round((value / total) * 100) : 0
                  return (
                    <div key={label}>
                      <div className="flex justify-between items-center mb-2">
                        <div className="flex items-center gap-2">
                          <Icon size={14} style={{ color }} />
                          <span className="text-[13px] font-medium text-gray-700">{label}</span>
                        </div>
                        <span className="text-[13px] font-bold text-gray-900">{pct}%
                          <span className="text-gray-400 font-normal text-xs ml-1">({value.toLocaleString('fr')})</span>
                        </span>
                      </div>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${pct}%`, background: color }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </ChartCard>

          </div>

          {/* Sources de Leads */}
          <ChartCard title="Sources de Leads">
            <div className="space-y-3">
              {stats?.sources.map(({ source, count }, i) => {
                const pct = total ? Math.round((count / total) * 100) : 0
                return (
                  <div key={source}>
                    <div className="flex justify-between items-center mb-1.5">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                        <span className="text-[13px] font-medium text-gray-700 capitalize">
                          {source.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <span className="text-[13px] font-bold text-gray-900">
                        {count.toLocaleString('fr')} <span className="text-gray-400 font-normal text-xs">({pct}%)</span>
                      </span>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${pct}%`, background: CHART_COLORS[i % CHART_COLORS.length] }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </ChartCard>

          {/* KPIs Scraping temporels */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "Scrappés aujourd'hui", value: stats?.scraped_today ?? 0,  color: 'text-blue-600',  bg: 'bg-blue-50'  },
              { label: "Cette semaine",         value: stats?.scraped_week  ?? 0,  color: 'text-violet-600',bg: 'bg-violet-50'},
              { label: "Ce mois",               value: stats?.scraped_month ?? 0,  color: 'text-green-600', bg: 'bg-green-50' },
            ].map(({ label, value, color, bg }) => (
              <div key={label} className="card p-5 flex items-center gap-4 animate-fade-up">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${bg}`}>
                  <Activity size={18} className={color} />
                </div>
                <div>
                  <p className={`text-2xl font-extrabold tabular-nums ${color}`}>{value.toLocaleString('fr')}</p>
                  <p className="text-[12px] text-gray-400 font-medium">{label}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Alertes */}
          {alerts.length > 0 && (
            <div className="space-y-3 animate-fade-up">
              <div className="flex items-center gap-2 mb-1">
                <div className="w-1 h-5 rounded-full bg-amber-500" />
                <h3 className="font-bold text-gray-800 text-[15px]">Alertes</h3>
              </div>
              {alerts.map(({ type, msg, Icon }, i) => {
                const cfg = {
                  warning: { bg: 'bg-amber-50 border-amber-200', text: 'text-amber-800', icon: 'text-amber-500' },
                  info:    { bg: 'bg-blue-50 border-blue-200',   text: 'text-blue-800',  icon: 'text-blue-500'  },
                  success: { bg: 'bg-green-50 border-green-200', text: 'text-green-800', icon: 'text-green-500' },
                }[type]
                return (
                  <div key={i} className={`flex items-center px-4 py-3 rounded-xl border ${cfg.bg}`}>
                    <p className={`text-[13px] font-medium ${cfg.text}`}>{msg}</p>
                  </div>
                )
              })}
            </div>
          )}

          {/* Vue Funnel */}
          <ChartCard title="Funnel de conversion" subtitle="Scraping MQL SQL Client">
            <div className="space-y-3 pt-2">
              {funnelSteps.map(({ label, sublabel, value, color, pct }, i) => (
                <div key={label} className="flex items-center gap-4">
                  <div className="w-36 flex-shrink-0 text-right">
                    <p className="text-[13px] font-semibold text-gray-700">{label}</p>
                    <p className="text-[11px] text-gray-400">{sublabel}</p>
                  </div>
                  <div className="flex-1 relative h-9 bg-gray-100 rounded-lg overflow-hidden">
                    <div
                      className="h-full rounded-lg flex items-center pl-3 transition-all duration-700"
                      style={{ width: `${Math.max(pct, 2)}%`, background: color }}
                    >
                      <span className="text-white text-[12px] font-bold whitespace-nowrap">
                        {value.toLocaleString('fr')}
                      </span>
                    </div>
                  </div>
                  <div className="w-12 flex-shrink-0 text-right">
                    <span className="text-[13px] font-bold" style={{ color }}>{pct}%</span>
                  </div>
                  {i < funnelSteps.length - 1 && (
                    <TrendingDown size={14} className="text-gray-300 flex-shrink-0" />
                  )}
                  {i === funnelSteps.length - 1 && (
                    <CheckCircle size={14} className="text-green-400 flex-shrink-0" />
                  )}
                </div>
              ))}
            </div>
          </ChartCard>

        </div>
      </div>
    </div>
  )
}
