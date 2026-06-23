import { useEffect, useState } from 'react'
import Sidebar from '../components/Navbar'
import axios from 'axios'
import {
  Play, Trash2, RefreshCw, Plus, Clock, CheckCircle,
  AlertCircle, Loader, MapPin, Search, Building2, TrendingUp
} from 'lucide-react'

const API = axios.create({ baseURL: (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000') })
API.interceptors.request.use(c => {
  const t = localStorage.getItem('token')
  if (t) c.headers.Authorization = `Bearer ${t}`
  return c
})

const SOURCE_COLORS: Record<string, string> = {
  'Google Maps':        'bg-green-100 text-green-700',
  'Pages Jaunes':       'bg-yellow-100 text-yellow-700',
  'Pages Jaunes Maroc': 'bg-orange-100 text-orange-700',
  'Import CSV':         'bg-gray-100 text-gray-700',
}

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  en_attente: { label: 'En attente', color: 'text-gray-500',  icon: Clock },
  actif:      { label: 'En cours',   color: 'text-blue-600',  icon: Loader },
  termine:    { label: 'Terminé',    color: 'text-green-600', icon: CheckCircle },
  erreur:     { label: 'Erreur',     color: 'text-red-600',   icon: AlertCircle },
}

const SEGMENT_COLORS: Record<string, string> = {
  'Chaud':    'bg-red-100 text-red-700',
  'Prêts à Acheter': 'bg-orange-100 text-orange-700',
  'Froid':    'bg-blue-100 text-blue-700',
  'À Risque': 'bg-gray-100 text-gray-600',
}

const SECTORS = [
  'Informatique & Tech', 'Finance & Comptabilité', 'Santé', 'Immobilier',
  'Construction & BTP', 'Transport & Logistique', 'Education & Formation',
  'Restauration & Hôtellerie', 'Industrie & Production', 'Commerce & Distribution',
  'Services aux entreprises', 'Agriculture & Alimentaire', 'Energie & Environnement',
  'Juridique', 'Marketing & Communication'
]

export default function Scraping() {
  const [stats, setStats]             = useState<any>(null)
  const [jobs, setJobs]               = useState<any[]>([])
  const [recentLeads, setRecentLeads] = useState<any[]>([])
  const [deletingId, setDeletingId]   = useState<number | null>(null)
  const [loading, setLoading]         = useState(true)
  const [showModal, setShowModal]     = useState(false)
  const [submitting, setSubmitting]   = useState(false)
  const [alert, setAlert]             = useState<{ type: 'success' | 'error'; msg: string } | null>(null)

  const [form, setForm] = useState({
    name: '', source: 'Google Maps', keywords: '',
    location: '', sector: '', maxLeads: 100,
  })
  const [csvFile, setCsvFile]       = useState<File | null>(null)
  const [csvUploading, setCsvUploading] = useState(false)
  const [csvUploaded, setCsvUploaded]   = useState(false)

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [s, j, l] = await Promise.all([
        API.get('/scraping/stats'),
        API.get('/scraping/jobs'),
        API.get('/scraping/recent-leads'),
      ])
      setStats(s.data)
      setJobs(j.data)
      setRecentLeads(l.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAll() }, [])

  const deleteLead = async (id: number) => {
    if (!confirm('Supprimer ce lead ?')) return
    setDeletingId(id)
    try {
      await axios.delete(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/leads/${id}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      })
      setRecentLeads(prev => prev.filter(l => l.id !== id))
    } catch {
      alert('Erreur lors de la suppression')
    } finally {
      setDeletingId(null)
    }
  }

  const createJob = async () => {
    if (!form.name.trim()) return
    setSubmitting(true)
    const maxLeads = Math.min(500, Math.max(1, Number(form.maxLeads) || 1))
    try {
      await API.post('/scraping/jobs', { ...form, maxLeads })
      setAlert({ type: 'success', msg: `Job "${form.name}" créé avec succès` })
      setShowModal(false)
      setForm({ name: '', source: 'Google Maps', keywords: '', location: '', sector: '', maxLeads: 100 })
      fetchAll()
    } catch (e: any) {
      setAlert({ type: 'error', msg: ` Erreur : ${e.message}` })
    } finally {
      setSubmitting(false)
    }
  }

  const deleteJob = async (id: number, name: string) => {
    if (!confirm(`Supprimer le job "${name}" ?`)) return
    await API.delete(`/scraping/jobs/${id}`)
    setJobs(jobs.filter(j => j.id !== id))
    fetchAll()
  }

  const startJob = async (id: number) => {
    try {
      await API.post(`/scraping/jobs/${id}/start`)
      setAlert({ type: 'success', msg: 'Scraping lancé — les leads arrivent dans quelques secondes...' })
      // Polling toutes les 3s pendant 60s max
      let tries = 0
      const poll = setInterval(async () => {
        tries++
        await fetchAll()
        if (tries >= 20) clearInterval(poll)
      }, 3000)
    } catch (e: any) {
      setAlert({ type: 'error', msg: ` ${e.response?.data?.detail || e.message}` })
    }
  }

  const updateStatus = async (id: number, status: string) => {
    const res = await API.patch(`/scraping/jobs/${id}/status`, { status })
    setJobs(jobs.map(j => j.id === id ? res.data : j))
    fetchAll()
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />
      <div className="ml-52 flex-1 overflow-auto min-w-0">

        {/* Modal Nouveau Job */}
        {showModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
              <div className="px-6 py-4 border-b flex justify-between items-center">
                <h2 className="text-lg font-bold text-gray-900">Nouveau Job de Scraping</h2>
                <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">×</button>
              </div>
              <div className="p-6 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                    Nom du job <span className="text-red-500">*</span>
                  </label>
                  <input type="text" placeholder="Ex: Google Maps — Restaurants Tunis"
                    value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Source</label>
                  <select value={form.source} onChange={e => { setForm({ ...form, source: e.target.value }); setCsvFile(null); setCsvUploaded(false) }}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400">
                    {Object.keys(SOURCE_COLORS).map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>

                {/* Upload CSV — visible uniquement si source = Import CSV */}
                {form.source === 'Import CSV' && (
                  <div>
                    <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Fichier CSV</label>
                    {!csvUploaded ? (
                      <label className="flex flex-col items-center justify-center w-full h-24 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors">
                        <span className="text-sm text-gray-400">{csvFile ? csvFile.name : ' Cliquez pour choisir un fichier .csv'}</span>
                        {csvFile && (
                          <button
                            type="button"
                            disabled={csvUploading}
                            onClick={async (e) => {
                              e.preventDefault()
                              setCsvUploading(true)
                              const fd = new FormData()
                              fd.append('file', csvFile)
                              try {
                                await axios.post(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/scraping/upload-csv`, fd, {
                                  headers: { Authorization: `Bearer ${localStorage.getItem('token') || sessionStorage.getItem('token')}` }
                                })
                                setCsvUploaded(true)
                              } catch { alert('Erreur upload CSV') }
                              finally { setCsvUploading(false) }
                            }}
                            className="mt-2 px-3 py-1 bg-blue-500 text-white text-xs rounded-lg hover:bg-blue-600 disabled:opacity-50"
                          >
                            {csvUploading ? 'Upload...' : ' Uploader'}
                          </button>
                        )}
                        <input type="file" accept=".csv" className="hidden" onChange={e => { setCsvFile(e.target.files?.[0] || null); setCsvUploaded(false) }} />
                      </label>
                    ) : (
                      <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                        <span className="text-green-600 text-sm">{csvFile?.name} uploadé</span>
                        <button type="button" onClick={() => { setCsvFile(null); setCsvUploaded(false) }} className="text-xs text-gray-400 hover:text-red-500 ml-auto">Changer</button>
                      </div>
                    )}
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Mots-clés</label>
                  <input type="text" placeholder="Ex: restaurant, café, pizzeria..."
                    value={form.keywords} onChange={e => setForm({ ...form, keywords: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Localisation</label>
                  <input type="text"
                    placeholder="Ex: Tunis, Sfax, Sousse..."
                    value={form.location} onChange={e => setForm({ ...form, location: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                    Nombre de leads à scraper
                  </label>
                  <input type="number" min={1} max={500} value={form.maxLeads}
                    onChange={e => setForm({ ...form, maxLeads: Number(e.target.value) })}
                    placeholder="Ex : 100"
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400"
                  />
                  <p className="text-xs text-gray-400 mt-1">Entre 1 et 500</p>
                </div>
              </div>
              <div className="px-6 pb-5 flex gap-3">
                <button onClick={() => setShowModal(false)}
                  className="flex-1 border border-gray-200 text-gray-600 py-2.5 rounded-lg text-sm hover:bg-gray-50">
                  Annuler
                </button>
                <button onClick={createJob} disabled={!form.name.trim() || submitting}
                  className="flex-1 bg-blue-600 text-white py-2.5 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-40 font-medium flex items-center justify-center gap-2">
                  {submitting ? <Loader size={14} className="animate-spin"/> : <Play size={14}/>}
                  Créer le job
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Header */}
        <div className="bg-white px-6 py-4 border-b sticky top-0 z-10 shadow-sm">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-xl font-bold text-gray-900">Scraping de Leads</h1>
              <p className="text-gray-400 text-sm">Collectez automatiquement des leads qualifiés</p>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={fetchAll} className="p-2 hover:bg-gray-100 rounded-lg text-gray-500">
                <RefreshCw size={16} className={loading ? 'animate-spin' : ''}/>
              </button>
              <button onClick={() => setShowModal(true)}
                className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700">
                <Plus size={15}/> Nouveau Job
              </button>
            </div>
          </div>
        </div>

        <div className="p-6 space-y-6">

          {/* Alerte */}
          {alert && (
            <div className={`p-4 rounded-xl border flex items-center gap-3 ${alert.type === 'success' ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50 border-red-200 text-red-800'}`}>
              {alert.type === 'success' ? <CheckCircle size={16}/> : <AlertCircle size={16}/>}
              <span className="text-sm flex-1">{alert.msg}</span>
              <button onClick={() => setAlert(null)} className="text-xs underline opacity-60">Fermer</button>
            </div>
          )}

          {/* KPIs */}
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: 'Jobs Actifs',       value: stats?.jobs_actifs     ?? 0, color: 'text-blue-600',  bg: 'bg-blue-50',  icon: Play },
              { label: 'Leads en Base',      value: stats?.leads_collectes ?? 0, color: 'text-green-600', bg: 'bg-green-50', icon: TrendingUp },
              { label: 'En Attente',        value: stats?.en_attente      ?? 0, color: 'text-orange-500',bg: 'bg-orange-50',icon: Clock },
              { label: 'Taux de Succès',    value: `${stats?.taux_succes ?? 0}%`, color: 'text-purple-600', bg: 'bg-purple-50', icon: CheckCircle },
            ].map(({ label, value, color, bg, icon: Icon }) => (
              <div key={label} className="bg-white rounded-xl border shadow-sm p-5">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{label}</p>
                  <div className={`w-8 h-8 rounded-lg ${bg} flex items-center justify-center`}>
                    <Icon size={15} className={color}/>
                  </div>
                </div>
                <p className={`text-3xl font-extrabold ${color}`}>{value}</p>
              </div>
            ))}
          </div>

          {/* Jobs Table */}
          <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-1 h-5 bg-blue-600 rounded"/>
                <h2 className="font-bold text-gray-800">Jobs de Scraping</h2>
                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">{jobs.length}</span>
              </div>
            </div>

            {jobs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                <Search size={32} className="mb-3 opacity-20"/>
                <p className="text-sm font-medium">Aucun job de scraping</p>
                <p className="text-xs mt-1">Cliquez sur "Nouveau Job" pour commencer</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-xs text-gray-500 font-semibold uppercase tracking-wide">
                      <th className="px-4 py-3 text-left">Nom</th>
                      <th className="px-4 py-3 text-left">Source</th>
                      <th className="px-4 py-3 text-left">Mots-clés</th>
                      <th className="px-4 py-3 text-left">Localisation</th>
                      <th className="px-4 py-3 text-left">Max</th>
                      <th className="px-4 py-3 text-left">Leads</th>
                      <th className="px-4 py-3 text-left">Statut</th>
                      <th className="px-4 py-3 text-left">Date</th>
                      <th className="px-4 py-3"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {jobs.map(job => {
                      const cfg = STATUS_CONFIG[job.status] || STATUS_CONFIG['en_attente']
                      const Icon = cfg.icon
                      return (
                        <tr key={job.id} className="hover:bg-gray-50 transition-colors">
                          <td className="px-4 py-3 font-semibold text-gray-900">{job.name}</td>
                          <td className="px-4 py-3">
                            <span className={`text-xs px-2 py-1 rounded-full font-medium ${SOURCE_COLORS[job.source] || 'bg-gray-100 text-gray-600'}`}>
                              {job.source}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-500 text-xs max-w-[120px] truncate">{job.keywords || '—'}</td>
                          <td className="px-4 py-3 text-gray-500 text-xs">
                            {job.location ? <span className="flex items-center gap-1"><MapPin size={10}/>{job.location}</span> : '—'}
                          </td>
                          <td className="px-4 py-3 text-gray-500 text-xs">{job.max_leads}</td>
                          <td className="px-4 py-3">
                            <span className="font-bold text-green-600">{job.leads_collected}</span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`flex items-center gap-1.5 text-xs font-medium ${cfg.color}`}>
                              <Icon size={13} className={job.status === 'actif' ? 'animate-spin' : ''}/>
                              {cfg.label}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-gray-400 text-xs">
                            {new Date(job.created_at).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-1">
                              {job.status === 'en_attente' && (
                                <button onClick={() => startJob(job.id)}
                                  title="Lancer le scraping"
                                  className="p-1.5 hover:bg-blue-50 rounded text-blue-500 hover:text-blue-700">
                                  <Play size={13}/>
                                </button>
                              )}
                              {job.status === 'actif' && (
                                <span title="En cours..." className="p-1.5">
                                  <Loader size={13} className="animate-spin text-blue-400"/>
                                </span>
                              )}
                              <button onClick={() => deleteJob(job.id, job.name)}
                                className="p-1.5 hover:bg-red-50 rounded text-gray-300 hover:text-red-400">
                                <Trash2 size={13}/>
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Leads récemment collectés */}
          <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b flex items-center gap-2">
              <div className="w-1 h-5 bg-green-500 rounded"/>
              <h2 className="font-bold text-gray-800">Leads Récemment Collectés</h2>
              <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">{recentLeads.length}</span>
            </div>

            {recentLeads.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-14 text-gray-400">
                <Building2 size={28} className="mb-2 opacity-20"/>
                <p className="text-sm">Aucun lead collecté par scraping pour le moment</p>
                <p className="text-xs mt-1">Les leads importés via CSV ou scraping apparaîtront ici</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-xs text-gray-500 font-semibold uppercase tracking-wide">
                      <th className="px-4 py-3 text-left">Entreprise</th>
                      <th className="px-4 py-3 text-left">Secteur</th>
                      <th className="px-4 py-3 text-left">Région</th>
                      <th className="px-4 py-3 text-left">Email</th>
                      <th className="px-4 py-3 text-left">Segment</th>
                      <th className="px-4 py-3 text-left">Score</th>
                      <th className="px-4 py-3 text-left">Collecté le</th>
                      <th className="px-4 py-3 text-left"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {recentLeads.map(lead => (
                      <tr key={lead.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-semibold text-gray-900">{lead.company}</td>
                        <td className="px-4 py-3 text-gray-500 text-xs">{lead.sector || '—'}</td>
                        <td className="px-4 py-3 text-gray-500 text-xs">
                          {lead.region ? <span className="flex items-center gap-1"><MapPin size={10}/>{lead.region}</span> : '—'}
                        </td>
                        <td className="px-4 py-3 text-gray-500 text-xs">{lead.email || '—'}</td>
                        <td className="px-4 py-3">
                          {lead.segment ? (
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEGMENT_COLORS[lead.segment] || 'bg-gray-100 text-gray-600'}`}>
                              {lead.segment}
                            </span>
                          ) : '—'}
                        </td>
                        <td className="px-4 py-3">
                          {lead.score != null ? (
                            <span className={`text-xs font-bold ${lead.score >= 70 ? 'text-green-600' : lead.score >= 40 ? 'text-orange-500' : 'text-gray-400'}`}>
                              {Math.round(lead.score)}
                            </span>
                          ) : '—'}
                        </td>
                        <td className="px-4 py-3 text-gray-400 text-xs">
                          {lead.created_at ? new Date(lead.created_at).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'}
                        </td>
                        <td className="px-4 py-3">
                          <button
                            onClick={() => deleteLead(lead.id)}
                            disabled={deletingId === lead.id}
                            className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors disabled:opacity-40"
                            title="Supprimer ce lead"
                          >
                            <Trash2 size={14}/>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  )
}
