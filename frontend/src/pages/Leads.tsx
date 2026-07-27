import { useEffect, useState, useCallback, type ReactNode } from 'react'
import Sidebar from '../components/Navbar'
import { getLeads, updateLeadStatus } from '../services/api'
import { Search, Filter, ChevronLeft, ChevronRight, Mail, Phone, Globe, MapPin, Building2, ExternalLink, X, Tag, Radar } from 'lucide-react'

interface Lead {
  id: number
  company: string
  first_name: string | null
  last_name: string | null
  email: string | null
  phone: string | null
  website: string | null
  sector: string | null
  region: string | null
  status: string
  source: string | null
  lead_score: number | null
  segment: string | null
  company_type: string | null
  enriched: boolean
}

interface LeadsResponse {
  total: number
  page: number
  pages: number
  items: Lead[]
}

const SEGMENT_COLORS: Record<string, string> = {
  Chaud: 'bg-red-100 text-red-700',
  'Prêts à Acheter': 'bg-orange-100 text-orange-700',
  Froid: 'bg-blue-100 text-blue-700',
  'À Risque': 'bg-yellow-100 text-yellow-700',
}

const STATUS_COLORS: Record<string, string> = {
  new:       'bg-gray-100 text-gray-600',
  'nouveau': 'bg-gray-100 text-gray-600',
  'contacté':'bg-blue-100 text-blue-700',
  'qualifié':'bg-green-100 text-green-700',
  'converti':'bg-purple-100 text-purple-700',
  'perdu':   'bg-red-100 text-red-700',
}

const SECTORS = [
  'Culture & Musées', 'Informatique & Tech', 'Finance & Comptabilité', 'Santé', 'Immobilier',
  'Construction & BTP', 'Transport & Logistique', 'Education & Formation',
  'Restauration & Hôtellerie', 'Industrie & Production', 'Commerce & Distribution',
  'Services aux entreprises', 'Agriculture & Alimentaire', 'Energie & Environnement',
  'Juridique', 'Marketing & Communication',
]

