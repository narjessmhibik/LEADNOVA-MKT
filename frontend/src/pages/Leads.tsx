import { useEffect, useState, useCallback } from 'react'
import Sidebar from '../components/Navbar'
import { getLeads, updateLeadStatus, convertLeadToOpportunity } from '../services/api'
import { Search, Filter, ChevronLeft, ChevronRight, Mail, Phone, Globe, ArrowRightCircle, Check } from 'lucide-react'

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
  'Informatique & Tech', 'Finance & Comptabilité', 'Santé', 'Immobilier',
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

  const [converting, setConverting] = useState<number | null>(null)
  const [converted, setConverted] = useState<number[]>([])
  const [convertMsg, setConvertMsg] = useState<string | null>(null)

  const handleConvert = async (lead: Lead) => {
    setConverting(lead.id)
    try {
      const res = await convertLeadToOpportunity(lead.id)
      setConverted(prev => [...prev, lead.id])
      setConvertMsg(`${lead.company || 'Lead'} converti en opportunité (${res.data.value.toLocaleString('fr')} TND)`)
      setTimeout(() => setConvertMsg(null), 4000)
    } catch (e: any) {
      setConvertMsg(e.response?.data?.detail || 'Erreur lors de la conversion')
      setTimeout(() => setConvertMsg(null), 4000)
    } finally {
      setConverting(null)
    }
  }

  const scoreColor = (score: number | null) => {
    if (!score) return 'text-gray-400'
    if (score >= 66) return 'text-red-600 font-bold'
    if (score >= 33) return 'text-orange-500 font-semibold'
    return 'text-blue-500'
  }

  return (
    <div className="flex h-screen bg-gray-100">
      <Sidebar />

      {/* Toast conversion */}
      {convertMsg && (
        <div className="fixed top-5 left-1/2 -translate-x-1/2 z-50 bg-white border border-indigo-200 shadow-lg rounded-xl px-4 py-3 flex items-center gap-2 text-sm font-medium text-gray-800 animate-fade-in">
          <ArrowRightCircle size={16} className="text-indigo-500" />
          {convertMsg}
        </div>
      )}

      <div className="ml-52 flex-1 overflow-auto min-w-0">

        {/* Header */}
        <div className="bg-white p-6 border-b sticky top-0 z-10">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-800">Leads</h1>
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
                className="border rounded-lg px-3 py-2 text-sm flex-1 outline-none focus:border-blue-400"
              />
              <button
                onClick={handleSearch}
                className="bg-blue-600 text-white px-3 py-2 rounded-lg hover:bg-blue-700"
              >
                <Search size={16} />
              </button>
            </div>

            {/* Segment */}
            <select
              value={segment}
              onChange={e => handleFilter('segment', e.target.value)}
              className="border rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400"
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
              className="border rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400"
            >
              <option value="">Tous les secteurs</option>
              {SECTORS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>

            {/* Email */}
            <select
              value={hasEmail}
              onChange={e => handleFilter('hasEmail', e.target.value)}
              className="border rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400"
            >
              <option value="">Email : tous</option>
              <option value="true">Avec email</option>
              <option value="false">Sans email</option>
            </select>

            {/* Statut */}
            <select
              value={status}
              onChange={e => handleFilter('status', e.target.value)}
              className="border rounded-lg px-3 py-2 text-sm outline-none focus:border-blue-400"
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
                      <th className="p-3 text-left text-gray-500 font-medium">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data?.items.length === 0 ? (
                      <tr>
                        <td colSpan={9} className="text-center py-16 text-gray-400">
                          Aucun lead trouvé
                        </td>
                      </tr>
                    ) : (
                      data?.items.map((lead) => (
                        <tr key={lead.id} className="border-t hover:bg-gray-50 transition-colors">
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
                              <span title="Site web" className={`w-5 h-5 rounded-full flex items-center justify-center text-white text-xs ${lead.website ? 'bg-blue-500' : 'bg-gray-200'}`}>
                                W
                              </span>
                            </div>
                          </td>

                          {/* Statut */}
                          <td className="p-3">
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

                          {/* Action : conversion en opportunité */}
                          <td className="p-3">
                            {converted.includes(lead.id) || lead.status === 'converti' ? (
                              <span className="inline-flex items-center gap-1 text-xs text-purple-600 font-medium">
                                <Check size={13} /> Converti
                              </span>
                            ) : (
                              <button
                                onClick={() => handleConvert(lead)}
                                disabled={converting === lead.id}
                                title="Convertir ce lead en opportunité (pipeline Sales)"
                                className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg border border-indigo-200 text-indigo-600 hover:bg-indigo-50 disabled:opacity-50 transition-colors whitespace-nowrap"
                              >
                                <ArrowRightCircle size={13} />
                                {converting === lead.id ? '...' : 'Convertir'}
                              </button>
                            )}
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
    </div>
  )
}
