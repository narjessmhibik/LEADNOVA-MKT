import { useState } from 'react'
import Sidebar from '../components/Navbar'
import {
  User, Shield, Bell, Camera, Check, X,
  Mail, Phone, Briefcase, ChevronRight,
  Sparkles, Megaphone, AlertTriangle, FileBarChart
} from 'lucide-react'

const TABS = [
  { id: 'profil',        label: 'Profil',          icon: User },
  { id: 'securite',      label: 'Sécurité',         icon: Shield },
  { id: 'notifications', label: 'Notifications',    icon: Bell },
]

const NOTIF_ITEMS = [
  { key: 'lead',   title: 'Nouveau lead collecté', desc: 'Notification à chaque nouveau lead scrapé',   icon: Sparkles,  color: 'text-[var(--nova-500)]', bg: 'bg-[var(--nova-50)]' },
  { key: 'camp',   title: 'Campagne terminée',      desc: 'Être notifié quand une campagne se termine',   icon: Megaphone, color: 'text-sky-500',    bg: 'bg-sky-50'    },
]

const NOTIF_DEFAULTS = { lead: true, camp: true }

function loadNotifs(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem('notif_prefs')
    return raw ? { ...NOTIF_DEFAULTS, ...JSON.parse(raw) } : NOTIF_DEFAULTS
  } catch { return NOTIF_DEFAULTS }
}

