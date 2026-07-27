import { useEffect, useState, useRef } from 'react'
import Sidebar from '../components/Navbar'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, PieChart, Pie, Cell,
  AreaChart, Area
} from 'recharts'
import {
  Mail, MousePointer, Send, TrendingUp, Eye,
  Users, RefreshCw, Target, Award, Download, FileText
} from 'lucide-react'
import axios from 'axios'

const API = axios.create({ baseURL: (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000') })
API.interceptors.request.use(c => {
  const t = localStorage.getItem('token') || sessionStorage.getItem('token')
  if (t) c.headers.Authorization = `Bearer ${t}`
  return c
})

const SEG_COLORS: Record<string, string> = {
  'Chaud': '#e11d48', 'Prêts à Acheter': '#ea580c',
  'Froid': '#6366f1', 'A Risque': '#d97706',
}
const PIE_COLORS = ['#6366f1', '#7c3aed', '#10b981', '#f59e0b', '#e11d48', '#0ea5e9']

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-100 rounded-xl shadow-lg px-4 py-3 text-sm">
      {label && <p className="font-semibold text-gray-700 mb-1">{label}</p>}
      {payload.map((p: any) => (
        <div key={p.name} className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-gray-500">{p.name} :</span>
          <span className="font-bold text-gray-800">{p.value}</span>
        </div>
      ))}
    </div>
  )
}

function KpiCard({ label, value, sub, icon, color, trend }: {
  label: string; value: string | number; sub?: string
  icon: React.ReactNode; color: string; trend?: string
}) {
  return (
    <div className="card p-5 flex items-start gap-4 animate-fade-up">
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 ${color}`}>
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest mb-1">{label}</p>
        <p className="text-2xl font-extrabold text-gray-900 tabular-nums">{value}</p>
        {sub && <p className="text-[11px] text-gray-400 mt-0.5 truncate">{sub}</p>}
      </div>
      {trend && (
        <span className="text-[11px] font-bold text-green-600 bg-green-50 px-2 py-0.5 rounded-full flex-shrink-0">{trend}</span>
      )}
    </div>
  )
}

export default function Rapports() {
  const [engagement, setEngagement]   = useState<any>(null)
  const [emailStats, setEmailStats]   = useState<any>(null)
  const [leadStats, setLeadStats]     = useState<any>(null)
  const [abStats, setAbStats]         = useState<any>(null)
  const [weeklyStats, setWeeklyStats]         = useState<any[]>([])
  const [campaignHistory, setCampaignHistory] = useState<any[]>([])
  const [compareA, setCompareA]               = useState<string>('')
  const [compareB, setCompareB]               = useState<string>('')
  const [loading, setLoading]                 = useState(true)
  const [exporting, setExporting]     = useState<'excel' | 'pdf' | null>(null)
  const reportRef = useRef<HTMLDivElement>(null)

  const handleExportExcel = async () => {
    setExporting('excel')
    try {
      const token = localStorage.getItem('token') || sessionStorage.getItem('token')
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/leads/export/excel`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!response.ok) throw new Error('Export échoué')
      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = `leads_leadnova_${new Date().toISOString().slice(0, 10)}.xlsx`
      a.click()
      URL.revokeObjectURL(objectUrl)
    } catch {
      alert("Erreur lors de l'export Excel.")
    } finally {
      setExporting(null)
    }
  }

  const handleExportPDF = async () => {
    setExporting('pdf')
    try {
      const token = localStorage.getItem('token') || sessionStorage.getItem('token')
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/leads/export/report-pdf`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!response.ok) throw new Error('Export échoué')
      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = `rapport_leadnova_${new Date().toISOString().slice(0, 10)}.pdf`
      a.click()
      URL.revokeObjectURL(objectUrl)
    } catch {
      alert("Erreur lors de l'export PDF.")
    } finally {
      setExporting(null)
    }
  }

  const fetchAll = () => {
    setLoading(true)
    Promise.all([
      API.get('/campaigns/stats/engagement').catch(() => ({ data: null })),
      API.get('/campaigns/stats/email').catch(() => ({ data: null })),
      API.get('/leads/stats').catch(() => ({ data: null })),
      API.get('/campaigns/ab-stats').catch(() => ({ data: null })),
      API.get('/campaigns/stats/weekly').catch(() => ({ data: [] })),
      API.get('/campaigns/history').catch(() => ({ data: [] })),
    ]).then(([eng, email, leads, ab, weekly, history]) => {
      setEngagement(eng.data)
      setEmailStats(email.data)
      setLeadStats(leads.data)
      setAbStats(ab.data)
      setWeeklyStats(weekly.data || [])
      setCampaignHistory(history.data || [])
    }).finally(() => setLoading(false))
  }

  useEffect(() => { fetchAll() }, [])

  const segmentBarData = engagement?.by_segment?.map((s: any) => ({
    name: s.segment, 'Envoyés': s.sent, 'Ouverts': s.opened, 'Cliqués': s.clicked,
  })) ?? []

  const abBarData = abStats
    ? ['A', 'B'].map(v => ({
        version: `Version ${v}`,
        'Assignés': abStats[v]?.total ?? 0,
        'Envoyés':  abStats[v]?.sent  ?? 0,
        'Taux (%)': abStats[v]?.open_rate ?? 0,
      }))
    : []

  const segPieData = leadStats?.segments
    ? Object.entries(leadStats.segments).map(([name, value]) => ({ name, value }))
    : []

  const sourceData = (() => {
    const raw = leadStats?.sources ?? []
    const pjmCount = raw.find((s: any) =>
      s.source?.toLowerCase().includes('pages jaunes') || s.source?.toLowerCase().includes('pages_jaunes')
    )?.count ?? 0
    const merged = raw
      .filter((s: any) => !s.source?.toLowerCase().includes('pages jaunes') && !s.source?.toLowerCase().includes('pages_jaunes'))
      .map((s: any) => s.source?.toLowerCase().includes('scraping') ? { ...s, count: s.count + pjmCount } : s)
    return merged.map((s: any) => ({
      name: s.source?.replace(/_/g, ' ') ?? '—',
      value: s.count,
    }))
  })()

  if (loading) return (
    <div className="flex h-screen bg-[var(--bg)]">
      <Sidebar />
      <div className="ml-[var(--sidebar-w)] flex-1 transition-[margin-left] duration-200 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw size={24} className="animate-spin text-blue-500 mx-auto mb-3" />
          <p className="text-gray-400 text-sm">Chargement des analytics...</p>
        </div>
      </div>
    </div>
  )

  return (
    <div className="flex h-screen bg-[var(--bg)]">
      <Sidebar />
      <div className="ml-[var(--sidebar-w)] flex-1 transition-[margin-left] duration-200 overflow-auto min-w-0">

        {/* Header */}
        <header className="sticky top-0 z-20 bg-white/80 backdrop-blur-md border-b border-gray-100 px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-extrabold text-gray-900 font-display tracking-tight">Analytics</h1>
              <p className="text-[12px] text-gray-400 mt-0.5">
                {leadStats?.total?.toLocaleString('fr')} leads analysés
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={fetchAll} className="btn btn-secondary text-xs">
                <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Actualiser
              </button>
              <button
                onClick={handleExportExcel}
                disabled={exporting !== null}
                className="btn btn-secondary text-xs bg-green-50 border-green-200 text-green-700 hover:bg-green-100"
              >
                <Download size={13} className={exporting === 'excel' ? 'animate-bounce' : ''} />
                {exporting === 'excel' ? 'Export...' : 'Export Excel'}
              </button>
              <button
                onClick={handleExportPDF}
                disabled={exporting !== null}
                className="btn btn-secondary text-xs bg-red-50 border-red-200 text-red-700 hover:bg-red-100"
              >
                <FileText size={13} className={exporting === 'pdf' ? 'animate-bounce' : ''} />
                {exporting === 'pdf' ? 'Génération...' : 'Export PDF'}
              </button>
            </div>
          </div>
        </header>

        <div ref={reportRef} className="p-8 space-y-8">

          {/* Section Leads */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1 h-5 rounded-full bg-[var(--nova-600)]" />
              <h2 className="font-bold text-gray-800 text-[15px]">Base de Leads</h2>
            </div>
            <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
              <KpiCard
                label="Total Leads" value={leadStats?.total?.toLocaleString('fr') ?? 0}
                sub="unique, dédupliqués"
                icon={<Users size={20} className="text-blue-600" />} color="bg-blue-50"
              />
              <KpiCard
                label="Score moyen" value={`${leadStats?.avg_score ?? 0}/100`}
                sub="modèle de scoring ML"
                icon={<TrendingUp size={20} className="text-[var(--nova-600)]" />} color="bg-[var(--nova-50)]"
              />
              <KpiCard
                label="Avec email" value={`${leadStats?.email_rate ?? 0}%`}
                sub={`${leadStats?.with_email?.toLocaleString('fr')} contacts`}
                icon={<Mail size={20} className="text-green-600" />} color="bg-green-50"
              />
              <KpiCard
                label="Leads chauds" value={leadStats?.segments?.Chaud?.toLocaleString('fr') ?? 0}
                sub="prêts à être contactés"
                icon={<Target size={20} className="text-red-500" />} color="bg-red-50"
              />
            </div>
          </div>

          {/* Section Email */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1 h-5 rounded-full bg-green-500" />
              <h2 className="font-bold text-gray-800 text-[15px]">Engagement Email</h2>
            </div>
            <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
              <KpiCard
                label="Emails envoyés" value={engagement?.sent?.toLocaleString('fr') ?? 0}
                sub={`sur ${emailStats?.total_with_email?.toLocaleString('fr')} éligibles`}
                icon={<Send size={20} className="text-blue-600" />} color="bg-blue-50"
              />
              <KpiCard
                label="Taux d'ouverture" value={`${engagement?.open_rate ?? 0}%`}
                sub={`${engagement?.opened?.toLocaleString('fr') ?? 0} ouvertures`}
                icon={<Eye size={20} className="text-green-600" />} color="bg-green-50"
              />
              <KpiCard
                label="Taux de clic" value={`${engagement?.click_rate ?? 0}%`}
                sub={`${engagement?.clicked?.toLocaleString('fr') ?? 0} clics`}
                icon={<MousePointer size={20} className="text-orange-600" />} color="bg-orange-50"
              />
              <KpiCard
                label="Emails générés" value={emailStats?.generated?.toLocaleString('fr') ?? 0}
                sub="génération A/B Testing"
                icon={<Award size={20} className="text-violet-600" />} color="bg-violet-50"
              />
            </div>
          </div>

          {/* Graphiques row 1 */}
          <div className="grid xl:grid-cols-2 gap-6">

            {/* Segmentation pie */}
            <div className="card p-6">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-1 h-5 rounded-full bg-violet-500" />
                <div>
                  <h2 className="font-bold text-gray-900 text-[15px]">Segmentation des leads</h2>
                  <p className="text-[11px] text-gray-400">Répartition par segment IA</p>
                </div>
              </div>
              {segPieData.length > 0 ? (
                <div className="flex items-center gap-6">
                  <ResponsiveContainer width={180} height={180}>
                    <PieChart>
                      <Pie data={segPieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3} dataKey="value">
                        {segPieData.map((entry: any) => (
                          <Cell key={entry.name} fill={SEG_COLORS[entry.name] || '#6366f1'} />
                        ))}
                      </Pie>
                      <Tooltip content={<CustomTooltip />} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex-1 space-y-2">
                    {segPieData.map((s: any) => {
                      const total = segPieData.reduce((a: number, b: any) => a + Number(b.value), 0)
                      const pct = total > 0 ? Math.round((Number(s.value) / total) * 100) : 0
                      return (
                        <div key={s.name} className="flex items-center gap-2">
                          <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: SEG_COLORS[s.name] || '#6366f1' }} />
                          <span className="text-[12px] text-gray-600 flex-1">{s.name}</span>
                          <span className="text-[12px] font-bold text-gray-900">{Number(s.value).toLocaleString('fr')}</span>
                          <span className="text-[11px] text-gray-400 w-8 text-right">{pct}%</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-center h-48 text-gray-300 flex-col gap-2">
                  <Target size={32} />
                  <p className="text-sm">Aucune donnée de segmentation</p>
                </div>
              )}
            </div>

            {/* Sources bar */}
            <div className="card p-6">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-1 h-5 rounded-full bg-blue-500" />
                <div>
                  <h2 className="font-bold text-gray-900 text-[15px]">Leads par source</h2>
                  <p className="text-[11px] text-gray-400">Provenance des leads</p>
                </div>
              </div>
              {sourceData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={sourceData} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                    <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} width={80} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="value" fill="#6366f1" radius={[0, 4, 4, 0]} name="Leads" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-48 text-gray-300 flex-col gap-2">
                  <Users size={32} />
                  <p className="text-sm">Aucune donnée source</p>
                </div>
              )}
            </div>
          </div>

          {/* Graphiques row 2 */}
          <div className="grid xl:grid-cols-2 gap-6">

            {/* Engagement par segment */}
            <div className="card p-6">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-1 h-5 rounded-full bg-green-500" />
                <div>
                  <h2 className="font-bold text-gray-900 text-[15px]">Engagement par segment</h2>
                  <p className="text-[11px] text-gray-400">Envoyés / Ouverts / Cliqués</p>
                </div>
              </div>
              {segmentBarData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={segmentBarData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} />
                    <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="Envoyés" fill="#6366f1" radius={[3,3,0,0]} />
                    <Bar dataKey="Ouverts"  fill="#10b981" radius={[3,3,0,0]} />
                    <Bar dataKey="Cliqués"  fill="#f59e0b" radius={[3,3,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-48 text-gray-300 flex-col gap-2">
                  <Mail size={32} />
                  <p className="text-sm">Aucun email envoyé encore</p>
                  <p className="text-xs">Lancez une campagne pour voir les stats</p>
                </div>
              )}
            </div>

            {/* A/B Testing */}
            <div className="card p-6">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-1 h-5 rounded-full bg-orange-500" />
                <div>
                  <h2 className="font-bold text-gray-900 text-[15px]">Résultats A/B Testing</h2>
                  <p className="text-[11px] text-gray-400">Comparaison Version A vs B</p>
                </div>
              </div>
              {abBarData.some(d => d['Envoyés'] > 0) ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={abBarData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="version" tick={{ fontSize: 11, fill: '#64748b' }} />
                    <YAxis yAxisId="left" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                    <YAxis yAxisId="right" orientation="right" unit="%" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar yAxisId="left"  dataKey="Assignés" fill="#6366f1" radius={[3,3,0,0]} />
                    <Bar yAxisId="left"  dataKey="Envoyés"  fill="#10b981" radius={[3,3,0,0]} />
                    <Bar yAxisId="right" dataKey="Taux (%)" fill="#f59e0b" radius={[3,3,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-48 text-gray-300 flex-col gap-2">
                  <Award size={32} />
                  <p className="text-sm">Pas encore de données A/B</p>
                </div>
              )}
            </div>
          </div>

          {/* Évolution hebdomadaire */}
          {weeklyStats.length > 0 && (
            <div className="card p-6 animate-fade-up">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-1 h-5 rounded-full bg-sky-500" />
                <div>
                  <h2 className="font-bold text-gray-900 text-[15px]">Évolution des campagnes</h2>
                  <p className="text-[11px] text-gray-400">Taux d'ouverture & clic par semaine (8 dernières semaines)</p>
                </div>
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={weeklyStats} margin={{ top: 4, right: 4, bottom: 0, left: -10 }}>
                  <defs>
                    <linearGradient id="gradOpen" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#10b981" stopOpacity={0.18} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gradClick" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#f59e0b" stopOpacity={0.18} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="week" tick={{ fontSize: 11, fill: '#64748b' }} />
                  <YAxis unit="%" tick={{ fontSize: 11, fill: '#94a3b8' }} domain={[0, 'auto']} />
                  <Tooltip content={<CustomTooltip />} formatter={(v: any) => `${v}%`} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Area type="monotone" dataKey="open_rate"  name="Taux ouverture (%)" stroke="#10b981" strokeWidth={2} fill="url(#gradOpen)"  dot={{ r: 3, fill: '#10b981' }} />
                  <Area type="monotone" dataKey="click_rate" name="Taux clic (%)"      stroke="#f59e0b" strokeWidth={2} fill="url(#gradClick)" dot={{ r: 3, fill: '#f59e0b' }} />
                </AreaChart>
              </ResponsiveContainer>
              <div className="mt-3 grid grid-cols-3 gap-3">
                {[
                  { label: 'Semaines analysées', val: weeklyStats.length },
                  { label: 'Ouverture moy.', val: `${(weeklyStats.reduce((a, w) => a + w.open_rate, 0) / weeklyStats.length).toFixed(1)}%` },
                  { label: 'Clic moy.', val: `${(weeklyStats.reduce((a, w) => a + w.click_rate, 0) / weeklyStats.length).toFixed(1)}%` },
                ].map(({ label, val }) => (
                  <div key={label} className="rounded-xl bg-gray-50 border border-gray-100 px-4 py-3 text-center">
                    <p className="text-[10px] text-gray-400 uppercase tracking-widest font-semibold">{label}</p>
                    <p className="text-lg font-extrabold text-gray-900 mt-1">{val}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Table taux par segment */}
          {engagement?.by_segment?.length > 0 && (
            <div className="card overflow-hidden animate-fade-up">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                <div className="w-1 h-5 rounded-full bg-[var(--nova-500)]" />
                <h2 className="font-bold text-gray-900 text-[15px]">Taux d'ouverture & clic par segment</h2>
              </div>
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50/80 border-b border-gray-100">
                    {['Segment', 'Envoyés', 'Ouverture', 'Clic', 'Performance'].map(h => (
                      <th key={h} className="px-6 py-3 text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {engagement.by_segment.map((s: any) => (
                    <tr key={s.segment} className="table-row-hover">
                      <td className="px-6 py-3.5">
                        <div className="flex items-center gap-2">
                          <div className="w-2.5 h-2.5 rounded-full" style={{ background: SEG_COLORS[s.segment] ?? '#6366f1' }} />
                          <span className="font-semibold text-[13px] text-gray-800">{s.segment}</span>
                        </div>
                      </td>
                      <td className="px-6 py-3.5 text-[13px] text-gray-600">{s.sent}</td>
                      <td className="px-6 py-3.5 font-bold text-green-600 text-[13px]">{s.open_rate}%</td>
                      <td className="px-6 py-3.5 font-bold text-orange-500 text-[13px]">{s.click_rate}%</td>
                      <td className="px-6 py-3.5">
                        <div className="space-y-1.5">
                          <div className="flex items-center gap-2">
                            <div className="w-20 bg-gray-100 rounded-full h-1.5">
                              <div className="h-1.5 rounded-full bg-green-500" style={{ width: `${Math.min(s.open_rate * 2, 100)}%` }} />
                            </div>
                            <span className="text-[10px] text-gray-400 w-6">ouv</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="w-20 bg-gray-100 rounded-full h-1.5">
                              <div className="h-1.5 rounded-full bg-orange-400" style={{ width: `${Math.min(s.click_rate * 5, 100)}%` }} />
                            </div>
                            <span className="text-[10px] text-gray-400 w-6">clic</span>
                          </div>
                          <span className="text-[10px] font-semibold text-gray-500">
                            {s.open_rate > 20 ? 'Bon' : s.open_rate > 10 ? 'Moyen' : 'Faible'}
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Funnel email */}
          {emailStats && (
            <div className="card p-6 animate-fade-up">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-1 h-5 rounded-full bg-[var(--nova-500)]" />
                <h2 className="font-bold text-gray-900 text-[15px]">Funnel email</h2>
              </div>
              {(() => {
                const steps = [
                  { label: 'Générés',  val: emailStats.generated ?? 0, color: 'bg-[var(--nova-400)]' },
                  { label: 'Envoyés',  val: emailStats.sent ?? 0,      color: 'bg-blue-400' },
                  { label: 'Ouverts',  val: emailStats.opened ?? 0,    color: 'bg-green-500' },
                  { label: 'Cliqués',  val: emailStats.clicked ?? 0,   color: 'bg-orange-400' },
                ]
                const max = steps[0].val || 1
                return (
                  <div className="space-y-3">
                    {steps.map((step, i) => {
                      const pct = Math.round((step.val / max) * 100)
                      const conv = i > 0 && steps[i-1].val > 0
                        ? `${Math.round((step.val / steps[i-1].val) * 100)}% du précédent`
                        : ''
                      return (
                        <div key={step.label} className="flex items-center gap-4">
                          <div className="w-20 text-right text-[11px] font-semibold text-gray-500 shrink-0">{step.label}</div>
                          <div className="flex-1 bg-gray-100 rounded-full h-7 overflow-hidden relative">
                            <div className={`h-full ${step.color} rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} />
                            <span className="absolute inset-0 flex items-center px-3 text-[11px] font-bold text-white drop-shadow">
                              {step.val.toLocaleString()}
                            </span>
                          </div>
                          <div className="w-28 text-[10px] text-gray-400 shrink-0 text-right">
                            {pct}%{conv ? ` · ${conv}` : ''}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )
              })()}
            </div>
          )}

          {/* Comparaison entre campagnes */}
          {campaignHistory.length >= 2 && (
            <div className="card p-6 animate-fade-up">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-1 h-5 rounded-full bg-orange-400" />
                <h2 className="font-bold text-gray-900 text-[15px]">Comparaison entre campagnes</h2>
              </div>
              <div className="flex flex-col sm:flex-row gap-3 mb-5">
                {[
                  { val: compareA, set: setCompareA, label: 'Campagne A' },
                  { val: compareB, set: setCompareB, label: 'Campagne B' },
                ].map(({ val, set, label }) => (
                  <div key={label} className="flex-1">
                    <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">{label}</label>
                    <select className="input text-sm w-full" value={val} onChange={e => set(e.target.value)}>
                      <option value="">— choisir —</option>
                      {campaignHistory.map((c: any) => (
                        <option key={c.id} value={String(c.id)}>
                          {c.campaign_name || c.name || `#${c.id}`}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
              {compareA && compareB && compareA !== compareB && (() => {
                const ca = campaignHistory.find((c: any) => String(c.id) === compareA)
                const cb = campaignHistory.find((c: any) => String(c.id) === compareB)
                if (!ca || !cb) return null
                const metrics = [
                  { label: 'Leads ciblés', a: ca.leads_targeted ?? 0,          b: cb.leads_targeted ?? 0,          unit: '' },
                  { label: 'Envoyés',      a: ca.stats?.sent ?? 0,              b: cb.stats?.sent ?? 0,              unit: '' },
                  { label: 'Ouverture',    a: ca.stats?.open_rate  ?? ca.open_rate  ?? 0, b: cb.stats?.open_rate  ?? cb.open_rate  ?? 0, unit: '%' },
                  { label: 'Clic',         a: ca.stats?.click_rate ?? ca.click_rate ?? 0, b: cb.stats?.click_rate ?? cb.click_rate ?? 0, unit: '%' },
                ]
                return (
                  <div className="space-y-3">
                    <div className="grid grid-cols-3 text-[10px] font-bold text-gray-400 uppercase tracking-widest pb-1 border-b border-gray-100">
                      <span>{ca.campaign_name || ca.name || `#${ca.id}`}</span>
                      <span className="text-center">Métrique</span>
                      <span className="text-right">{cb.campaign_name || cb.name || `#${cb.id}`}</span>
                    </div>
                    {metrics.map(m => {
                      const aVal = Number(m.a); const bVal = Number(m.b)
                      const maxV = Math.max(aVal, bVal, 1)
                      const aWins = aVal >= bVal
                      return (
                        <div key={m.label} className="grid grid-cols-3 items-center gap-3">
                          <div className="flex items-center gap-2 justify-end">
                            <span className={`text-[13px] font-bold ${aWins ? 'text-green-600' : 'text-gray-500'}`}>
                              {aVal.toLocaleString()}{m.unit}
                            </span>
                            <div className="w-20 bg-gray-100 rounded-full h-2 overflow-hidden">
                              <div className={`h-full ${aWins ? 'bg-green-500' : 'bg-gray-300'} rounded-full`}
                                style={{ width: `${(aVal / maxV) * 100}%` }} />
                            </div>
                          </div>
                          <div className="text-center text-[10px] font-semibold text-gray-400">{m.label}</div>
                          <div className="flex items-center gap-2">
                            <div className="w-20 bg-gray-100 rounded-full h-2 overflow-hidden">
                              <div className={`h-full ${!aWins ? 'bg-green-500' : 'bg-gray-300'} rounded-full`}
                                style={{ width: `${(bVal / maxV) * 100}%` }} />
                            </div>
                            <span className={`text-[13px] font-bold ${!aWins ? 'text-green-600' : 'text-gray-500'}`}>
                              {bVal.toLocaleString()}{m.unit}
                            </span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )
              })()}
              {compareA === compareB && compareA !== '' && (
                <p className="text-[12px] text-amber-600 text-center py-2">Sélectionnez deux campagnes différentes</p>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  )
}

