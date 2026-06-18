import { useEffect, useState } from 'react'
import Sidebar from '../components/Navbar'
import axios from 'axios'
import {
  Plus, Trash2, AlertTriangle, TrendingUp,
  DollarSign, Target, X, ChevronRight, RefreshCw,
  GripVertical, CheckCircle
} from 'lucide-react'

const API = axios.create({ baseURL: 'http://127.0.0.1:8000' })
API.interceptors.request.use(c => {
  const t = localStorage.getItem('token')
  if (t) c.headers.Authorization = `Bearer ${t}`
  return c
})

const STAGES = ['Prospection', 'Qualification', 'Proposition', 'Négociation', 'Gagné']

const STAGE_COLORS: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  'Prospection':  { bg: 'bg-gray-50',   border: 'border-gray-200',  text: 'text-gray-600',   dot: 'bg-gray-400'   },
  'Qualification':{ bg: 'bg-blue-50',   border: 'border-blue-200',  text: 'text-blue-600',   dot: 'bg-blue-500'   },
  'Proposition':  { bg: 'bg-violet-50', border: 'border-violet-200',text: 'text-violet-600', dot: 'bg-violet-500' },
  'Négociation':  { bg: 'bg-orange-50', border: 'border-orange-200',text: 'text-orange-600', dot: 'bg-orange-500' },
  'Gagné':        { bg: 'bg-green-50',  border: 'border-green-200', text: 'text-green-600',  dot: 'bg-green-500'  },
}

const PROB_BY_STAGE: Record<string, number> = {
  'Prospection': 20, 'Qualification': 40, 'Proposition': 60, 'Négociation': 80, 'Gagné': 100
}

function fmt(n: number) {
  if (n >= 1000000) return `${(n/1000000).toFixed(1)}M`
  if (n >= 1000)    return `${(n/1000).toFixed(0)}k`
  return n.toString()
}

