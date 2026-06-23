import { useEffect, useState } from 'react'
import Sidebar from '../components/Navbar'
import { getLeadStats } from '../services/api'
import axios from 'axios'
import {
  Mail, Play, CheckCircle, Clock, AlertCircle,
  ChevronDown, ChevronUp, ChevronLeft, ChevronRight,
  Search, Send, Target, Users, Trash2, Calendar,
  RefreshCw, Trophy, Zap, RotateCcw, X, Sparkles,
  ArrowRight, Filter, Eye, Brain, TrendingUp
} from 'lucide-react'

const API = axios.create({ baseURL: (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000') })
API.interceptors.request.use(c => {
  const t = localStorage.getItem('token')
  if (t) c.headers.Authorization = `Bearer ${t}`
  return c
})

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; dot: string }> = {
  draft:    { label: 'Brouillon', color: 'text-gray-600',   bg: 'bg-gray-100',   dot: 'bg-gray-400'   },
  sending:  { label: 'En cours',  color: 'text-blue-600',   bg: 'bg-blue-50',    dot: 'bg-blue-500'   },
  sent:     { label: 'Envoyée',   color: 'text-green-600',  bg: 'bg-green-50',   dot: 'bg-green-500'  },
  scheduled:{ label: 'Planifiée', color: 'text-violet-600', bg: 'bg-violet-50',  dot: 'bg-violet-500' },
  failed:   { label: 'Échouée',   color: 'text-red-600',    bg: 'bg-red-50',     dot: 'bg-red-500'    },
}

const SEG_COLORS: Record<string, string> = {
  'Chaud': 'bg-red-50 text-red-600 border-red-100',
  'Prêts à Acheter': 'bg-orange-50 text-orange-600 border-orange-100',
  'Froid': 'bg-blue-50 text-blue-600 border-blue-100',
  'À Risque': 'bg-amber-50 text-amber-600 border-amber-100',
}

function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-widest mb-1.5">
      {children}{required && <span className="text-red-400 ml-1">*</span>}
    </label>
  )
}

function SectionCard({ color, title, children, badge }: {
  color: string; title: string; children: React.ReactNode; badge?: string
}) {
  return (
    <div className="card p-6">
      <div className="flex items-center gap-3 mb-5">
        <div className={`w-1 h-6 rounded-full ${color}`} />
        <h2 className="font-bold text-gray-900 text-[15px]">{title}</h2>
        {badge && (
          <span className="ml-auto text-[11px] font-semibold bg-gray-100 text-gray-500 px-2.5 py-1 rounded-full">
            {badge}
          </span>
        )}
      </div>
      {children}
    </div>
  )
}

