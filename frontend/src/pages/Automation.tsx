import { useEffect, useState } from 'react'
import Sidebar from '../components/Navbar'
import axios from 'axios'
import {
  Plus, Zap, Play, Pause, Trash2, X, CheckCircle,
  Mail, Users, TrendingUp, Clock, RefreshCw, Activity
} from 'lucide-react'

const API = axios.create({ baseURL: (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000') })
API.interceptors.request.use(c => {
  const t = localStorage.getItem('token')
  if (t) c.headers.Authorization = `Bearer ${t}`
  return c
})

const TRIGGERS = [
  { id: 'new_lead',    label: 'Nouveau lead',      desc: 'Quand un lead est ajouté',         icon: Users  },
  { id: 'score_high',  label: 'Score élevé',        desc: 'Score IA ≥ 70 (lead chaud)',       icon: TrendingUp },
  { id: 'no_email',    label: 'Sans réponse',        desc: 'Après 7 jours sans réponse',       icon: Clock  },
  { id: 'deal_won',    label: 'Deal gagné',          desc: 'Quand un deal passe à "Gagné"',    icon: CheckCircle },
]

const TRIGGER_LABELS: Record<string, string> = {
  new_lead: 'Nouveau lead', score_high: 'Score élevé',
  no_email: 'Sans réponse', deal_won: 'Deal gagné', manual: 'Manuel'
}

export default function Automation() {
  const [workflows, setWorkflows] = useState<any[]>([])
  const [stats, setStats]         = useState<any>(null)
  const [loading, setLoading]     = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [executing, setExecuting]   = useState<number | null>(null)
  const [execResult, setExecResult] = useState<{ id: number; msg: string } | null>(null)
  const [sentEmails, setSentEmails] = useState<any[]>([])
  const [showEmails, setShowEmails] = useState(false)
  const [selectedEmail, setSelectedEmail] = useState<any | null>(null)
  const [trigger, setTrigger]     = useState('')
  const [form, setForm]           = useState({ name: '', description: '' })

  const fetchAll = async () => {
    setLoading(true)
    const [wf, st] = await Promise.all([
      API.get('/workflows/').catch(() => ({ data: [] })),
      API.get('/workflows/stats/summary').catch(() => ({ data: null })),
    ])
    setWorkflows(wf.data)
    setStats(st.data)
    setLoading(false)
  }

  const openSentEmails = async (id: number) => {
    const r = await API.get(`/workflows/${id}/sent-emails`).catch(() => ({ data: [] }))
    setSentEmails(r.data || [])
    setSelectedEmail(r.data?.[0] || null)
    setShowEmails(true)
  }

  useEffect(() => { fetchAll() }, [])

  const createWorkflow = async () => {
    if (!form.name) return
    await API.post('/workflows/', {
      name: form.name, trigger: trigger || 'manual',
      description: form.description || `Workflow déclenché par : ${TRIGGER_LABELS[trigger] || 'Manuel'}`,
      actions: 'email',
    })
    setShowModal(false)
    setForm({ name: '', description: '' })
    setTrigger('')
    setExecResult({ id: -1, msg: 'Workflow créé en pause — activez-le (▶) puis lancez-le quand vous le souhaitez.' })
    fetchAll()
  }

  const toggleStatus = async (wf: any) => {
    const newStatus = wf.status === 'active' ? 'paused' : 'active'
    await API.patch(`/workflows/${wf.id}`, { status: newStatus })
    setWorkflows(workflows.map(w => w.id === wf.id ? { ...w, status: newStatus } : w))
  }

  const executeWorkflow = async (id: number) => {
    setExecuting(id)
    setExecResult(null)
    setSentEmails([])
    try {
      const res = await API.post(`/workflows/${id}/execute`)
      setExecResult({ id, msg: res.data.message })
      // Attendre que les emails soient envoyés puis les afficher
      // Polling toutes les 15s jusqu'à trouver des emails (max 5 min)
      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        const r = await API.get(`/workflows/${id}/sent-emails`).catch(() => ({ data: [] }))
        if (r.data?.length > 0) {
          setSentEmails(r.data)
          setShowEmails(true)
          setExecuting(null)
          fetchAll()
          clearInterval(poll)
        } else if (attempts >= 20) {
          setExecuting(null)
          fetchAll()
          clearInterval(poll)
        }
      }, 15000)
    } catch (e: any) {
      setExecResult({ id, msg: e.response?.data?.detail || 'Erreur lors de l\'exécution' })
      setExecuting(null)
    }
  }

  const deleteWorkflow = async (id: number) => {
    await API.delete(`/workflows/${id}`)
    setWorkflows(workflows.filter(w => w.id !== id))
    fetchAll()
  }

  return (
    <div className="flex h-screen bg-[var(--bg)]">
      <Sidebar />

      {/* Panel emails envoyés */}
      {showEmails && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col animate-scale-in">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <div>
                <h2 className="font-bold text-gray-900">Emails envoyés</h2>
                <p className="text-xs text-gray-400 mt-0.5">{sentEmails.length} email(s) générés et envoyés</p>
              </div>
              <button onClick={() => { setShowEmails(false); setSelectedEmail(null) }}
                className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>

            <div className="flex flex-1 overflow-hidden">
              {/* Liste */}
              <div className="w-64 border-r border-gray-100 overflow-y-auto">
                {sentEmails.map(e => (
                  <div key={e.id} onClick={() => setSelectedEmail(e)}
                    className={`px-4 py-3 cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors ${
                      selectedEmail?.id === e.id ? 'bg-blue-50 border-l-2 border-l-[var(--nova-500)]' : ''
                    }`}>
                    <p className="font-semibold text-[13px] text-gray-900 truncate">{e.company}</p>
                    <p className="text-[11px] text-blue-500 truncate">{e.email}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] bg-green-100 text-green-600 px-1.5 py-0.5 rounded font-semibold">Envoyé</span>
                      {e.segment && <span className="text-[10px] text-gray-400">{e.segment}</span>}
                    </div>
                  </div>
                ))}
              </div>

              {/* Contenu email */}
              <div className="flex-1 overflow-y-auto p-5">
                {selectedEmail ? (
                  <div>
                    <div className="mb-4">
                      <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Destinataire</p>
                      <p className="font-bold text-gray-900">{selectedEmail.company}</p>
                      <p className="text-sm text-blue-500">{selectedEmail.email}</p>
                      {selectedEmail.score && (
                        <p className="text-xs text-gray-400 mt-0.5">Score IA : {selectedEmail.score}/100</p>
                      )}
                    </div>
                    <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 mb-3">
                      <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-widest mb-1">Objet</p>
                      <p className="font-semibold text-gray-900 text-sm">{selectedEmail.subject}</p>
                    </div>
                    <div className="bg-gray-50 border border-gray-100 rounded-xl p-4">
                      <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-widest mb-2">Corps</p>
                      <pre className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed font-sans">
                        {selectedEmail.body}
                      </pre>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-300 flex-col gap-2">
                    <Mail size={32} />
                    <p className="text-sm">Sélectionne un email pour le voir</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg animate-scale-in">
            <div className="flex justify-between items-center px-6 py-4 border-b border-gray-100">
              <div>
                <h2 className="font-bold text-gray-900">Nouveau Workflow</h2>
                <p className="text-xs text-gray-400 mt-0.5">Automatisez vos actions commerciales</p>
              </div>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>
            <div className="p-6 space-y-5">
              <div>
                <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-widest mb-1.5">Nom du workflow *</label>
                <input className="input" placeholder="Ex: Relance leads chauds"
                  value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-widest mb-2">Déclencheur</label>
                <div className="grid grid-cols-2 gap-2">
                  {TRIGGERS.map(t => {
                    const Icon = t.icon
                    return (
                      <div key={t.id} onClick={() => setTrigger(t.id)}
                        className={`rounded-xl p-3 cursor-pointer border transition-all ${
                          trigger === t.id
                            ? 'border-[var(--nova-500)] bg-blue-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}>
                        <div className="flex items-center gap-2 mb-1">
                          <Icon size={14} className={trigger === t.id ? 'text-blue-500' : 'text-gray-400'} />
                          <p className={`text-[13px] font-semibold ${trigger === t.id ? 'text-blue-700' : 'text-gray-700'}`}>{t.label}</p>
                        </div>
                        <p className="text-[11px] text-gray-400 ml-5">{t.desc}</p>
                      </div>
                    )
                  })}
                </div>
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-widest mb-2">Action — Envoyer un email</label>
                <div className="border border-gray-200 rounded-xl p-4 bg-gray-50 flex items-center gap-3">
                  <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                    <Mail size={14} className="text-blue-600" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-800">Email automatique IA</p>
                  </div>
                  <CheckCircle size={16} className="ml-auto text-green-500" />
                </div>
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-widest mb-1.5">Description (optionnel)</label>
                <input className="input" placeholder="Décrivez ce workflow..."
                  value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
              </div>
            </div>
            <div className="px-6 pb-5 flex gap-3">
              <button onClick={() => setShowModal(false)} className="btn btn-secondary flex-1 justify-center">Annuler</button>
              <button onClick={createWorkflow} disabled={!form.name}
                className="btn btn-primary flex-1 justify-center disabled:opacity-40">
                <Zap size={14} /> Créer le workflow
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="ml-[var(--sidebar-w)] flex-1 transition-[margin-left] duration-200 overflow-auto min-w-0">
        {/* Header */}
        <header className="sticky top-0 z-20 bg-white/80 backdrop-blur-md border-b border-gray-100 px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-extrabold text-gray-900 font-display tracking-tight">Automation</h1>
              <p className="text-[12px] text-gray-400 mt-0.5">Workflows intelligents pour automatiser la prospection</p>
            </div>
            <div className="flex items-center gap-6">
              {[
                { val: stats?.active ?? 0,      label: 'Actifs',       color: 'text-green-600' },
                { val: stats?.executions ?? 0,   label: 'Exécutions',   color: 'text-gray-900'  },
                { val: stats?.emails_sent ?? 0,  label: 'Emails auto',  color: 'text-blue-600'  },
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
                <Plus size={15} /> Nouveau Workflow
              </button>
            </div>
          </div>
        </header>

        <div className="p-8 space-y-6">

          {/* Résultat exécution */}
          {execResult && (
            <div className="flex items-center gap-3 px-5 py-3.5 rounded-xl border bg-green-50 border-green-200 text-green-800 text-sm animate-fade-up">
              <CheckCircle size={15} className="flex-shrink-0" />
              <span className="font-medium">{execResult.msg}</span>
              <button onClick={() => setExecResult(null)} className="ml-auto opacity-50 hover:opacity-100">
                <X size={14} />
              </button>
            </div>
          )}

          {workflows.length === 0 ? (
            <div className="card flex flex-col items-center py-20 text-gray-300">
              <Zap size={48} className="mb-4" />
              <p className="text-base font-semibold text-gray-400">Aucun workflow créé</p>
              <p className="text-sm text-gray-300 mt-1 mb-6">Automatisez votre prospection en quelques clics</p>
              <button onClick={() => setShowModal(true)} className="btn btn-primary">
                <Plus size={15} /> Créer mon premier workflow
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {workflows.map(wf => (
                <div key={wf.id} className="card p-5 animate-fade-up">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-4 flex-1 min-w-0">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                        wf.status === 'active' ? 'bg-green-50' : 'bg-gray-100'
                      }`}>
                        <Zap size={18} className={wf.status === 'active' ? 'text-green-500' : 'text-gray-400'} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-bold text-gray-900 text-[15px]">{wf.name}</h3>
                          <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                            wf.status === 'active'
                              ? 'bg-green-100 text-green-600'
                              : 'bg-gray-100 text-gray-500'
                          }`}>
                            {wf.status === 'active' ? 'Actif' : 'En pause'}
                          </span>
                        </div>
                        {wf.description && (
                          <p className="text-[12px] text-gray-400 mb-3">{wf.description}</p>
                        )}
                        {/* Flow visuel */}
                        <div className="flex items-center gap-2 flex-wrap">
                          <div className="flex items-center gap-1.5 bg-blue-50 border border-blue-100 text-blue-700 px-3 py-1.5 rounded-lg text-xs font-semibold">
                            <Activity size={11} />
                            {TRIGGER_LABELS[wf.trigger] || wf.trigger}
                          </div>
                          <div className="text-gray-300 text-xs"> </div>
                          <div className="flex items-center gap-1.5 bg-violet-50 border border-violet-100 text-violet-700 px-3 py-1.5 rounded-lg text-xs font-semibold">
                            <Mail size={11} /> Email IA
                          </div>
                          <div className="text-gray-300 text-xs"> </div>
                          <div className="flex items-center gap-1.5 bg-green-50 border border-green-100 text-green-700 px-3 py-1.5 rounded-lg text-xs font-semibold">
                            <CheckCircle size={11} /> Suivi CRM
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Stats + Actions */}
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <div className="flex gap-4 bg-gray-50 rounded-xl px-4 py-2">
                        <div className="text-center">
                          <p className="text-base font-extrabold text-gray-900">{wf.executions}</p>
                          <p className="text-[10px] text-gray-400">exéc.</p>
                        </div>
                        <div className="w-px bg-gray-200" />
                        <div className="text-center">
                          <p className="text-base font-extrabold text-blue-600">{wf.emails_sent}</p>
                          <p className="text-[10px] text-gray-400">emails</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {(wf.emails_sent ?? 0) > 0 && (
                          <button onClick={() => openSentEmails(wf.id)}
                            className="btn btn-secondary text-xs px-3 py-2 border-blue-200 text-blue-600 hover:bg-[var(--nova-50)]">
                            <Mail size={13} /> Voir emails
                          </button>
                        )}
                        <button onClick={() => executeWorkflow(wf.id)}
                          disabled={executing === wf.id || wf.status !== 'active'}
                          className="btn btn-secondary text-xs disabled:opacity-40 px-3 py-2">
                          {executing === wf.id
                            ? <RefreshCw size={13} className="animate-spin" />
                            : <Play size={13} />
                          }
                          Exécuter
                        </button>
                        <button onClick={() => toggleStatus(wf)}
                          className={`p-2 rounded-lg transition-colors border ${
                            wf.status === 'active'
                              ? 'border-orange-200 text-orange-500 hover:bg-orange-50'
                              : 'border-green-200 text-green-500 hover:bg-green-50'
                          }`}>
                          {wf.status === 'active' ? <Pause size={14} /> : <Play size={14} />}
                        </button>
                        <button onClick={() => deleteWorkflow(wf.id)}
                          className="p-2 rounded-lg border border-gray-200 text-gray-400 hover:text-red-400 hover:bg-red-50 hover:border-red-200 transition-colors">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Templates suggérés */}
          <div className="card p-6">
            <h2 className="font-bold text-gray-900 text-[15px] mb-1">Templates recommandés</h2>
            <p className="text-[12px] text-gray-400 mb-4">Workflows prêts à l'emploi pour votre prospection B2B</p>
            <div className="grid grid-cols-2 gap-3">
              {[
                { name: 'Bienvenue nouveaux leads',  trigger: 'new_lead',   desc: 'Email de bienvenue dès qu\'un lead est ajouté' },
                { name: 'Relance leads chauds',      trigger: 'score_high', desc: 'Contactez automatiquement les leads avec score ≥ 70' },
                { name: 'Suivi après 7 jours',       trigger: 'no_email',   desc: 'Relance si pas de réponse après une semaine' },
              ].map(t => (
                <div key={t.name} className="border border-gray-100 rounded-xl p-4 hover:border-[var(--nova-200)] hover:bg-[var(--nova-50)]/30 transition-all group">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <p className="font-semibold text-[13px] text-gray-800 mb-1">{t.name}</p>
                      <p className="text-[11px] text-gray-400">{t.desc}</p>
                    </div>
                    <button
                      onClick={async () => {
                        await API.post('/workflows/', { name: t.name, trigger: t.trigger, description: t.desc, actions: 'email' })
                        fetchAll()
                      }}
                      className="text-[11px] font-semibold text-blue-600 border border-blue-200 px-2.5 py-1 rounded-lg hover:bg-[var(--nova-600)] hover:text-white transition-all flex-shrink-0 opacity-0 group-hover:opacity-100">
                      + Ajouter
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}