export default function Ventes() {
  const [deals, setDeals]         = useState<any[]>([])
  const [stats, setStats]         = useState<any>(null)
  const [loading, setLoading]     = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [dragId, setDragId]       = useState<number | null>(null)
  const [dragOver, setDragOver]   = useState<string | null>(null)
  const [selected, setSelected]   = useState<any | null>(null)
  const [form, setForm]           = useState({
    title: '', company: '', value: '', stage: 'Prospection',
    probability: 20, risk: false, notes: ''
  })

  const fetchAll = async () => {
    setLoading(true)
    const [d, s] = await Promise.all([
      API.get('/opportunities/').catch(() => ({ data: [] })),
      API.get('/opportunities/stats/summary').catch(() => ({ data: null })),
    ])
    setDeals(d.data)
    setStats(s.data)
    setLoading(false)
  }

  useEffect(() => { fetchAll() }, [])

  const createDeal = async () => {
    if (!form.title) return
    await API.post('/opportunities/', {
      ...form, value: parseFloat(form.value) || 0
    })
    setShowModal(false)
    setForm({ title: '', company: '', value: '', stage: 'Prospection', probability: 20, risk: false, notes: '' })
    fetchAll()
  }

  const deleteDeal = async (id: number) => {
    await API.delete(`/opportunities/${id}`)
    setDeals(deals.filter(d => d.id !== id))
    if (selected?.id === id) setSelected(null)
    fetchAll()
  }

  const moveStage = async (id: number, newStage: string) => {
    await API.patch(`/opportunities/${id}`, {
      stage: newStage, probability: PROB_BY_STAGE[newStage] ?? 50
    })
    setDeals(deals.map(d => d.id === id ? { ...d, stage: newStage, probability: PROB_BY_STAGE[newStage] } : d))
  }

  const toggleRisk = async (id: number, risk: boolean) => {
    await API.patch(`/opportunities/${id}`, { risk })
    setDeals(deals.map(d => d.id === id ? { ...d, risk } : d))
  }

  // Drag & Drop
  const onDragStart = (id: number) => setDragId(id)
  const onDrop = (stage: string) => {
    if (dragId !== null && dragOver !== null) moveStage(dragId, stage)
    setDragId(null); setDragOver(null)
  }

  const dealsInStage = (stage: string) => deals.filter(d => d.stage === stage)

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />

      {/* Modal nouveau deal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md animate-scale-in">
            <div className="flex justify-between items-center px-6 py-4 border-b border-gray-100">
              <h2 className="font-bold text-gray-900">Nouveau Deal</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={18} />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-widest mb-1.5">Nom du deal *</label>
                <input className="input" placeholder="Ex: Contrat annuel TechCorp"
                  value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-widest mb-1.5">Entreprise</label>
                  <input className="input" placeholder="TechCorp SAS"
                    value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-widest mb-1.5">Valeur (TND)</label>
                  <input type="number" className="input" placeholder="50000"
                    value={form.value} onChange={e => setForm({ ...form, value: e.target.value })} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-widest mb-1.5">Étape</label>
                  <select className="input" value={form.stage}
                    onChange={e => setForm({ ...form, stage: e.target.value, probability: PROB_BY_STAGE[e.target.value] ?? 20 })}>
                    {STAGES.map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-widest mb-1.5">Probabilité</label>
                  <div className="flex items-center gap-2">
                    <input type="range" min={0} max={100} value={form.probability}
                      onChange={e => setForm({ ...form, probability: Number(e.target.value) })}
                      className="flex-1 accent-blue-600" />
                    <span className="text-sm font-bold text-blue-600 w-10">{form.probability}%</span>
                  </div>
                </div>
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-widest mb-1.5">Notes</label>
                <textarea className="input h-20 resize-none" placeholder="Contexte, prochaines étapes..."
                  value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} />
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.risk}
                  onChange={e => setForm({ ...form, risk: e.target.checked })}
                  className="w-4 h-4 accent-red-500" />
                <span className="text-sm text-gray-600">Marquer comme deal à risque</span>
              </label>
            </div>
            <div className="px-6 pb-5 flex gap-3">
              <button onClick={() => setShowModal(false)} className="btn btn-secondary flex-1 justify-center">Annuler</button>
              <button onClick={createDeal} disabled={!form.title} className="btn btn-primary flex-1 justify-center disabled:opacity-40">
                <Plus size={15} /> Créer le deal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Detail panel */}
      {selected && (
        <div className="fixed right-0 top-0 h-full w-80 bg-white shadow-2xl z-40 border-l border-gray-100 flex flex-col animate-fade-in">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <h3 className="font-bold text-gray-900 truncate">{selected.title}</h3>
            <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600"><X size={16} /></button>
          </div>
          <div className="flex-1 overflow-auto p-5 space-y-4">
            <div>
              <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Entreprise</p>
              <p className="text-sm font-medium text-gray-800">{selected.company || '—'}</p>
            </div>
            <div>
              <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Valeur</p>
              <p className="text-2xl font-extrabold text-blue-600">{(selected.value || 0).toLocaleString('fr')} TND</p>
            </div>
            <div>
              <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Étape</p>
              <div className="flex gap-1 flex-wrap mt-1">
                {STAGES.map(s => (
                  <button key={s} onClick={() => { moveStage(selected.id, s); setSelected({ ...selected, stage: s }) }}
                    className={`text-xs px-2.5 py-1 rounded-full font-semibold border transition-all ${
                      selected.stage === s
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'border-gray-200 text-gray-500 hover:border-blue-300'
                    }`}>{s}</button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest mb-2">Probabilité</p>
              <div className="flex items-center gap-3">
                <div className="flex-1 bg-gray-100 rounded-full h-2">
                  <div className="h-2 rounded-full bg-blue-500 transition-all" style={{ width: `${selected.probability}%` }} />
                </div>
                <span className="text-sm font-bold text-blue-600">{selected.probability}%</span>
              </div>
            </div>
            {selected.notes && (
              <div>
                <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Notes</p>
                <p className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">{selected.notes}</p>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Deal à risque</span>
              <button onClick={() => { toggleRisk(selected.id, !selected.risk); setSelected({ ...selected, risk: !selected.risk }) }}
                className={`w-10 h-5 rounded-full transition-colors ${selected.risk ? 'bg-red-500' : 'bg-gray-200'}`}>
                <div className={`w-4 h-4 bg-white rounded-full shadow transition-transform mx-0.5 ${selected.risk ? 'translate-x-5' : 'translate-x-0'}`} />
              </button>
            </div>
          </div>
          <div className="p-4 border-t border-gray-100">
            <button onClick={() => deleteDeal(selected.id)}
              className="btn w-full justify-center text-red-500 border border-red-200 hover:bg-red-50">
              <Trash2 size={14} /> Supprimer le deal
            </button>
          </div>
        </div>
      )}

      <div className="ml-56 flex-1 overflow-auto min-w-0">
        {/* Header */}
        <header className="sticky top-0 z-20 bg-white/80 backdrop-blur-md border-b border-gray-100 px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-gray-900">Pipeline Commercial</h1>
              <p className="text-[12px] text-gray-400 mt-0.5">Gérez vos opportunités en temps réel</p>
            </div>
            <div className="flex items-center gap-6">
              {[
                { val: `${fmt(stats?.pipeline ?? 0)} TND`, label: 'Pipeline', color: 'text-gray-900' },
                { val: `${fmt(stats?.forecast ?? 0)} TND`, label: 'Prévision IA', color: 'text-blue-600' },
                { val: stats?.total ?? 0, label: 'Deals actifs', color: 'text-gray-900' },
                { val: stats?.at_risk ?? 0, label: 'À risque', color: 'text-red-500' },
              ].map(({ val, label, color }) => (
                <div key={label} className="text-center">
                  <p className={`text-xl font-extrabold tabular-nums ${color}`}>{val}</p>
                  <p className="text-[11px] text-gray-400 font-medium">{label}</p>
                </div>
              ))}
              <button onClick={fetchAll} className="btn btn-secondary text-xs">
                <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
              </button>
              <button onClick={() => setShowModal(true)} className="btn btn-primary">
                <Plus size={15} /> Nouveau Deal
              </button>
            </div>
          </div>
        </header>

        <div className="p-8 space-y-6">

          {/* Alertes à risque */}
          {deals.filter(d => d.risk).length > 0 && (
            <div className="card p-4 border-red-100 bg-red-50/50 animate-fade-up">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={15} className="text-red-500" />
                <h2 className="font-bold text-red-600 text-sm">Deals à risque — Action requise</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {deals.filter(d => d.risk).map(d => (
                  <button key={d.id} onClick={() => setSelected(d)}
                    className="flex items-center gap-2 bg-white border border-red-200 text-red-700 px-3 py-1.5 rounded-lg text-xs font-semibold hover:bg-red-50 transition-colors">
                    <span>{d.title}</span>
                    <span className="text-red-400">· {(d.value || 0).toLocaleString('fr')} TND</span>
                    <ChevronRight size={12} />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Kanban */}
          <div className="grid grid-cols-5 gap-4">
            {STAGES.map(stage => {
              const sc = STAGE_COLORS[stage]
              const stagDeals = dealsInStage(stage)
              const stageTotal = stagDeals.reduce((s, d) => s + (d.value || 0), 0)
              return (
                <div key={stage}
                  onDragOver={e => { e.preventDefault(); setDragOver(stage) }}
                  onDrop={() => onDrop(stage)}
                  onDragLeave={() => setDragOver(null)}
                  className={`rounded-2xl border-2 transition-all min-h-[400px] flex flex-col ${
                    dragOver === stage ? 'border-blue-400 bg-blue-50/50 scale-[1.01]' : `${sc.border} ${sc.bg}`
                  }`}>
                  <div className="px-4 py-3 border-b border-inherit">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${sc.dot}`} />
                        <span className={`text-xs font-bold uppercase tracking-wide ${sc.text}`}>{stage}</span>
                      </div>
                      <span className={`text-xs font-bold px-1.5 py-0.5 rounded-full bg-white/80 ${sc.text}`}>
                        {stagDeals.length}
                      </span>
                    </div>
                    {stageTotal > 0 && (
                      <p className="text-[11px] text-gray-400 font-medium">{fmt(stageTotal)} TND</p>
                    )}
                  </div>

                  <div className="flex-1 p-3 space-y-2 overflow-y-auto">
                    {stagDeals.length === 0 ? (
                      <div className="flex items-center justify-center h-24 border-2 border-dashed border-gray-200 rounded-xl">
                        <p className="text-[11px] text-gray-300">Glisser ici</p>
                      </div>
                    ) : stagDeals.map(deal => (
                      <div key={deal.id}
                        draggable
                        onDragStart={() => onDragStart(deal.id)}
                        onClick={() => setSelected(deal)}
                        className={`bg-white rounded-xl border p-3 cursor-pointer hover:shadow-md transition-all group ${
                          deal.risk ? 'border-red-200' : 'border-gray-100'
                        } ${dragId === deal.id ? 'opacity-40 scale-95' : ''}`}>
                        <div className="flex items-start justify-between gap-1 mb-2">
                          <p className="font-semibold text-[13px] text-gray-900 leading-tight">{deal.title}</p>
                          <GripVertical size={12} className="text-gray-300 flex-shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>
                        {deal.company && (
                          <p className="text-[11px] text-gray-400 mb-2 truncate">{deal.company}</p>
                        )}
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-bold text-blue-600">{fmt(deal.value || 0)} TND</span>
                          {deal.risk && <AlertTriangle size={12} className="text-red-400" />}
                          {deal.stage === 'Gagné' && <CheckCircle size={12} className="text-green-500" />}
                        </div>
                        <div className="mt-2 bg-gray-100 rounded-full h-1">
                          <div className="h-1 rounded-full bg-blue-400 transition-all" style={{ width: `${deal.probability}%` }} />
                        </div>
                        <p className="text-[10px] text-gray-400 mt-1">{deal.probability}% probabilité</p>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Table tous les deals */}
          {deals.length > 0 && (
            <div className="card overflow-hidden animate-fade-up">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3">
                <Target size={16} className="text-gray-400" />
                <h2 className="font-bold text-gray-900 text-[15px]">Tous les deals</h2>
                <span className="badge badge-gray">{deals.length}</span>
              </div>
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50/80 border-b border-gray-100">
                    {['Deal', 'Entreprise', 'Valeur', 'Étape', 'Probabilité', 'Statut', ''].map(h => (
                      <th key={h} className="px-5 py-3 text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {deals.map(d => {
                    const sc = STAGE_COLORS[d.stage] || STAGE_COLORS['Prospection']
                    return (
                      <tr key={d.id} onClick={() => setSelected(d)} className="table-row-hover cursor-pointer">
                        <td className="px-5 py-3.5 font-semibold text-[13px] text-gray-900">{d.title}</td>
                        <td className="px-5 py-3.5 text-[12px] text-gray-500">{d.company || '—'}</td>
                        <td className="px-5 py-3.5 font-bold text-blue-600 text-[13px]">{(d.value || 0).toLocaleString('fr')} TND</td>
                        <td className="px-5 py-3.5">
                          <span className={`inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-full ${sc.bg} ${sc.text} border ${sc.border}`}>
                            <div className={`w-1.5 h-1.5 rounded-full ${sc.dot}`} />
                            {d.stage}
                          </span>
                        </td>
                        <td className="px-5 py-3.5">
                          <div className="flex items-center gap-2">
                            <div className="w-16 bg-gray-100 rounded-full h-1.5">
                              <div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${d.probability}%` }} />
                            </div>
                            <span className="text-xs text-gray-500">{d.probability}%</span>
                          </div>
                        </td>
                        <td className="px-5 py-3.5">
                          {d.risk
                            ? <span className="badge bg-red-50 text-red-600 border-red-100 border">À risque</span>
                            : <span className="badge bg-green-50 text-green-600 border-green-100 border">OK</span>
                          }
                        </td>
                        <td className="px-5 py-3.5">
                          <button onClick={e => { e.stopPropagation(); deleteDeal(d.id) }}
                            className="p-1.5 rounded-lg text-gray-300 hover:text-red-400 hover:bg-red-50 transition-colors">
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}