function EmailHtmlPreview({ subject, body, cta }: { subject?: string; body: string; cta?: string }) {
  // Découpe le corps en paragraphes (sépare sur les sauts de ligne)
  const rawParas = (body || '').split(/\n\s*\n|\n/).map(p => p.trim()).filter(Boolean)
  // Si un CTA est fourni, on retire la ligne du corps qui le contient pour l'afficher en bouton
  const ctaKey = cta ? cta.toLowerCase().slice(0, 12) : ''
  const paragraphs = ctaKey
    ? rawParas.filter(p => !p.toLowerCase().includes(ctaKey))
    : rawParas

  return (
    <div className="rounded-xl overflow-hidden border border-gray-200 bg-white shadow-sm">
      {/* Bandeau header */}
      <div className="bg-gradient-to-r from-indigo-600 to-violet-600 px-6 py-4 flex items-center gap-2">
        <div className="w-7 h-7 rounded-lg bg-white/20 flex items-center justify-center">
          <Mail size={15} className="text-white" />
        </div>
        <span className="text-white font-bold text-sm tracking-wide">LeadPilot</span>
      </div>

      {/* Objet */}
      {subject && (
        <div className="px-6 pt-5">
          <h3 className="text-[15px] font-bold text-gray-900 leading-snug">{subject}</h3>
        </div>
      )}

      {/* Corps */}
      <div className="px-6 py-4 space-y-3">
        {paragraphs.map((p, i) => (
          <p key={i} className="text-[13px] text-gray-700 leading-relaxed whitespace-pre-line">{p}</p>
        ))}
        {cta && (
          <div className="pt-1">
            <span className="inline-flex items-center gap-1.5 bg-indigo-600 text-white text-[13px] font-semibold px-5 py-2.5 rounded-lg shadow-sm">
              {cta} <ArrowRight size={14} />
            </span>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="bg-gray-50 border-t border-gray-100 px-6 py-3 text-center">
        <p className="text-[10px] text-gray-400">Envoyé par LeadPilot · Prospection B2B</p>
        <p className="text-[10px] text-gray-300 mt-0.5">Se désabonner</p>
      </div>
    </div>
  )
}

export default function Campaigns() {
  const [emailStats, setEmailStats] = useState<any>(null)
  const [abStats, setAbStats]       = useState<any>(null)
  const [abWinner, setAbWinner]     = useState<any>(null)
  const [history, setHistory]       = useState<any[]>([])
  const [loading, setLoading]       = useState(true)
  const [launching, setLaunching]   = useState(false)
  const [result, setResult]         = useState<{ type: 'success' | 'error'; msg: string } | null>(null)

  const [form, setForm] = useState({
    campaign_name: '', subject: '', cta: '', ctaLink: '',
    tone: 'professionnel', segment: '', sector: '',
    region: '', dailyLimit: 50, manualName: '', manualEmail: '',
  })

  const [companySearch, setCompanySearch]         = useState('')
  const [companySuggestions, setCompanySuggestions] = useState<any[]>([])
  const [selectedCompanies, setSelectedCompanies]   = useState<any[]>([])

  const [allEmails, setAllEmails]             = useState<any[]>([])
  const [emailTotal, setEmailTotal]           = useState(0)
  const [emailPage, setEmailPage]             = useState(1)
  const [emailSearch, setEmailSearch]         = useState('')
  const [emailSearchInput, setEmailSearchInput] = useState('')
  const [emailSegFilter, setEmailSegFilter]   = useState('')
  const [selectedEmail, setSelectedEmail]     = useState<any | null>(null)
  const [activeVersion, setActiveVersion]     = useState<'A' | 'B'>('A')
  const [manualEmailPreview, setManualEmailPreview] = useState<any | null>(null)
  const EMAIL_LIMIT = 6

  const isFormValid = form.subject.trim() && form.cta.trim() && form.campaign_name.trim()

  const [timingResult, setTimingResult] = useState<any>(null)
  const [timingLoading, setTimingLoading] = useState(false)

  const fetchTiming = async (segment: string, sector: string) => {
    if (!segment) return
    setTimingLoading(true)
    try {
      const res = await API.get('/campaigns/ml-timing', {
        params: { segment, secteur: sector || 'Informatique & Tech' }
      })
      setTimingResult(res.data)
    } catch { setTimingResult(null) }
    finally { setTimingLoading(false) }
  }

  const fetchAll = () => {
    setLoading(true)
    Promise.all([
      API.get('/campaigns/stats/email').catch(() => ({ data: null })),
      API.get('/campaigns/ab-stats').catch(() => ({ data: null })),
      API.get('/campaigns/history').catch(() => ({ data: [] })),
      API.get('/campaigns/ab-winner').catch(() => ({ data: null })),
    ]).then(([email, ab, hist, winner]) => {
      setEmailStats(email.data)
      setAbStats(ab.data)
      setHistory(hist.data || [])
      setAbWinner(winner.data)
    }).finally(() => setLoading(false))
  }

  const computeWinner = async () => {
    try {
      const res = await API.post('/campaigns/ab-winner/compute')
      setResult({ type: 'success', msg: `Calcul lancé — résultat dans quelques secondes` })
      setTimeout(() => API.get('/campaigns/ab-winner').then(r => setAbWinner(r.data)), 4000)
    } catch (e: any) {
      setResult({ type: 'error', msg: e.message })
    }
  }

  const fetchEmails = (page = 1, search = emailSearch, seg = emailSegFilter) => {
    API.get('/campaigns/preview-emails', {
      params: { limit: EMAIL_LIMIT, offset: (page - 1) * EMAIL_LIMIT, search, segment: seg || null }
    }).then(r => { setAllEmails(r.data.items || []); setEmailTotal(r.data.total || 0) })
  }

  useEffect(() => { fetchAll() }, [])
  useEffect(() => { fetchEmails(emailPage, emailSearch, emailSegFilter) }, [emailPage, emailSearch, emailSegFilter])

  const searchCompanies = async (q: string) => {
    if (q.length < 2) { setCompanySuggestions([]); return }
    const res = await API.get('/leads/', { params: { search: q, limit: 8 } })
    setCompanySuggestions(res.data.items || [])
  }

  const addCompany = (lead: any) => {
    if (!selectedCompanies.find(c => c.id === lead.id))
      setSelectedCompanies([...selectedCompanies, lead])
    setCompanySearch(''); setCompanySuggestions([])
  }

  const launch = async (dryRun: boolean) => {
    setLaunching(true); setResult(null)
    try {
      const res = await API.post('/campaigns/generate-emails', {
        campaign_name: form.campaign_name, segment: form.segment || null,
        limit: form.dailyLimit, dry_run: dryRun, subject: form.subject || null,
        cta: form.cta || null, cta_link: form.ctaLink || null, tone: form.tone || null, sector: form.sector || null,
        region: form.region || null, regenerate: true,
        lead_ids: selectedCompanies.length > 0 ? selectedCompanies.map(c => c.id) : null,
      })
      setResult({ type: 'success', msg: `"${res.data.campaign_name}" — ${res.data.limit} emails · ${dryRun ? 'Dry-run' : 'Envoi réel'}` })
      setTimeout(() => { fetchAll(); fetchEmails(1) }, 6000)
    } catch (e: any) {
      setResult({ type: 'error', msg: e.message })
    } finally { setLaunching(false) }
  }

  const sendManualEmail = async () => {
    if (!form.manualEmail) return
    setLaunching(true); setResult(null)
    try {
      const res = await API.post('/campaigns/send-manual', {
        to_email: form.manualEmail, to_name: form.manualName || form.manualEmail,
        subject: form.subject || null, cta: form.cta || null, tone: form.tone || null,
      })
      setManualEmailPreview({ to: form.manualEmail, subject: res.data.subject, body: res.data.body })
      setResult({ type: 'success', msg: `Email envoyé à ${form.manualEmail}` })
      setForm({ ...form, manualEmail: '', manualName: '' })
    } catch (e: any) {
      setResult({ type: 'error', msg: e.message })
    } finally { setLaunching(false) }
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />

      {/* Modal email manuel */}
      {manualEmailPreview && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg animate-scale-in">
            <div className="flex justify-between items-center px-6 py-4 border-b border-gray-100">
              <div>
                <div className="flex items-center gap-2">
                  <CheckCircle size={16} className="text-green-500" />
                  <h3 className="font-bold text-gray-900">Email envoyé avec succès</h3>
                </div>
                <p className="text-xs text-gray-400 mt-0.5">À : {manualEmailPreview.to}</p>
              </div>
              <button onClick={() => setManualEmailPreview(null)}
                className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-400">
                <X size={16} />
              </button>
            </div>
            <div className="p-6 max-h-[70vh] overflow-auto">
              <EmailHtmlPreview subject={manualEmailPreview.subject} body={manualEmailPreview.body} cta={form.cta} />
            </div>
            <div className="px-6 pb-5">
              <button onClick={() => setManualEmailPreview(null)}
                className="btn btn-primary w-full justify-center">
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="ml-56 flex-1 overflow-auto min-w-0">

        {/* Header */}
        <header className="sticky top-0 z-20 bg-white/80 backdrop-blur-md border-b border-gray-100 px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-gray-900">Campagnes Email</h1>
            </div>
            {/* KPI header */}
            <div className="flex items-center gap-6">
              {[
                { val: emailStats?.total_with_email?.toLocaleString('fr') ?? '—', label: 'Prospects', color: 'text-gray-900' },
                { val: emailStats?.generated ?? 0,  label: 'Générés',  color: 'text-indigo-600' },
                { val: emailStats?.sent ?? 0,        label: 'Envoyés',  color: 'text-emerald-600' },
                { val: `${emailStats?.open_rate ?? 0}%`,  label: 'Ouverture', color: 'text-sky-600' },
                { val: `${emailStats?.click_rate ?? 0}%`, label: 'Clics',     color: 'text-violet-600' },
              ].map(({ val, label, color }) => (
                <div key={label} className="text-center">
                  <p className={`text-xl font-extrabold tabular-nums ${color}`}>{val}</p>
                  <p className="text-[11px] text-gray-400 font-medium">{label}</p>
                </div>
              ))}
              <button onClick={fetchAll} className="btn btn-secondary text-xs ml-2">
                <RefreshCw size={13} />
              </button>
            </div>
          </div>
        </header>

        <div className="p-8 space-y-6">

          {/* Alert */}
          {result && (
            <div className={`flex items-center gap-3 px-5 py-3.5 rounded-xl border text-sm animate-fade-up ${
              result.type === 'success'
                ? 'bg-green-50 border-green-200 text-green-800'
                : 'bg-red-50 border-red-200 text-red-700'
            }`}>
              {result.type === 'success'
                ? <CheckCircle size={16} className="flex-shrink-0" />
                : <AlertCircle size={16} className="flex-shrink-0" />
              }
              <span className="flex-1 font-medium">{result.msg}</span>
              <button onClick={() => setResult(null)} className="ml-auto text-current opacity-50 hover:opacity-100">
                <X size={14} />
              </button>
            </div>
          )}

          {/* Main grid */}
          <div className="grid xl:grid-cols-2 gap-6">

            {/* COLONNE GAUCHE */}
            <div className="space-y-5">

              {/* Créer une campagne */}
              <div className="card p-6 space-y-5">
                <div className="flex items-center gap-3 pb-4 border-b border-gray-100">
                  <div className="w-1 h-6 rounded-full bg-indigo-500" />
                  <h2 className="font-bold text-gray-900 text-[15px]">Créer une campagne</h2>
                </div>

                {/* Nom */}
                <div>
                  <Label required>Nom de la campagne</Label>
                  <input className={`input ${!form.campaign_name ? 'border-red-200' : ''}`}
                    placeholder="Ex: Prospection Startups Tunis — Juin 2026"
                    value={form.campaign_name}
                    onChange={e => setForm({ ...form, campaign_name: e.target.value })} />
                </div>

                {/* Objet + CTA */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label required>Objet de l'email</Label>
                    <input className={`input ${!form.subject ? 'border-red-200' : ''}`}
                      placeholder="Doublez vos leads en 30 jours"
                      value={form.subject}
                      onChange={e => setForm({ ...form, subject: e.target.value })} />
                  </div>
                  <div>
                    <Label required>CTA</Label>
                    <input className={`input ${!form.cta ? 'border-red-200' : ''}`}
                      placeholder="Réserver un appel de 15 min"
                      value={form.cta}
                      onChange={e => setForm({ ...form, cta: e.target.value })} />
                  </div>
                </div>

                {/* Lien du CTA */}
                <div>
                  <Label>Lien du bouton CTA <span className="normal-case font-normal text-gray-400">(où mène le bouton)</span></Label>
                  <input className="input"
                    placeholder="https://calendly.com/votre-lien  ·  https://votre-site.tn"
                    value={form.ctaLink}
                    onChange={e => setForm({ ...form, ctaLink: e.target.value })} />
                </div>

                {/* Ton + Segment + Secteur + Région */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Ton</Label>
                    <select className="input" value={form.tone}
                      onChange={e => setForm({ ...form, tone: e.target.value })}>
                      <option value="professionnel">Professionnel</option>
                      <option value="direct et confiant">Direct et confiant</option>
                      <option value="amical et accessible">Amical et accessible</option>
                      <option value="éducatif et utile">Éducatif et utile</option>
                      <option value="urgent et percutant">Urgent et percutant</option>
                    </select>
                  </div>
                  <div>
                    <Label>Segment</Label>
                    <select className="input" value={form.segment}
                      onChange={e => {
                        setForm({ ...form, segment: e.target.value })
                        fetchTiming(e.target.value, form.sector)
                      }}>
                      {['', 'Chaud', 'Prêts à Acheter', 'Froid', 'À Risque'].map((o, i) => (
                        <option key={o} value={o}>{['Tous', 'Chaud', 'Prêts à Acheter', 'Froid', 'À Risque'][i]}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <Label>Secteur</Label>
                    <select className="input" value={form.sector}
                      onChange={e => {
                        setForm({ ...form, sector: e.target.value })
                        fetchTiming(form.segment, e.target.value)
                      }}>
                      {['','Informatique & Tech','Finance & Comptabilité','Santé','Immobilier','Construction & BTP','Transport & Logistique','Education & Formation','Restauration & Hôtellerie','Industrie & Production','Commerce & Distribution','Services aux entreprises','Agriculture & Alimentaire','Energie & Environnement','Juridique','Marketing & Communication'].map(o => (
                        <option key={o} value={o}>{o || 'Tous'}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Société spécifique */}
                <div className="relative">
                  <Label>Société spécifique <span className="normal-case font-normal text-gray-400">(optionnel)</span></Label>
                  <div className="relative">
                    <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input className="input pl-8" placeholder="Rechercher une société..."
                      value={companySearch}
                      onChange={e => { setCompanySearch(e.target.value); searchCompanies(e.target.value) }} />
                  </div>
                  {companySuggestions.length > 0 && (
                    <div className="absolute z-10 w-full bg-white border border-gray-100 rounded-xl shadow-lg mt-1 overflow-hidden">
                      {companySuggestions.map(lead => (
                        <div key={lead.id} onClick={() => addCompany(lead)}
                          className="flex items-center justify-between px-4 py-2.5 hover:bg-indigo-50 cursor-pointer">
                          <span className="text-sm font-medium text-gray-800">{lead.company}</span>
                          <span className="text-xs text-gray-400">{lead.sector}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {selectedCompanies.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {selectedCompanies.map(c => (
                        <span key={c.id} className="flex items-center gap-1 bg-indigo-50 border border-indigo-100 text-indigo-700 px-3 py-1 rounded-full text-xs font-medium">
                          {c.company}
                          <button onClick={() => setSelectedCompanies(selectedCompanies.filter(x => x.id !== c.id))}
                            className="hover:text-red-500 ml-0.5">×</button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Volume */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <Label>Volume quotidien</Label>
                    <span className="text-[13px] font-bold text-indigo-600">{form.dailyLimit} emails/jour</span>
                  </div>
                  <input type="range" min={1} max={300} value={form.dailyLimit}
                    onChange={e => setForm({ ...form, dailyLimit: Number(e.target.value) })}
                    className="w-full accent-indigo-600 h-1.5" />
                  <div className="flex justify-between text-[10px] text-gray-400 mt-1"><span>1</span><span>300</span></div>
                </div>

                {/* Boutons */}
                <div className="pt-2 border-t border-gray-100">
                  {!isFormValid && (
                    <p className="text-xs text-red-400 mb-3 flex items-center gap-1.5">
                      <AlertCircle size={12} /> Remplissez le nom, l'objet et le CTA pour lancer
                    </p>
                  )}
                  <div className="grid grid-cols-2 gap-3 mb-2">
                    <button onClick={() => launch(true)} disabled={launching || !isFormValid}
                      className="btn btn-secondary justify-center py-2.5 disabled:opacity-40">
                      {launching ? <Clock size={14} className="animate-spin" /> : <Eye size={14} />}
                      Aperçu
                    </button>
                    <button onClick={() => launch(false)} disabled={launching || !isFormValid}
                      className="btn btn-primary justify-center py-2.5 disabled:opacity-40">
                      {launching ? <Clock size={14} className="animate-spin" /> : <Send size={14} />}
                      Lancer
                    </button>
                  </div>
                  <p className="text-[11px] text-gray-400 text-center">
                    {selectedCompanies.length > 0
                      ? `${selectedCompanies.length} société(s) ciblée(s)`
                      : [form.segment, form.sector, form.region].filter(Boolean).join(' · ') || 'Tous les leads avec email'
                    } · {form.dailyLimit} emails max
                  </p>
                </div>
              </div>

              {/* Envoyer à un contact */}
              <div className="card p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-1 h-6 rounded-full bg-emerald-500" />
                  <h2 className="font-bold text-gray-900 text-[15px]">Envoyer à un contact</h2>
                </div>
                <div className="space-y-2">
                  <input className="input w-full text-sm" placeholder="Nom du contact (optionnel)"
                    value={form.manualName}
                    onChange={e => setForm({ ...form, manualName: e.target.value })} />
                  <div className="flex gap-2">
                    <input type="email" className="input flex-1 text-sm"
                      placeholder="Email — ex: contact@entreprise.tn"
                      value={form.manualEmail}
                      onChange={e => setForm({ ...form, manualEmail: e.target.value })} />
                    <button onClick={sendManualEmail} disabled={!form.manualEmail || launching}
                      className="btn btn-primary disabled:opacity-40 flex-shrink-0">
                      <Send size={14} /> Envoyer
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* COLONNE DROITE */}
            <div className="space-y-5">

              {/* ML Timing */}
              {form.segment && (
                <div className="card p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-1 h-6 rounded-full bg-indigo-500" />
                    <Brain size={16} className="text-indigo-500" />
                    <h2 className="font-bold text-gray-900 text-[15px]">Meilleur moment d'envoi</h2>
                    {timingResult?.source === 'real' && (
                      <span className="ml-auto text-[10px] font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-600">
                        Données réelles
                      </span>
                    )}
                  </div>

                  {!form.segment ? (
                    <p className="text-sm text-gray-400 text-center py-4">Sélectionnez un segment pour voir les recommandations</p>
                  ) : timingLoading ? (
                    <div className="flex items-center justify-center py-6 gap-2 text-indigo-400">
                      <Clock size={16} className="animate-spin" />
                      <span className="text-sm">Analyse en cours…</span>
                    </div>
                  ) : timingResult ? (
                    <div>
                      {/* Top slot */}
                      <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4 mb-4">
                        <div className="flex items-center gap-2 mb-1">
                          <Trophy size={14} className="text-indigo-500" />
                          <span className="text-[11px] font-bold text-indigo-600 uppercase tracking-wide">Créneau optimal</span>
                        </div>
                        <div className="flex items-baseline gap-2">
                          <span className="text-2xl font-extrabold text-indigo-700">
                            {timingResult.top_3?.[0]?.jour}
                          </span>
                          <span className="text-xl font-bold text-indigo-500">
                            {timingResult.top_3?.[0]?.heure}
                          </span>
                          <span className="ml-auto text-[11px] font-semibold bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">
                            Score {timingResult.top_3?.[0]?.score?.toFixed(1)}%
                          </span>
                        </div>
                      </div>

                      {/* Top 3 */}
                      <div className="space-y-2">
                        {timingResult.top_3?.slice(1).map((slot: any, i: number) => (
                          <div key={i} className="flex items-center justify-between bg-gray-50 border border-gray-100 rounded-lg px-4 py-2.5">
                            <div className="flex items-center gap-2">
                              <span className="text-[11px] font-semibold text-gray-400">#{i + 2}</span>
                              <span className="text-[13px] font-semibold text-gray-800">{slot.jour}</span>
                              <span className="text-[13px] text-gray-500">{slot.heure}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-20 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                                <div className="h-full bg-indigo-400 rounded-full" style={{ width: `${slot.score}%` }} />
                              </div>
                              <span className="text-[11px] text-gray-400 w-10 text-right">{slot.score?.toFixed(1)}%</span>
                            </div>
                          </div>
                        ))}
                      </div>

                    </div>
                  ) : null}
                </div>
              )}

              {/* A/B Testing */}
              {abStats && (abStats['A'] || abStats['B']) && (
                <SectionCard color="bg-orange-500" title="Résultats A/B Testing">
                  <div className="grid grid-cols-2 gap-3">
                    {['A', 'B'].map(v => {
                      const s = abStats[v]; if (!s) return null
                      const isA = v === 'A'
                      return (
                        <div key={v} className={`rounded-xl p-4 border ${isA ? 'bg-blue-50 border-blue-100' : 'bg-violet-50 border-violet-100'}`}>
                          <div className="flex items-center justify-between mb-3">
                            <span className={`text-sm font-bold px-2.5 py-1 rounded-lg ${isA ? 'bg-blue-100 text-blue-700' : 'bg-violet-100 text-violet-700'}`}>
                              Version {v}
                            </span>
                            <span className="text-[11px] text-gray-400 font-medium">50%</span>
                          </div>
                          <div className="grid grid-cols-3 gap-1 text-center">
                            {[
                              { val: s.total, lab: 'Assignés' },
                              { val: s.sent,  lab: 'Envoyés'  },
                              { val: `${s.open_rate}%`, lab: 'Ouverture', color: s.open_rate > 0 ? (isA ? 'text-blue-600' : 'text-violet-600') : 'text-gray-300' },
                            ].map(({ val, lab, color }) => (
                              <div key={lab}>
                                <p className={`text-lg font-extrabold ${color || 'text-gray-900'}`}>{val}</p>
                                <p className="text-[10px] text-gray-400">{lab}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  {abStats['A'] && abStats['B'] && abStats['A'].open_rate !== abStats['B'].open_rate && (
                    <div className="mt-3 flex items-center gap-2 bg-green-50 border border-green-100 rounded-xl px-4 py-3 text-sm text-green-700 font-semibold">
                      <Trophy size={15} />
                      Gagnant : Version {abStats['A'].open_rate >= abStats['B'].open_rate ? 'A' : 'B'}
                      <span className="ml-auto font-bold">{Math.max(abStats['A'].open_rate, abStats['B'].open_rate)}%</span>
                    </div>
                  )}
                </SectionCard>
              )}

              {/* Gagnant auto */}
              {(abWinner?.winner || abStats?.['A'] || abStats?.['B']) && <SectionCard color="bg-amber-400" title="Gagnant auto-sélectionné" badge="après 24h">
                <div className="flex justify-end mb-4 -mt-2">
                  <button onClick={computeWinner}
                    className="btn btn-secondary text-xs">
                    <Zap size={12} /> Calculer maintenant
                  </button>
                </div>
                {!abWinner || abWinner.winner === null ? (
                  <div className="flex flex-col items-center py-8 text-gray-300">
                    <Trophy size={32} className="mb-3" />
                    {abWinner?.reason === 'insufficient_data' ? (
                      <>
                        <p className="text-sm font-semibold text-gray-500">Données insuffisantes</p>
                        <p className="text-xs text-gray-400 mt-1">Minimum {abWinner.min_required} envois par version</p>
                        <div className="flex gap-3 mt-4 text-xs">
                          <span className="badge badge-blue">A : {abWinner.stats?.A?.sent ?? 0} envois</span>
                          <span className="badge badge-violet">B : {abWinner.stats?.B?.sent ?? 0} envois</span>
                        </div>
                      </>
                    ) : (
                      <>
                        <p className="text-sm font-medium text-gray-400">Aucun résultat disponible</p>
                        <p className="text-xs text-gray-400 mt-1">Lancez le calcul pour analyser</p>
                      </>
                    )}
                  </div>
                ) : (
                  <div>
                    <div className={`rounded-xl p-4 mb-3 flex items-center gap-4 ${abWinner.winner === 'A' ? 'bg-blue-50 border border-blue-100' : 'bg-violet-50 border border-violet-100'}`}>
                      <Trophy size={28} className={abWinner.winner === 'A' ? 'text-blue-500' : 'text-violet-500'} />
                      <div className="flex-1">
                        <p className={`font-bold text-base ${abWinner.winner === 'A' ? 'text-blue-700' : 'text-violet-700'}`}>
                          Version {abWinner.winner} — Gagnante
                        </p>
                        {abWinner.decided_at && (
                          <p className="text-xs text-gray-400 mt-0.5">
                            {new Date(abWinner.decided_at).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                          </p>
                        )}
                      </div>
                      <p className={`text-2xl font-extrabold ${abWinner.winner === 'A' ? 'text-blue-600' : 'text-violet-600'}`}>
                        {abWinner.stats?.[abWinner.winner]?.open_rate}%
                      </p>
                    </div>
                  </div>
                )}
              </SectionCard>}

              {/* Emails générés */}
              <div className="card overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
                  <Mail size={16} className="text-indigo-500" />
                  <h2 className="font-bold text-gray-900 text-[15px]">Emails générés</h2>
                  <span className="badge badge-blue ml-1">{emailTotal}</span>
                  <div className="ml-auto flex items-center gap-2">
                    <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden">
                      <input type="text" placeholder="Rechercher..." value={emailSearchInput}
                        onChange={e => setEmailSearchInput(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') { setEmailSearch(emailSearchInput); setEmailPage(1) } }}
                        className="text-xs px-2.5 py-1.5 outline-none w-28" />
                      <button onClick={() => { setEmailSearch(emailSearchInput); setEmailPage(1) }}
                        className="px-2 py-1.5 bg-gray-50 hover:bg-gray-100 border-l border-gray-200">
                        <Search size={12} className="text-gray-500" />
                      </button>
                    </div>
                    <select value={emailSegFilter}
                      onChange={e => { setEmailSegFilter(e.target.value); setEmailPage(1) }}
                      className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 outline-none bg-white">
                      <option value="">Tous</option>
                      <option value="Chaud">Chaud</option>
                      <option value="Prêts à Acheter">Prêts à Acheter</option>
                      <option value="Froid">Froid</option>
                      <option value="À Risque">À Risque</option>
                    </select>
                    <button onClick={async () => {
                      if (!confirm('Supprimer tous les emails générés ?')) return
                      await API.delete('/campaigns/reset-emails')
                      setAllEmails([]); setEmailTotal(0); fetchAll()
                      setResult({ type: 'success', msg: 'Emails générés supprimés' })
                    }} className="p-1.5 hover:bg-red-50 rounded-lg text-gray-400 hover:text-red-400 transition-colors">
                      <RotateCcw size={13} />
                    </button>
                  </div>
                </div>

                {allEmails.length === 0 ? (
                  <div className="flex flex-col items-center py-14 text-gray-300">
                    <Mail size={36} className="mb-3" />
                    <p className="text-sm font-medium text-gray-400">Aucun email généré</p>
                    <p className="text-xs text-gray-300 mt-1">Lancez un Dry-run pour prévisualiser</p>
                  </div>
                ) : (
                  <>
                    {allEmails.map(email => (
                      <div key={email.id}>
                        <div
                          onClick={() => { setSelectedEmail(selectedEmail?.id === email.id ? null : email); setActiveVersion('A') }}
                          className={`px-5 py-3.5 border-b border-gray-50 cursor-pointer hover:bg-gray-50 transition-all ${
                            selectedEmail?.id === email.id ? 'bg-blue-50/60 border-l-[3px] border-l-blue-500' : ''
                          }`}>
                          <div className="flex items-center justify-between">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-0.5">
                                <span className="font-semibold text-[13px] text-gray-900 truncate">{email.company}</span>
                                {email.ab_version && (
                                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold flex-shrink-0 ${
                                    email.ab_version === 'A' ? 'bg-blue-100 text-blue-600' : 'bg-violet-100 text-violet-600'
                                  }`}>v{email.ab_version}</span>
                                )}
                                {email.email_sent && (
                                  <span className="text-[10px] bg-green-100 text-green-600 px-1.5 py-0.5 rounded font-semibold flex-shrink-0">Envoyé</span>
                                )}
                              </div>
                              <p className="text-[11px] text-blue-500 font-medium truncate">{email.subject_a}</p>
                              <p className="text-[11px] text-gray-400 truncate">{email.email}</p>
                            </div>
                            <div className="ml-3 text-gray-300 flex-shrink-0">
                              {selectedEmail?.id === email.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            </div>
                          </div>
                        </div>

                        {selectedEmail?.id === email.id && (
                          <div className="bg-gray-50/80 border-b border-gray-100 p-4">
                            <div className="flex gap-2 mb-3">
                              <button onClick={() => setActiveVersion('A')}
                                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                                  activeVersion === 'A' ? 'bg-blue-600 text-white' : 'border border-gray-200 text-gray-500 hover:bg-white'
                                }`}>Version A</button>
                              {email.subject_b && (
                                <button onClick={() => setActiveVersion('B')}
                                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                                    activeVersion === 'B' ? 'bg-violet-600 text-white' : 'border border-gray-200 text-gray-500 hover:bg-white'
                                  }`}>Version B</button>
                              )}
                            </div>
                            <div className="max-h-[420px] overflow-auto">
                              <EmailHtmlPreview
                                subject={activeVersion === 'A' ? email.subject_a : email.subject_b}
                                body={activeVersion === 'A' ? email.body_a : email.body_b}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    ))}

                    {emailTotal > EMAIL_LIMIT && (
                      <div className="flex items-center justify-between px-5 py-3 bg-gray-50 text-xs text-gray-400">
                        <span>{emailTotal} emails · page {emailPage}</span>
                        <div className="flex gap-1">
                          <button onClick={() => setEmailPage(p => Math.max(1, p - 1))} disabled={emailPage === 1}
                            className="p-1.5 border border-gray-200 rounded-lg hover:bg-white disabled:opacity-40 transition-colors">
                            <ChevronLeft size={12} />
                          </button>
                          <button onClick={() => setEmailPage(p => p + 1)} disabled={emailPage * EMAIL_LIMIT >= emailTotal}
                            className="p-1.5 border border-gray-200 rounded-lg hover:bg-white disabled:opacity-40 transition-colors">
                            <ChevronRight size={12} />
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Historique */}
          {history.length > 0 && (
            <div className="card overflow-hidden animate-fade-up">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3">
                <Calendar size={16} className="text-gray-400" />
                <h2 className="font-bold text-gray-900 text-[15px]">Historique des campagnes</h2>
                <span className="badge badge-gray">{history.length}</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-gray-50/80 border-b border-gray-100">
                      {['Campagne', 'Objet', 'Segment', 'Volume', 'Statut', 'Date', ''].map(h => (
                        <th key={h} className="px-5 py-3 text-left text-[10px] font-bold text-gray-400 uppercase tracking-widest">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {history.map(c => {
                      const st = STATUS_CONFIG[c.campaign_status || c.status || 'draft']
                      return (
                        <tr key={c.id} className="table-row-hover">
                          <td className="px-5 py-3.5 font-semibold text-[13px] text-gray-900">
                            {c.campaign_name || c.name}
                          </td>
                          <td className="px-5 py-3.5 text-[12px] text-gray-500 max-w-[180px] truncate">
                            {c.subject || '—'}
                          </td>
                          <td className="px-5 py-3.5">
                            {c.segment_filter ? (
                              <span className={`badge border ${SEG_COLORS[c.segment_filter] || 'badge-gray'}`}>
                                {c.segment_filter}
                              </span>
                            ) : <span className="text-[12px] text-gray-400">Tous</span>}
                          </td>
                          <td className="px-5 py-3.5 text-[12px] text-gray-500">
                            {c.leads_targeted ? `${c.leads_targeted} emails` : '—'}
                          </td>
                          <td className="px-5 py-3.5">
                            <div className={`inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-full ${st.bg} ${st.color}`}>
                              <div className={`w-1.5 h-1.5 rounded-full ${st.dot}`} />
                              {st.label}
                            </div>
                          </td>
                          <td className="px-5 py-3.5 text-[11px] text-gray-400 whitespace-nowrap">
                            {new Date(c.created_at).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                          </td>
                          <td className="px-5 py-3.5">
                            <button
                              onClick={async () => {
                                await API.delete(`/campaigns/${c.id}`)
                                setHistory(history.filter(x => x.id !== c.id))
                              }}
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
            </div>
          )}

        </div>
      </div>
    </div>
  )
}
