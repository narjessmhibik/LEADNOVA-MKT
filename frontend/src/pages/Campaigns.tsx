import { useEffect, useState, useRef } from 'react'
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

function SectionCard({ color, icon, title, subtitle, children, badge }: {
  color: string; icon?: React.ReactNode; title: string; subtitle?: string
  children: React.ReactNode; badge?: string
}) {
  return (
    <div className="card p-6">
      <div className="flex items-center gap-3 mb-5">
        <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${color}`}>
          {icon}
        </div>
        <div>
          <h2 className="font-bold text-gray-900 text-[15px]">{title}</h2>
          {subtitle && <p className="text-[11px] text-gray-400">{subtitle}</p>}
        </div>
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
        <span className="text-white font-bold text-sm tracking-wide">Leadnova</span>
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
            <span className="inline-flex items-center gap-1.5 bg-[var(--nova-600)] text-white text-[13px] font-semibold px-5 py-2.5 rounded-lg shadow-sm">
              {cta} <ArrowRight size={14} />
            </span>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="bg-gray-50 border-t border-gray-100 px-6 py-3 text-center">
        <p className="text-[10px] text-gray-400">Envoyé par Leadnova · Prospection B2B</p>
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
  const [showConfirm, setShowConfirm] = useState(false)

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

  const [timingResult, setTimingResult]   = useState<any>(null)
  const [timingLoading, setTimingLoading] = useState(false)

  const [previewOneResult, setPreviewOneResult]   = useState<any | null>(null)
  const [previewOneLoading, setPreviewOneLoading] = useState(false)
  const [winnerDismissed, setWinnerDismissed]     = useState(false)
  const [progress, setProgress]   = useState<any | null>(null)
  const [activeCampaignId, setActiveCampaignId] = useState<number | null>(null)
  const [scheduleMode, setScheduleMode] = useState(false)
  const [scheduledAt, setScheduledAt]   = useState('')
  const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const previewOne = async () => {
    setPreviewOneLoading(true)
    try {
      const res = await API.post('/campaigns/preview-one', {
        segment: form.segment || 'Froid',
        sector:  form.sector  || null,
        subject: form.subject || null,
        cta:     form.cta     || null,
        tone:    form.tone    || null,
      })
      setPreviewOneResult(res.data)
    } catch (e: any) {
      setResult({ type: 'error', msg: `Aperçu rapide échoué : ${e.message}` })
    } finally {
      setPreviewOneLoading(false)
    }
  }

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

  const startProgressPolling = (campaignId: number) => {
    setActiveCampaignId(campaignId)
    setProgress({ status: 'running', generated: 0, sent: 0, errors: 0, total: form.dailyLimit })
    if (progressIntervalRef.current) clearInterval(progressIntervalRef.current)
    progressIntervalRef.current = setInterval(async () => {
      try {
        const r = await API.get(`/campaigns/${campaignId}/progress`)
        setProgress(r.data)
        if (r.data.status === 'done') {
          clearInterval(progressIntervalRef.current!)
          progressIntervalRef.current = null
          setTimeout(() => { fetchAll(); fetchEmails(1); setProgress(null) }, 2000)
        }
      } catch { /* Redis indisponible, on ignore */ }
    }, 2500)
  }

  const launch = async (dryRun: boolean) => {
    setLaunching(true); setResult(null); setProgress(null)
    try {
      const res = await API.post('/campaigns/generate-emails', {
        campaign_name: form.campaign_name, segment: form.segment || null,
        limit: form.dailyLimit, dry_run: dryRun, subject: form.subject || null,
        cta: form.cta || null, cta_link: form.ctaLink || null, tone: form.tone || null, sector: form.sector || null,
        region: form.region || null, regenerate: true,
        lead_ids: selectedCompanies.length > 0 ? selectedCompanies.map(c => c.id) : null,
      })
      setResult({ type: 'success', msg: `"${res.data.campaign_name}" — ${res.data.limit} emails · ${dryRun ? 'Dry-run' : 'Envoi réel'}` })
      if (res.data.campaign_id) startProgressPolling(res.data.campaign_id)
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
    <div className="flex h-screen bg-[var(--bg)]">
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

      {/* Modale aperçu rapide */}
      {previewOneResult && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg animate-scale-in">
            <div className="flex justify-between items-center px-6 py-4 border-b border-gray-100">
              <div>
                <div className="flex items-center gap-2">
                  <Sparkles size={16} className="text-[var(--nova-500)]" />
                  <h3 className="font-bold text-gray-900">Aperçu rapide — 1 email généré</h3>
                </div>
                <p className="text-xs text-gray-400 mt-0.5">
                  {previewOneResult.company} · {previewOneResult.segment} · {previewOneResult.sector}
                </p>
              </div>
              <button onClick={() => setPreviewOneResult(null)}
                className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-400">
                <X size={16} />
              </button>
            </div>
            <div className="p-6 max-h-[70vh] overflow-auto">
              <EmailHtmlPreview subject={previewOneResult.subject} body={previewOneResult.body} cta={form.cta} />
            </div>
            <div className="px-6 pb-5">
              <button onClick={() => setPreviewOneResult(null)} className="btn btn-primary w-full justify-center">
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modale de confirmation avant envoi */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl animate-scale-in max-h-[92vh] flex flex-col">
            {/* Header */}
            <div className="flex justify-between items-start px-6 py-4 border-b border-gray-100">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center flex-shrink-0">
                  <Send size={18} className="text-amber-500" />
                </div>
                <div>
                  <h3 className="font-bold text-gray-900 text-[15px]">Confirmer l'envoi de la campagne</h3>
                  <p className="text-xs text-gray-400 mt-0.5">Vérifiez avant d'envoyer — l'action est définitive.</p>
                </div>
              </div>
              <button onClick={() => setShowConfirm(false)}
                className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-400">
                <X size={16} />
              </button>
            </div>

            {/* Corps */}
            <div className="p-6 overflow-auto space-y-5">
              {/* Récapitulatif */}
              <div className="grid grid-cols-2 gap-3">
                {[
                  { lab: 'Campagne', val: form.campaign_name || '—' },
                  { lab: 'Objet',    val: form.subject || '—' },
                  { lab: 'Ciblage',  val: selectedCompanies.length > 0
                      ? `${selectedCompanies.length} société(s)`
                      : [form.segment, form.sector, form.region].filter(Boolean).join(' · ') || 'Tous les leads avec email' },
                  { lab: 'Volume',   val: `${form.dailyLimit} emails max` },
                ].map(({ lab, val }) => (
                  <div key={lab} className="rounded-xl border border-[var(--border)] px-4 py-3">
                    <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">{lab}</p>
                    <p className="text-[13px] font-semibold text-gray-800 truncate" title={val}>{val}</p>
                  </div>
                ))}
              </div>

              {/* Aperçu de l'email */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Eye size={14} className="text-[var(--nova-500)]" />
                  <p className="text-[11px] font-bold text-gray-500 uppercase tracking-widest">Aperçu de l'email</p>
                  <span className="ml-auto inline-flex items-center gap-1 text-[10px] font-semibold text-[var(--nova-600)] bg-[var(--nova-50)] px-2 py-0.5 rounded-full">
                    <Sparkles size={10} /> Personnalisé par l'IA pour chaque destinataire
                  </span>
                </div>
                <div className="max-h-[40vh] overflow-auto">
                  <EmailHtmlPreview
                    subject={allEmails[0]?.subject_a || form.subject}
                    body={allEmails[0]?.body_a ||
                      `Bonjour,\n\nJe me permets de vous contacter au sujet de votre activité.\n\n${form.subject || ''}\n\nSeriez-vous disponible pour un court échange ?`}
                    cta={form.cta}
                  />
                </div>
                {allEmails.length === 0 && (
                  <p className="text-[11px] text-gray-400 mt-2">
                    Modèle d'aperçu — lancez un « Aperçu » (dry-run) pour visualiser un email réel généré.
                  </p>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-gray-100 flex gap-3">
              <button onClick={() => setShowConfirm(false)}
                className="btn btn-secondary flex-1 justify-center">
                Annuler
              </button>
              <button onClick={() => { setShowConfirm(false); launch(false) }} disabled={launching}
                className="btn btn-primary flex-1 justify-center disabled:opacity-40">
                <Send size={14} /> Confirmer et envoyer
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="ml-[var(--sidebar-w)] flex-1 transition-[margin-left] duration-200 overflow-auto min-w-0">

        {/* Header */}
        <header className="sticky top-0 z-20 bg-white/80 backdrop-blur-md border-b border-gray-100 px-8 py-4">
          <div className="flex items-center justify-between gap-6">
            <div>
              <h1 className="text-xl font-extrabold text-gray-900 font-display tracking-tight leading-none">Campagnes</h1>
              <p className="text-[12px] text-gray-400 mt-0.5">Génération IA, A/B testing & envoi d'emails</p>
            </div>
            {/* KPI header */}
            <div className="flex items-center gap-2.5">
              {[
                { val: emailStats?.total_with_email?.toLocaleString('fr') ?? '—', label: 'Prospects', color: 'text-gray-900' },
                { val: emailStats?.generated ?? 0,  label: 'Versions A/B',  color: 'text-[var(--nova-600)]' },
                { val: emailStats?.sent ?? 0,        label: 'Envoyés',  color: 'text-emerald-600' },
                { val: `${emailStats?.open_rate ?? 0}%`,  label: 'Ouverture', color: 'text-sky-600' },
                { val: `${emailStats?.click_rate ?? 0}%`, label: 'Clics',     color: 'text-violet-600' },
              ].map(({ val, label, color }) => (
                <div key={label}
                  className="text-center px-3 py-1.5 rounded-xl border border-transparent hover:border-[var(--border-2)] hover:bg-[var(--surface-2)] hover:shadow-sm transition-all cursor-default">
                  <p className={`text-lg font-extrabold tabular-nums leading-none ${color}`}>{val}</p>
                  <p className="text-[10px] text-gray-400 font-medium mt-1">{label}</p>
                </div>
              ))}
              <button onClick={fetchAll} className="btn btn-secondary text-xs ml-1">
                <RefreshCw size={13} />
              </button>
            </div>
          </div>
        </header>

        <div className="p-8 space-y-6">

          {/* Barre de progression génération */}
          {progress && progress.status === 'running' && (
            <div className="card p-4 border-[var(--nova-200)] bg-[var(--nova-50)] animate-fade-up">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Clock size={14} className="text-[var(--nova-500)] animate-spin" />
                  <span className="text-[13px] font-semibold text-[var(--nova-700)]">
                    Génération en cours…
                  </span>
                </div>
                <span className="text-[12px] font-bold text-[var(--nova-600)] tabular-nums">
                  {progress.generated} / {progress.total} emails
                </span>
              </div>
              <div className="w-full bg-[var(--nova-100)] rounded-full h-2 overflow-hidden">
                <div
                  className="h-2 bg-[var(--nova-500)] rounded-full transition-all duration-500"
                  style={{ width: `${progress.total > 0 ? Math.round((progress.generated / progress.total) * 100) : 0}%` }}
                />
              </div>
              <div className="flex justify-between mt-1.5 text-[10px] text-[var(--nova-500)]">
                <span>{progress.sent > 0 ? `${progress.sent} envoyés` : 'Génération IA...'}</span>
                <span>{progress.total > 0 ? `${Math.round((progress.generated / progress.total) * 100)}%` : '0%'}</span>
              </div>
            </div>
          )}
          {progress && progress.status === 'done' && (
            <div className="flex items-center gap-3 px-5 py-3.5 rounded-xl border bg-green-50 border-green-200 text-green-800 text-sm animate-fade-up">
              <CheckCircle size={16} className="flex-shrink-0" />
              <span className="font-medium">
                Génération terminée — {progress.generated} emails générés
                {progress.sent > 0 ? `, ${progress.sent} envoyés` : ''}
              </span>
            </div>
          )}

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
                  <div className="w-9 h-9 rounded-xl bg-[var(--nova-50)] flex items-center justify-center flex-shrink-0">
                    <Sparkles size={17} className="text-[var(--nova-500)]" />
                  </div>
                  <div>
                    <h2 className="font-bold text-gray-900 text-[15px]">Créer une campagne</h2>
                    <p className="text-[11px] text-gray-400">Génération d'emails personnalisés par l'IA</p>
                  </div>
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

                {/* Banner A/B winner */}
                {abWinner?.winner && !winnerDismissed && (
                  <div className="flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
                    <Trophy size={16} className="text-amber-500 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] font-bold text-amber-800">
                        Version {abWinner.winner} gagnante — {abWinner.stats?.[abWinner.winner]?.open_rate}% d'ouverture
                      </p>
                      <p className="text-[11px] text-amber-600 mt-0.5">
                        Utilisez ces paramètres pour votre prochaine campagne
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        const winnerTone = abWinner.winner === 'A' ? 'direct et confiant' : 'éducatif et utile'
                        setForm(f => ({ ...f, tone: winnerTone }))
                        setWinnerDismissed(true)
                      }}
                      className="text-[11px] font-semibold bg-amber-500 text-white px-3 py-1.5 rounded-lg hover:bg-amber-600 flex-shrink-0">
                      Appliquer
                    </button>
                    <button onClick={() => setWinnerDismissed(true)}
                      className="text-amber-400 hover:text-amber-600 flex-shrink-0">
                      <X size={14} />
                    </button>
                  </div>
                )}

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
                      {['','Culture & Musées','Informatique & Tech','Finance & Comptabilité','Santé','Immobilier','Construction & BTP','Transport & Logistique','Education & Formation','Restauration & Hôtellerie','Industrie & Production','Commerce & Distribution','Services aux entreprises','Agriculture & Alimentaire','Energie & Environnement','Juridique','Marketing & Communication'].map(o => (
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
                          className="flex items-center justify-between px-4 py-2.5 hover:bg-[var(--nova-50)] cursor-pointer">
                          <span className="text-sm font-medium text-gray-800">{lead.company}</span>
                          <span className="text-xs text-gray-400">{lead.sector}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {selectedCompanies.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {selectedCompanies.map(c => (
                        <span key={c.id} className="flex items-center gap-1 bg-[var(--nova-50)] border border-[var(--nova-100)] text-[var(--nova-700)] px-3 py-1 rounded-full text-xs font-medium">
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
                    <span className="text-[13px] font-bold text-[var(--nova-600)]">{form.dailyLimit} emails/jour</span>
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
                  <div className="grid grid-cols-3 gap-2 mb-2">
                    <button onClick={previewOne} disabled={previewOneLoading}
                      className="btn btn-secondary justify-center py-2.5 disabled:opacity-40 text-[var(--nova-600)] border-[var(--nova-200)] hover:bg-[var(--nova-50)]">
                      {previewOneLoading ? <Clock size={14} className="animate-spin" /> : <Sparkles size={14} />}
                      Aperçu rapide
                    </button>
                    <button onClick={() => launch(true)} disabled={launching || !isFormValid}
                      className="btn btn-secondary justify-center py-2.5 disabled:opacity-40">
                      {launching ? <Clock size={14} className="animate-spin" /> : <Eye size={14} />}
                      Dry-run
                    </button>
                    <button onClick={() => setShowConfirm(true)} disabled={launching || !isFormValid}
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
                  <div className="w-9 h-9 rounded-xl bg-emerald-50 flex items-center justify-center flex-shrink-0">
                    <Send size={16} className="text-emerald-500" />
                  </div>
                  <div>
                    <h2 className="font-bold text-gray-900 text-[15px]">Envoyer à un contact</h2>
                    <p className="text-[11px] text-gray-400">Email unique à une adresse précise</p>
                  </div>
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
              <div className="card p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-9 h-9 rounded-xl bg-[var(--nova-50)] flex items-center justify-center flex-shrink-0">
                      <Brain size={17} className="text-[var(--nova-500)]" />
                    </div>
                    <div>
                      <h2 className="font-bold text-gray-900 text-[15px]">Meilleur moment d'envoi</h2>
                      <p className="text-[11px] text-gray-400">Recommandation IA par segment</p>
                    </div>
                    {timingResult?.source === 'real' && (
                      <span className="ml-auto text-[10px] font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-600">
                        Données réelles
                      </span>
                    )}
                  </div>

                  {!form.segment ? (
                    <p className="text-sm text-gray-400 text-center py-4">Sélectionnez un segment pour voir les recommandations</p>
                  ) : timingLoading ? (
                    <div className="flex items-center justify-center py-6 gap-2 text-[var(--nova-400)]">
                      <Clock size={16} className="animate-spin" />
                      <span className="text-sm">Analyse en cours…</span>
                    </div>
                  ) : timingResult ? (
                    <div className="space-y-4">
                      {/* Top slot */}
                      <div className="bg-[var(--nova-50)] border border-[var(--nova-100)] rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-1">
                          <Trophy size={14} className="text-[var(--nova-500)]" />
                          <span className="text-[11px] font-bold text-[var(--nova-600)] uppercase tracking-wide">Créneau optimal</span>
                        </div>
                        <div className="flex items-baseline gap-2">
                          <span className="text-2xl font-extrabold text-[var(--nova-700)]">
                            {timingResult.top_3?.[0]?.jour}
                          </span>
                          <span className="text-xl font-bold text-[var(--nova-500)]">
                            {timingResult.top_3?.[0]?.heure}
                          </span>
                          <span className="ml-auto text-[11px] font-semibold bg-[var(--nova-100)] text-[var(--nova-700)] px-2 py-0.5 rounded-full">
                            {timingResult.top_3?.[0]?.score?.toFixed(1)}%
                          </span>
                        </div>
                      </div>

                      {/* Top 3 */}
                      <div className="space-y-1.5">
                        {timingResult.top_3?.slice(1).map((slot: any, i: number) => (
                          <div key={i} className="flex items-center justify-between bg-gray-50 border border-gray-100 rounded-lg px-3 py-2">
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] font-semibold text-gray-400">#{i + 2}</span>
                              <span className="text-[12px] font-semibold text-gray-800">{slot.jour}</span>
                              <span className="text-[12px] text-gray-500">{slot.heure}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                                <div className="h-full bg-[var(--nova-400)] rounded-full" style={{ width: `${slot.score}%` }} />
                              </div>
                              <span className="text-[10px] text-gray-400 w-8 text-right">{slot.score?.toFixed(1)}%</span>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Heatmap 7j × 16h */}
                      {timingResult.heatmap && (
                        <div>
                          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2">Heatmap — score par créneau</p>
                          <div className="overflow-x-auto">
                            <table className="text-[9px] border-collapse w-full">
                              <thead>
                                <tr>
                                  <td className="pr-1 text-gray-400 w-8" />
                                  {timingResult.hours?.map((h: number) => (
                                    <td key={h} className="text-center text-gray-400 pb-1 w-6">{h}h</td>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {timingResult.days?.map((day: string, di: number) => (
                                  <tr key={day}>
                                    <td className="pr-1 text-gray-500 font-semibold text-[9px] whitespace-nowrap">{day.slice(0,3)}</td>
                                    {timingResult.heatmap[di]?.map((score: number, hi: number) => {
                                      const h = timingResult.hours[hi] as number
                                      const isTop = timingResult.top_3?.[0]?.jour === day &&
                                        timingResult.top_3?.[0]?.heure === `${String(h).padStart(2,'0')}:00`
                                      const bg =
                                        score >= 70 ? '#3730a3' :
                                        score >= 55 ? '#4f46e5' :
                                        score >= 42 ? '#818cf8' :
                                        score >= 28 ? '#a5b4fc' :
                                        score >= 14 ? '#e0e7ff' :
                                                      '#f8fafc'
                                      const textColor = score >= 42 ? 'white' : 'transparent'
                                      return (
                                        <td key={hi} title={`${day} ${h}h — ${score}%`}
                                          className={`w-6 h-5 rounded-sm cursor-default text-center select-none text-[7px] font-bold leading-5 ${isTop ? 'ring-2 ring-yellow-400 ring-offset-0' : ''}`}
                                          style={{ background: bg, color: textColor }} >
                                          {isTop ? '★' : ''}
                                        </td>
                                      )
                                    })}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          <div className="flex items-center gap-2 mt-2">
                            <div className="flex h-2 flex-1 rounded-full overflow-hidden">
                              {[0.05,0.2,0.4,0.6,0.8,1].map((v, i) => (
                                <div key={i} className="flex-1" style={{ background: `rgba(99,102,241,${v})` }} />
                              ))}
                            </div>
                            <span className="text-[9px] text-gray-400">Faible → Fort</span>
                          </div>
                        </div>
                      )}

                      {/* Planification */}
                      <div className="border-t border-gray-100 pt-3">
                        <div className="flex items-center justify-between mb-2">
                          <p className="text-[11px] font-bold text-gray-600 flex items-center gap-1.5">
                            <Calendar size={12} /> Planifier l'envoi
                          </p>
                          <button onClick={() => setScheduleMode(!scheduleMode)}
                            className={`text-[10px] font-semibold px-2.5 py-1 rounded-full border transition-all ${
                              scheduleMode
                                ? 'bg-[var(--nova-600)] text-white border-[var(--nova-600)]'
                                : 'text-gray-500 border-gray-200 hover:border-[var(--nova-300)]'
                            }`}>
                            {scheduleMode ? 'Annuler' : 'Programmer'}
                          </button>
                        </div>
                        {scheduleMode && (
                          <div className="space-y-2">
                            <input type="datetime-local" className="input text-xs w-full"
                              value={scheduledAt}
                              min={new Date().toISOString().slice(0,16)}
                              onChange={e => setScheduledAt(e.target.value)} />
                            <button
                              disabled={!scheduledAt || !activeCampaignId}
                              onClick={async () => {
                                if (!scheduledAt || !activeCampaignId) {
                                  setResult({ type: 'error', msg: "Lancez d'abord un Dry-run pour créer la campagne" })
                                  return
                                }
                                try {
                                  const r = await API.post(`/campaigns/${activeCampaignId}/schedule`, { scheduled_at: scheduledAt })
                                  setResult({ type: 'success', msg: r.data.message })
                                  setScheduleMode(false)
                                  fetchAll()
                                } catch (e: any) {
                                  setResult({ type: 'error', msg: e.message })
                                }
                              }}
                              className="btn btn-primary w-full justify-center text-xs py-2 disabled:opacity-40">
                              <Calendar size={13} /> Confirmer la programmation
                            </button>
                            {!activeCampaignId && (
                              <p className="text-[10px] text-amber-600">Lancez un Dry-run d'abord pour créer la campagne</p>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ) : null}
                </div>

              {/* A/B Testing */}
              <SectionCard color="bg-orange-50" icon={<Zap size={17} className="text-orange-500" />} title="Résultats A/B Testing" subtitle="Comparaison des versions A / B">
                {abStats && (abStats['A'] || abStats['B']) ? (
                  <>
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
                  </>
                ) : (
                  <div className="flex flex-col items-center py-8 text-gray-300">
                    <Zap size={30} className="mb-3" />
                    <p className="text-sm font-semibold text-gray-400">Aucune donnée A/B pour l'instant</p>
                    <p className="text-xs text-gray-400 mt-1">Lancez une campagne pour comparer les versions A et B</p>
                  </div>
                )}
              </SectionCard>

              {/* Gagnant auto */}
              {(abWinner?.winner || abStats?.['A'] || abStats?.['B']) && <SectionCard color="bg-amber-50" icon={<Trophy size={17} className="text-amber-500" />} title="Gagnant auto-sélectionné" subtitle="Sélection automatique après 24h" badge="auto">
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
            </div>
          </div>

          {/* Emails générés — pleine largeur */}
          <div className="card overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-[var(--nova-50)] flex items-center justify-center flex-shrink-0">
                    <Mail size={17} className="text-[var(--nova-500)]" />
                  </div>
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
                            selectedEmail?.id === email.id ? 'bg-blue-50/60 border-l-[3px] border-l-[var(--nova-500)]' : ''
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
                                  activeVersion === 'A' ? 'bg-[var(--nova-600)] text-white' : 'border border-gray-200 text-gray-500 hover:bg-white'
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

          {/* Historique */}
          {history.length > 0 && (
            <div className="card overflow-hidden animate-fade-up">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-gray-100 flex items-center justify-center flex-shrink-0">
                  <Calendar size={16} className="text-gray-500" />
                </div>
                <div>
                  <h2 className="font-bold text-gray-900 text-[15px]">Historique des campagnes</h2>
                  <p className="text-[11px] text-gray-400">Toutes les campagnes lancées</p>
                </div>
                <span className="badge badge-gray ml-1">{history.length}</span>
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