export default function Parametres() {
  const store = localStorage.getItem('token') ? localStorage : sessionStorage
  const [activeTab, setActiveTab]   = useState('profil')
  const [avatar, setAvatar]         = useState<string | null>(store.getItem('avatar'))
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle')

  const [form, setForm] = useState({
    prenom: store.getItem('prenom') || '',
    nom:    store.getItem('nom')    || '',
    email:  store.getItem('email') || '',
    poste:  store.getItem('poste') || '',
    telephone: store.getItem('telephone') || '',
  })

  const [passwords, setPasswords] = useState({ current: '', next: '', confirm: '' })
  const [pwStatus,  setPwStatus]  = useState<'idle' | 'success' | 'error' | 'mismatch'>('idle')

  const [notifs, setNotifs] = useState<Record<string, boolean>>(loadNotifs)
  const [notifSaved, setNotifSaved] = useState(false)

  //  Photo
  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 2 * 1024 * 1024) { alert('Max 2MB'); return }
    const reader = new FileReader()
    reader.onloadend = () => {
      const b64 = reader.result as string
      setAvatar(b64)
      store.setItem('avatar', b64)
    }
    reader.readAsDataURL(file)
  }

  //  Profil save
  const handleSaveProfil = async () => {
    setSaveStatus('saving')
    Object.entries(form).forEach(([k, v]) => store.setItem(k, v))
    try {
      const token = store.getItem('token')
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'}/auth/me`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ full_name: `${form.prenom} ${form.nom}`.trim() }),
      })
      if (!res.ok) throw new Error('save failed')
      setSaveStatus('success')
    } catch {
      setSaveStatus('error')
    }
    setTimeout(() => setSaveStatus('idle'), 3000)
  }

  //  Password save
  const handleSavePassword = () => {
    if (!passwords.current || !passwords.next) { setPwStatus('error'); return }
    if (passwords.next !== passwords.confirm)  { setPwStatus('mismatch'); return }
    setPwStatus('success')
    setPasswords({ current: '', next: '', confirm: '' })
    setTimeout(() => setPwStatus('idle'), 3000)
  }

  //  Notifications
  const toggleNotif = (key: string) => {
    setNotifs(n => {
      const updated = { ...n, [key]: !n[key] }
      localStorage.setItem('notif_prefs', JSON.stringify(updated))  // persistance immédiate
      return updated
    })
  }

  const handleSaveNotifs = () => {
    localStorage.setItem('notif_prefs', JSON.stringify(notifs))
    setNotifSaved(true)
    setTimeout(() => setNotifSaved(false), 3000)
  }

  const activeNotifsCount = Object.values(notifs).filter(Boolean).length

  const initials = `${form.prenom?.[0] || ''}${form.nom?.[0] || ''}` || '?'

  return (
    <div className="flex h-screen bg-[var(--bg)]">
      <Sidebar />
      <div className="ml-[var(--sidebar-w)] flex-1 transition-[margin-left] duration-200 overflow-auto">

        {/* Header */}
        <div className="bg-white px-8 py-6 border-b border-gray-200">
          <h1 className="text-2xl font-extrabold text-gray-900 font-display tracking-tight">Réglages</h1>
          <p className="text-gray-500 text-sm mt-1">Gérez vos préférences et votre compte</p>
        </div>

        <div className="p-8">
          <div className="flex gap-6 max-w-5xl mx-auto">

            {/* Sidebar tabs */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-3 w-56 h-fit">
              {TABS.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setActiveTab(id)}
                  className={`flex items-center gap-3 w-full px-4 py-3 rounded-xl mb-1 text-sm text-left transition-all ${
                    activeTab === id
                      ? 'bg-[var(--nova-600)] text-white font-medium shadow-sm'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <Icon size={16} />
                  {label}
                  {activeTab === id && <ChevronRight size={14} className="ml-auto" />}
                </button>
              ))}
            </div>

            {/* Content */}
            <div className="flex-1">

              {/* PROFIL */}
              {activeTab === 'profil' && (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
                  <h2 className="text-lg font-bold text-gray-900 mb-6">Informations du profil</h2>

                  {/* Avatar */}
                  <div className="flex items-center gap-5 mb-8 p-4 bg-gray-50 rounded-xl">
                    <div className="relative">
                      <div className="w-20 h-20 rounded-full overflow-hidden bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-white text-2xl font-bold shadow-md">
                        {avatar
                          ? <img src={avatar} alt="avatar" className="w-full h-full object-cover" />
                          : <span>{initials}</span>
                        }
                      </div>
                      <label className="absolute -bottom-1 -right-1 bg-[var(--nova-600)] rounded-full p-1.5 cursor-pointer shadow hover:bg-[var(--nova-700)] transition-colors">
                        <Camera size={12} className="text-white" />
                        <input type="file" accept="image/*" onChange={handlePhotoChange} className="hidden" />
                      </label>
                    </div>
                    <div>
                      <p className="font-semibold text-gray-800">
                        {form.prenom || form.nom ? `${form.prenom} ${form.nom}` : 'Votre nom'}
                      </p>
                      <p className="text-gray-500 text-sm">{form.poste || 'Votre poste'}</p>
                      <label className="mt-2 inline-flex items-center gap-1.5 bg-white border border-gray-200 text-gray-600 px-3 py-1.5 rounded-lg text-xs cursor-pointer hover:bg-gray-50 transition-colors">
                        <Camera size={12} />
                        Changer la photo
                        <input type="file" accept="image/*" onChange={handlePhotoChange} className="hidden" />
                      </label>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2 block">Prénom</label>
                      <input
                        value={form.prenom}
                        onChange={e => setForm({ ...form, prenom: e.target.value })}
                        placeholder="Votre prénom"
                        className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-[var(--nova-500)] focus:ring-2 focus:ring-[var(--nova-100)] transition-all"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2 block">Nom</label>
                      <input
                        value={form.nom}
                        onChange={e => setForm({ ...form, nom: e.target.value })}
                        placeholder="Votre nom"
                        className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-[var(--nova-500)] focus:ring-2 focus:ring-[var(--nova-100)] transition-all"
                      />
                    </div>
                  </div>

                  <div className="mb-4">
                    <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2 block flex items-center gap-1.5">
                      <Mail size={12} /> Email
                    </label>
                    <input
                      value={form.email}
                      onChange={e => setForm({ ...form, email: e.target.value })}
                      placeholder="votre@email.com"
                      className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-[var(--nova-500)] focus:ring-2 focus:ring-[var(--nova-100)] transition-all"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-8">
                    <div>
                      <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2 block flex items-center gap-1.5">
                        <Briefcase size={12} /> Poste
                      </label>
                      <input
                        value={form.poste}
                        onChange={e => setForm({ ...form, poste: e.target.value })}
                        placeholder="Directeur commercial..."
                        className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-[var(--nova-500)] focus:ring-2 focus:ring-[var(--nova-100)] transition-all"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2 block flex items-center gap-1.5">
                        <Phone size={12} /> Téléphone
                      </label>
                      <input
                        value={form.telephone}
                        onChange={e => setForm({ ...form, telephone: e.target.value })}
                        placeholder="+216 XX XXX XXX"
                        className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-[var(--nova-500)] focus:ring-2 focus:ring-[var(--nova-100)] transition-all"
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-4 pt-4 border-t border-gray-100">
                    <button
                      onClick={handleSaveProfil}
                      disabled={saveStatus === 'saving'}
                      className="bg-[var(--nova-600)] text-white px-6 py-2.5 rounded-xl text-sm font-medium hover:bg-[var(--nova-700)] disabled:opacity-60 transition-colors"
                    >
                      {saveStatus === 'saving' ? 'Sauvegarde...' : 'Sauvegarder'}
                    </button>
                    {saveStatus === 'success' && (
                      <span className="flex items-center gap-1.5 text-green-600 text-sm font-medium">
                        <Check size={16} /> Profil sauvegardé
                      </span>
                    )}
                    {saveStatus === 'error' && (
                      <span className="flex items-center gap-1.5 text-red-500 text-sm">
                        <X size={16} /> Erreur de sauvegarde
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* SECURITE */}
              {activeTab === 'securite' && (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
                  <h2 className="text-lg font-bold text-gray-900 mb-6">Sécurité</h2>

                  <div className="bg-gray-50 rounded-xl p-6 mb-6">
                    <h3 className="font-semibold text-gray-700 mb-4">Modifier le mot de passe</h3>
                    <div className="space-y-4">
                      <div>
                        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2 block">Mot de passe actuel</label>
                        <input
                          type="password"
                          autoComplete="current-password"
                          value={passwords.current}
                          onChange={e => setPasswords({ ...passwords, current: e.target.value })}
                          className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-[var(--nova-500)] focus:ring-2 focus:ring-[var(--nova-100)] bg-white transition-all"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2 block">Nouveau mot de passe</label>
                        <input
                          type="password"
                          autoComplete="new-password"
                          value={passwords.next}
                          onChange={e => setPasswords({ ...passwords, next: e.target.value })}
                          className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-[var(--nova-500)] focus:ring-2 focus:ring-[var(--nova-100)] bg-white transition-all"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2 block">Confirmer le mot de passe</label>
                        <input
                          type="password"
                          autoComplete="new-password"
                          value={passwords.confirm}
                          onChange={e => setPasswords({ ...passwords, confirm: e.target.value })}
                          className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-[var(--nova-500)] focus:ring-2 focus:ring-[var(--nova-100)] bg-white transition-all"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 pt-2">
                    <button
                      onClick={handleSavePassword}
                      className="bg-[var(--nova-600)] text-white px-6 py-2.5 rounded-xl text-sm font-medium hover:bg-[var(--nova-700)] transition-colors"
                    >
                      Modifier le mot de passe
                    </button>
                    {pwStatus === 'success' && (
                      <span className="flex items-center gap-1.5 text-green-600 text-sm font-medium">
                        <Check size={16} /> Mot de passe modifié
                      </span>
                    )}
                    {pwStatus === 'mismatch' && (
                      <span className="flex items-center gap-1.5 text-red-500 text-sm">
                        <X size={16} /> Les mots de passe ne correspondent pas
                      </span>
                    )}
                    {pwStatus === 'error' && (
                      <span className="flex items-center gap-1.5 text-red-500 text-sm">
                        <X size={16} /> Remplissez tous les champs
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* NOTIFICATIONS */}
              {activeTab === 'notifications' && (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
                  <div className="flex items-start justify-between mb-6">
                    <div>
                      <h2 className="text-lg font-bold text-gray-900">Notifications</h2>
                      <p className="text-gray-500 text-sm mt-0.5">Choisissez les alertes à recevoir</p>
                    </div>
                    <span className="text-xs font-semibold bg-[var(--nova-50)] text-[var(--nova-600)] px-3 py-1.5 rounded-full">
                      {activeNotifsCount}/{NOTIF_ITEMS.length} activées
                    </span>
                  </div>

                  <div className="space-y-3 mb-8">
                    {NOTIF_ITEMS.map(({ key, title, desc, icon: Icon, color, bg }) => {
                      const on = notifs[key]
                      return (
                        <div
                          key={key}
                          onClick={() => toggleNotif(key)}
                          className={`flex items-center justify-between rounded-xl p-4 cursor-pointer border transition-all ${
                            on ? 'border-[var(--nova-200)] bg-[var(--nova-50)]' : 'border-gray-100 bg-white hover:bg-gray-50'
                          }`}
                        >
                          <div className="flex items-center gap-3.5">
                            <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-colors ${on ? bg : 'bg-gray-100'}`}>
                              <Icon size={18} className={on ? color : 'text-gray-400'} />
                            </div>
                            <div>
                              <p className="font-semibold text-sm text-gray-800">{title}</p>
                              <p className="text-gray-400 text-xs mt-0.5">{desc}</p>
                            </div>
                          </div>
                          <button
                            onClick={(e) => { e.stopPropagation(); toggleNotif(key) }}
                            className={`relative flex-shrink-0 w-11 h-6 rounded-full transition-colors duration-200 ${on ? 'bg-[var(--nova-600)]' : 'bg-gray-200'}`}
                          >
                            <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${on ? 'translate-x-6' : 'translate-x-1'}`} />
                          </button>
                        </div>
                      )
                    })}
                  </div>

                  <div className="flex items-center gap-4 pt-4 border-t border-gray-100">
                    <button
                      onClick={handleSaveNotifs}
                      className="bg-[var(--nova-600)] text-white px-6 py-2.5 rounded-xl text-sm font-medium hover:bg-[var(--nova-700)] transition-colors"
                    >
                      Sauvegarder
                    </button>
                    {notifSaved && (
                      <span className="flex items-center gap-1.5 text-emerald-600 text-sm font-medium">
                        <Check size={16} /> Préférences sauvegardées
                      </span>
                    )}
                  </div>
                </div>
              )}

            </div>
          </div>
        </div>
      </div>

    </div>
  )
}

