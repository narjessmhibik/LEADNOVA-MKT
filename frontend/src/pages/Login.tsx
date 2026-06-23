import { useState } from 'react'
import { login, register } from '../services/api'
import { Eye, EyeOff, Sparkles, Target, Zap, BarChart2, ArrowRight, Check } from 'lucide-react'

const FEATURES = [
  { icon: Target,    text: 'Génération automatique de leads B2B' },
  { icon: Sparkles,  text: 'Scoring IA automatique' },
  { icon: Zap,       text: 'Enrichissement automatique & CRM intégré' },
  { icon: BarChart2, text: 'Analytics & segmentation intelligente' },
]

export default function Login() {
  const [tab, setTab]               = useState<'login' | 'register'>('login')
  const [email, setEmail]           = useState('')
  const [password, setPassword]     = useState('')
  const [fullName, setFullName]     = useState('')
  const [error, setError]           = useState('')
  const [showPw, setShowPw]         = useState(false)
  const [loading, setLoading]       = useState(false)
  const [errors, setErrors]         = useState<Record<string, string>>({})
  const [registered, setRegistered] = useState(false)
  const [remember, setRemember]     = useState(false)

  const validate = () => {
    const e: Record<string, string> = {}
    if (tab === 'register' && !fullName.trim()) e.fullName = 'Nom requis'
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) e.email = 'Email invalide'
    if (!password || password.length < 8) e.password = 'Minimum 8 caractères'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async () => {
    if (!validate()) return
    setLoading(true)
    setError('')
    try {
      if (tab === 'login') {
        const res = await login(email, password)
        const storage = remember ? localStorage : sessionStorage
        storage.setItem('token', res.data.access_token)
        storage.setItem('email', email)
        // Stocker le nom pour la sidebar / le profil
        const fullName = (res.data.full_name || '').trim()
        if (fullName) {
          const parts = fullName.split(' ')
          storage.setItem('prenom', parts[0] || '')
          storage.setItem('nom', parts.slice(1).join(' ') || '')
        }
        // Vider l'autre storage pour éviter les conflits
        const other = remember ? sessionStorage : localStorage
        other.removeItem('token')
        other.removeItem('email')
        window.location.href = '/dashboard'
      } else {
        await register(email, password, fullName)
        setRegistered(true)
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail
      setError(msg || (tab === 'login' ? 'Email ou mot de passe incorrect' : "Erreur lors de l'inscription"))
    } finally {
      setLoading(false)
    }
  }

  const pwStrength = password.length === 0 ? 0 : password.length < 6 ? 1 : password.length < 10 ? 2 : 3
  const pwLabels   = ['', 'Faible', 'Correct', 'Fort']
  const pwColors   = ['', '#ef4444', '#f59e0b', '#22c55e']

  return (
    <div className="min-h-screen flex" style={{ background: '#f8fafc' }}>

      {/* Left brand panel */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden"
        style={{ background: 'linear-gradient(145deg, #0f172a 0%, #1e1b4b 60%, #0f172a 100%)' }}>

        {/* Background orbs */}
        <div className="absolute top-[-80px] right-[-80px] w-80 h-80 rounded-full opacity-20"
          style={{ background: 'radial-gradient(circle, #3b82f6, transparent)' }} />
        <div className="absolute bottom-[-60px] left-[-60px] w-64 h-64 rounded-full opacity-15"
          style={{ background: 'radial-gradient(circle, #8b5cf6, transparent)' }} />

        {/* Logo */}
        <div className="flex items-center gap-3 relative z-10">
          <div className="w-10 h-10 rounded-2xl flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)' }}>
            <Sparkles size={18} className="text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">LeadPilot</h1>
            <p className="text-[11px] text-blue-300 font-medium tracking-widest uppercase">AI-Powered CRM</p>
          </div>
        </div>

        {/* Hero */}
        <div className="relative z-10">
          <div className="inline-flex items-center gap-2 bg-blue-500/15 border border-blue-500/25 text-blue-300 text-xs font-semibold px-3 py-1.5 rounded-full mb-6">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            Plateforme B2B Intelligence
          </div>

          <h2 className="text-4xl font-bold text-white leading-tight mb-4">
            Transformez vos
            <span className="block"
              style={{ background: 'linear-gradient(135deg, #60a5fa, #a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              leads en clients
            </span>
          </h2>

          <p className="text-slate-400 text-sm leading-relaxed mb-10 max-w-sm">
            Générez, qualifiez et analysez automatiquement vos leads B2B grâce à l'intelligence artificielle.
          </p>

          <div className="space-y-4">
            {FEATURES.map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-center gap-3">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: 'rgba(59,130,246,.15)', border: '1px solid rgba(99,102,241,.25)' }}>
                  <Icon size={13} className="text-blue-400" />
                </div>
                <span className="text-slate-300 text-sm">{text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Footer stat */}
        <div className="relative z-10 flex gap-8">
          {[
            { val: '8 500+', lab: 'Leads générés' },
            { val: '62.9',   lab: 'Score moyen IA' },
          ].map(({ val, lab }) => (
            <div key={lab}>
              <p className="text-2xl font-bold text-white">{val}</p>
              <p className="text-slate-500 text-xs">{lab}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-[400px] animate-fade-up">

          {/* Écran confirmation email */}
          {registered && (
            <div className="text-center py-10">
              <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center mx-auto mb-5">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                  <polyline points="22,6 12,13 2,6"/>
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Vérifiez votre email</h2>
              <p className="text-gray-500 mb-1">Un lien de confirmation a été envoyé à</p>
              <p className="font-semibold text-blue-600 mb-6">{email}</p>
              <p className="text-sm text-gray-400 mb-8">Cliquez sur le lien dans l'email pour activer votre compte. Vérifiez aussi vos spams.</p>
              <button
                onClick={() => { setRegistered(false); setTab('login') }}
                className="text-sm text-blue-500 hover:underline"
              >
                Retour à la connexion
              </button>
            </div>
          )}

          {!registered && (<>

          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)' }}>
              <Sparkles size={14} className="text-white" />
            </div>
            <span className="font-bold text-gray-900">LeadPilot</span>
          </div>

          <h2 className="text-2xl font-bold text-gray-900 mb-1">
            {tab === 'login' ? 'Bon retour !' : 'Créer un compte'}
          </h2>
          <p className="text-gray-500 text-sm mb-8">
            {tab === 'login'
              ? 'Connectez-vous à votre espace LeadPilot'
              : 'Commencez avec LeadPilot gratuitement'}
          </p>

          {/* Tabs */}
          <div className="flex bg-gray-100 rounded-xl p-1 mb-6">
            {(['login', 'register'] as const).map(t => (
              <button
                key={t}
                onClick={() => { setTab(t); setError(''); setErrors({}) }}
                className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${
                  tab === t
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {t === 'login' ? 'Connexion' : 'Inscription'}
              </button>
            ))}
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-xl mb-5 text-sm">
              <span className="flex-shrink-0"> </span>
              {error}
            </div>
          )}

          <div className="space-y-4">
            {/* Nom (register) */}
            {tab === 'register' && (
              <div>
                <label className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5 block">
                  Nom complet
                </label>
                <input
                  className={`input ${errors.fullName ? 'border-red-400 focus:border-red-400' : ''}`}
                  placeholder="Votre nom complet"
                  value={fullName}
                  onChange={e => { setFullName(e.target.value); setErrors({ ...errors, fullName: '' }) }}
                />
                {errors.fullName && <p className="text-red-500 text-xs mt-1">{errors.fullName}</p>}
              </div>
            )}

            {/* Email */}
            <div>
              <label className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5 block">
                Email professionnel
              </label>
              <input
                type="email"
                className={`input ${errors.email ? 'border-red-400 focus:border-red-400' : ''}`}
                placeholder="vous@entreprise.com"
                value={email}
                onChange={e => { setEmail(e.target.value); setErrors({ ...errors, email: '' }) }}
              />
              {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email}</p>}
            </div>

            {/* Password */}
            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
                  Mot de passe
                </label>
                {tab === 'login' && (
                  <a href="#" className="text-xs text-blue-600 hover:underline font-medium">Oublié ?</a>
                )}
              </div>
              <div className={`input flex items-center gap-2 p-0 overflow-hidden ${errors.password ? 'border-red-400' : ''}`}>
                <input
                  type={showPw ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={e => { setPassword(e.target.value); setErrors({ ...errors, password: '' }) }}
                  className="flex-1 outline-none text-sm px-3.5 py-2.5 bg-transparent"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="pr-3.5 text-gray-400 hover:text-gray-600 flex-shrink-0"
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {errors.password && <p className="text-red-500 text-xs mt-1">{errors.password}</p>}

              {/* Strength bar */}
              {tab === 'register' && password.length > 0 && (
                <div className="mt-2">
                  <div className="flex gap-1 mb-1">
                    {[1, 2, 3].map(i => (
                      <div key={i} className="h-1.5 flex-1 rounded-full transition-all"
                        style={{ background: i <= pwStrength ? pwColors[pwStrength] : '#e2e8f0' }} />
                    ))}
                  </div>
                  <p className="text-xs font-medium" style={{ color: pwColors[pwStrength] || '#94a3b8' }}>
                    {pwLabels[pwStrength]}
                  </p>
                </div>
              )}
            </div>

            {/* Remember me */}
            {tab === 'login' && (
              <label className="flex items-center gap-2 cursor-pointer" onClick={() => setRemember(r => !r)}>
                <div className={`w-4 h-4 border-2 rounded flex items-center justify-center transition-colors ${remember ? 'bg-blue-500 border-blue-500' : 'border-gray-300'}`}>
                  <Check size={10} className={remember ? 'text-white' : 'text-transparent'} />
                </div>
                <span className="text-sm text-gray-500">Se souvenir de moi</span>
              </label>
            )}
          </div>

          {/* Submit */}
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="w-full mt-6 flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-bold text-white transition-all disabled:opacity-60"
            style={{ background: loading ? '#93c5fd' : 'linear-gradient(135deg, #2563eb, #7c3aed)', boxShadow: '0 4px 15px rgba(37,99,235,.4)' }}
          >
            {loading ? (
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
            ) : (
              <>
                {tab === 'login' ? 'Se connecter' : "Créer mon compte"}
                <ArrowRight size={16} />
              </>
            )}
          </button>

          <p className="text-center text-xs text-gray-400 mt-6">
            En continuant, vous acceptez nos{' '}
            <a href="#" className="text-blue-600 hover:underline">Conditions d'utilisation</a>
            {' '}et notre{' '}
            <a href="#" className="text-blue-600 hover:underline">Politique de confidentialité</a>
          </p>
          </>)}
        </div>
      </div>
    </div>
  )
}