export default function Leads() {
  const [data, setData] = useState<LeadsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [segment, setSegment] = useState('')
  const [sector, setSector] = useState('')
  const [hasEmail, setHasEmail] = useState('')
  const [status, setStatus] = useState('')

  const fetchLeads = useCallback(() => {
    setLoading(true)
    const params: Record<string, string | number | boolean> = { page, limit: 50 }
    if (search) params.search = search
    if (segment) params.segment = segment
    if (sector) params.sector = sector
    if (hasEmail === 'true') params.has_email = true
    if (hasEmail === 'false') params.has_email = false
    if (status) params.status = status

    getLeads(params)
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [page, search, segment, sector, hasEmail, status])

  useEffect(() => { fetchLeads() }, [fetchLeads])

  const handleSearch = () => {
    setSearch(searchInput)
    setPage(1)
  }

  const handleFilter = (key: string, value: string) => {
    if (key === 'segment') { setSegment(value); setPage(1) }
    if (key === 'sector') { setSector(value); setPage(1) }
    if (key === 'hasEmail') { setHasEmail(value); setPage(1) }
    if (key === 'status') { setStatus(value); setPage(1) }
  }

  const handleStatusChange = async (id: number, status: string) => {
    await updateLeadStatus(id, status)
    fetchLeads()
  }

  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)

  const normalizeUrl = (url: string) => url.startsWith('http') ? url : `https://${url}`

  const scoreColor = (score: number | null) => {
    if (!score) return 'text-gray-400'
    if (score >= 66) return 'text-red-600 font-bold'
    if (score >= 33) return 'text-orange-500 font-semibold'
    return 'text-blue-500'
  }

  return (
    <div className="flex h-screen bg-[var(--bg)]">
      <Sidebar />

      <div className="ml-[var(--sidebar-w)] flex-1 transition-[margin-left] duration-200 overflow-auto min-w-0">

        {/* Header */}
        <div className="bg-white p-6 border-b sticky top-0 z-10">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h1 className="text-2xl font-extrabold text-gray-900 font-display tracking-tight">Prospects</h1>
              <p className="text-gray-500 text-sm">
                {data?.total.toLocaleString() ?? '...'} résultats
              </p>
            </div>
          </div>

          {/* Filtres */}
          <div className="flex gap-3 flex-wrap">
            {/* Recherche */}
            <div className="flex gap-2 flex-1 min-w-[240px]">
              <input
                type="text"
                placeholder="Rechercher entreprise, email, téléphone..."
                value={searchInput}
                onChange={e => setSearchInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                className="border rounded-lg px-3 py-2 text-sm flex-1 outline-none focus:border-[var(--nova-400)]"
              />
              <button
                onClick={handleSearch}
                className="bg-[var(--nova-600)] text-white px-3 py-2 rounded-lg hover:bg-[var(--nova-700)]"
              >
                <Search size={16} />
              </button>
            </div>

            {/* Segment */}
            <select
              value={segment}
              onChange={e => handleFilter('segment', e.target.value)}
              className="border rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--nova-400)]"
            >
              <option value="">Tous les segments</option>
              <option value="Chaud">Chaud</option>
              <option value="Prêts à Acheter">Prêts à Acheter</option>
              <option value="Froid">Froid</option>
              <option value="À Risque">À Risque</option>
            </select>

            {/* Secteur */}
            <select
              value={sector}
              onChange={e => handleFilter('sector', e.target.value)}
              className="border rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--nova-400)]"
            >
              <option value="">Tous les secteurs</option>
              {SECTORS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>

            {/* Email */}
            <select
              value={hasEmail}
              onChange={e => handleFilter('hasEmail', e.target.value)}
              className="border rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--nova-400)]"
            >
              <option value="">Email : tous</option>
              <option value="true">Avec email</option>
              <option value="false">Sans email</option>
            </select>

            {/* Statut */}
            <select
              value={status}
              onChange={e => handleFilter('status', e.target.value)}
              className="border rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--nova-400)]"
            >
              <option value="">Tous les statuts</option>
              <option value="new">Nouveau</option>
              <option value="contacté">Contacté</option>
              <option value="qualifié">Qualifié</option>
              <option value="converti">Converti</option>
              <option value="perdu">Perdu</option>
            </select>

            {/* Reset */}
            {(search || segment || sector || hasEmail || status) && (
              <button
                onClick={() => {
                  setSearch(''); setSearchInput(''); setSegment('')
                  setSector(''); setHasEmail(''); setPage(1)
                }}
                className="text-sm text-gray-500 hover:text-red-500 flex items-center gap-1 px-2"
              >
                <Filter size={14} /> Réinitialiser
              </button>
            )}
          </div>
        </div>

        {/* Table */}
        <div className="p-6">
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            {loading ? (
              <div className="flex items-center justify-center py-20 text-gray-400">Chargement...</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b">
                      <th className="p-3 text-left text-gray-500 font-medium">Entreprise</th>
                      <th className="p-3 text-left text-gray-500 font-medium">Contact</th>
                      <th className="p-3 text-left text-gray-500 font-medium">Secteur</th>
                      <th className="p-3 text-left text-gray-500 font-medium">Région</th>
                      <th className="p-3 text-left text-gray-500 font-medium">Segment</th>
                      <th className="p-3 text-left text-gray-500 font-medium">Score</th>
                      <th className="p-3 text-left text-gray-500 font-medium">Joignabilité</th>
                      <th className="p-3 text-left text-gray-500 font-medium">Statut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data?.items.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="text-center py-16 text-gray-400">
                          Aucun lead trouvé
                        </td>
                      </tr>
                    ) : (
                      data?.items.map((lead) => (
                        <tr key={lead.id}
                          onClick={() => setSelectedLead(lead)}
                          className="border-t hover:bg-[var(--nova-50)]/60 transition-colors cursor-pointer">
                          {/* Entreprise */}
                          <td className="p-3">
                            <p className="font-semibold text-gray-900">{lead.company || '—'}</p>
                            {lead.company_type && (
                              <span className="text-xs text-gray-400">{lead.company_type}</span>
                            )}
                          </td>

                          {/* Contact */}
                          <td className="p-3">
                            {(lead.first_name || lead.last_name) && (
                              <p className="text-gray-700">{lead.first_name} {lead.last_name}</p>
                            )}
                            {lead.email && (
                              <p className="text-xs text-gray-500 flex items-center gap-1">
                                <Mail size={10} /> {lead.email}
                              </p>
                            )}
                            {lead.phone && (
                              <p className="text-xs text-gray-500 flex items-center gap-1">
                                <Phone size={10} /> {lead.phone}
                              </p>
                            )}
                          </td>

                          {/* Secteur */}
                          <td className="p-3">
                            <span className="text-gray-700">{lead.sector || '—'}</span>
                          </td>

                          {/* Région */}
                          <td className="p-3 text-gray-600">{lead.region || '—'}</td>

                          {/* Segment */}
                          <td className="p-3">
                            {lead.segment ? (
                              <span className={`px-2 py-1 rounded-full text-xs font-medium ${SEGMENT_COLORS[lead.segment] ?? 'bg-gray-100 text-gray-600'}`}>
                                {lead.segment}
                              </span>
                            ) : '—'}
                          </td>

                          {/* Score XGBoost */}
                          <td className={`p-3 text-sm ${scoreColor(lead.lead_score)}`}>
                            {lead.lead_score ? `${lead.lead_score.toFixed(1)}` : '—'}
                          </td>

                          {/* Joignabilité */}
                          <td className="p-3">
                            <div className="flex gap-1">
                              <span title="Email" className={`w-5 h-5 rounded-full flex items-center justify-center text-white text-xs ${lead.email ? 'bg-green-500' : 'bg-gray-200'}`}>
                                @
                              </span>
                              <span title="Téléphone" className={`w-5 h-5 rounded-full flex items-center justify-center text-white text-xs ${lead.phone ? 'bg-purple-500' : 'bg-gray-200'}`}>
                                T
                              </span>
                              {lead.website ? (
                                <a
                                  href={normalizeUrl(lead.website)}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={e => e.stopPropagation()}
                                  title={`Ouvrir ${lead.website}`}
                                  className="w-5 h-5 rounded-full flex items-center justify-center text-white text-xs bg-blue-500 hover:bg-blue-600 transition-colors"
                                >
                                  W
                                </a>
                              ) : (
                                <span title="Pas de site web" className="w-5 h-5 rounded-full flex items-center justify-center text-white text-xs bg-gray-200">
                                  W
                                </span>
                              )}
                            </div>
                          </td>

                          {/* Statut */}
                          <td className="p-3" onClick={e => e.stopPropagation()}>
                            <select
                              value={lead.status}
                              onChange={e => handleStatusChange(lead.id, e.target.value)}
                              className={`text-xs px-2 py-1 rounded-full border-0 cursor-pointer font-medium ${STATUS_COLORS[lead.status] ?? 'bg-gray-100 text-gray-600'}`}
                            >
                              <option value="new">Nouveau</option>
                              <option value="contacté">Contacté</option>
                              <option value="qualifié">Qualifié</option>
                              <option value="converti">Converti</option>
                              <option value="perdu">Perdu</option>
                            </select>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            {data && data.pages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50">
                <p className="text-sm text-gray-500">
                  Page {data.page} sur {data.pages} &nbsp;·&nbsp; {data.total.toLocaleString()} résultats
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="p-2 rounded-lg border hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <button
                    onClick={() => setPage(p => Math.min(data.pages, p + 1))}
                    disabled={page === data.pages}
                    className="p-2 rounded-lg border hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Panneau détail du prospect */}
      {selectedLead && (
        <>
          <div className="fixed inset-0 bg-black/30 z-40 animate-fade-in" onClick={() => setSelectedLead(null)} />
          <aside className="fixed top-0 right-0 h-screen w-[400px] max-w-[92vw] bg-white shadow-2xl z-50 overflow-y-auto animate-fade-in border-l border-[var(--border)]">
            {/* Header */}
            <div className="sticky top-0 bg-white border-b border-[var(--border)] px-6 py-5 flex items-start justify-between">
              <div className="flex items-start gap-3 min-w-0">
                <div className="w-11 h-11 rounded-xl nova-mark flex items-center justify-center flex-shrink-0">
                  <Building2 size={20} className="text-white" />
                </div>
                <div className="min-w-0">
                  <h2 className="text-lg font-extrabold text-gray-900 font-display tracking-tight truncate">
                    {selectedLead.company || '—'}
                  </h2>
                  {selectedLead.company_type && (
                    <span className="text-xs text-gray-400">{selectedLead.company_type}</span>
                  )}
                </div>
              </div>
              <button onClick={() => setSelectedLead(null)} className="text-gray-400 hover:text-gray-700 p-1 -mr-1 flex-shrink-0">
                <X size={18} />
              </button>
            </div>

            <div className="p-6 space-y-5">
              {/* Score + Segment */}
              <div className="flex gap-3">
                <div className="flex-1 rounded-xl border border-[var(--border)] p-3.5 text-center">
                  <p className={`text-2xl font-extrabold tabular-nums ${scoreColor(selectedLead.lead_score)}`}>
                    {selectedLead.lead_score != null ? selectedLead.lead_score.toFixed(1) : '—'}
                  </p>
                  <p className="text-[11px] text-gray-400 font-medium mt-0.5">Score IA</p>
                </div>
                <div className="flex-1 rounded-xl border border-[var(--border)] p-3.5 text-center flex flex-col items-center justify-center">
                  {selectedLead.segment ? (
                    <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${SEGMENT_COLORS[selectedLead.segment] ?? 'bg-gray-100 text-gray-600'}`}>
                      {selectedLead.segment}
                    </span>
                  ) : <span className="text-gray-300 text-sm">—</span>}
                  <p className="text-[11px] text-gray-400 font-medium mt-1.5">Segment</p>
                </div>
              </div>

              {/* Coordonnées */}
              <div className="space-y-1">
                <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wide mb-2">Coordonnées</p>
                <DetailRow icon={<Mail size={15} />} label="Email"
                  value={selectedLead.email}
                  href={selectedLead.email ? `mailto:${selectedLead.email}` : undefined} />
                <DetailRow icon={<Phone size={15} />} label="Téléphone"
                  value={selectedLead.phone}
                  href={selectedLead.phone ? `tel:${selectedLead.phone}` : undefined} />
                <DetailRow icon={<Globe size={15} />} label="Site web"
                  value={selectedLead.website}
                  href={selectedLead.website ? normalizeUrl(selectedLead.website) : undefined}
                  external />
              </div>

              {/* Classification */}
              <div className="space-y-1">
                <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wide mb-2">Classification</p>
                <DetailRow icon={<Tag size={15} />}    label="Secteur" value={selectedLead.sector} />
                <DetailRow icon={<MapPin size={15} />} label="Région"  value={selectedLead.region} />
                <DetailRow icon={<Radar size={15} />}  label="Source"  value={selectedLead.source} />
              </div>

              {/* Statut */}
              <div>
                <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wide mb-2">Statut</p>
                <select
                  value={selectedLead.status}
                  onChange={e => {
                    handleStatusChange(selectedLead.id, e.target.value)
                    setSelectedLead({ ...selectedLead, status: e.target.value })
                  }}
                  className={`text-xs px-3 py-1.5 rounded-full border-0 cursor-pointer font-semibold ${STATUS_COLORS[selectedLead.status] ?? 'bg-gray-100 text-gray-600'}`}
                >
                  <option value="new">Nouveau</option>
                  <option value="contacté">Contacté</option>
                  <option value="qualifié">Qualifié</option>
                  <option value="converti">Converti</option>
                  <option value="perdu">Perdu</option>
                </select>
              </div>
            </div>
          </aside>
        </>
      )}
    </div>
  )
}

function DetailRow({ icon, label, value, href, external }: {
  icon: ReactNode; label: string; value?: string | null; href?: string; external?: boolean
}) {
  return (
    <div className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
      <span className="text-[var(--ink-faint)] flex-shrink-0">{icon}</span>
      <span className="text-[12px] text-gray-400 w-20 flex-shrink-0">{label}</span>
      {value ? (
        href ? (
          <a href={href} target={external ? '_blank' : undefined} rel={external ? 'noopener noreferrer' : undefined}
            className="text-[13px] font-medium text-[var(--nova-600)] hover:underline truncate flex items-center gap-1 min-w-0">
            <span className="truncate">{value}</span>
            {external && <ExternalLink size={11} className="flex-shrink-0" />}
          </a>
        ) : (
          <span className="text-[13px] font-medium text-gray-800 truncate">{value}</span>
        )
      ) : (
        <span className="text-[13px] text-gray-300">—</span>
      )}
    </div>
  )
}

