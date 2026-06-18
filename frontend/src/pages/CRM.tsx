import { useState } from 'react'
import Sidebar from '../components/Navbar'

export default function CRM() {
  const [contacts, setContacts] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({
    name: '',
    email: '',
    company: '',
    job: '',
    segment: 'Enterprise',
    score: 50,
    status: 'Nouveau',
    activity: "A l'instant",
  })

  const handleAdd = () => {
    setContacts([...contacts, form])
    setShowModal(false)
    setForm({ name: '', email: '', company: '', job: '', segment: 'Enterprise', score: 50, status: 'Nouveau', activity: "A l'instant" })
  }

  return (
    <div className="flex h-screen bg-gray-100">
      <Sidebar />
      <div className="ml-64 flex-1 overflow-auto">

        {/* Header */}
        <div className="bg-white p-6 border-b flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">CRM - Gestion des Contacts</h1>
            <p className="text-gray-500 text-sm">Gerez et qualifiez vos contacts avec l'IA</p>
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm"
          >
            Ajouter Contact
          </button>
        </div>

        <div className="p-6">

          {/* KPIs */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-white p-6 rounded-xl shadow-sm border">
              <p className="text-sm font-bold text-gray-600 mb-3">Contacts Totaux</p>
              <p className="text-4xl font-extrabold text-gray-900">{contacts.length}</p>
            </div>
            <div className="bg-white p-6 rounded-xl shadow-sm border">
              <p className="text-sm font-bold text-gray-600 mb-3">Score Moyen</p>
              <p className="text-4xl font-extrabold text-gray-900">
                {contacts.length > 0 ? Math.round(contacts.reduce((a, c) => a + c.score, 0) / contacts.length) : 0}
              </p>
            </div>
            <div className="bg-white p-6 rounded-xl shadow-sm border">
              <p className="text-sm font-bold text-gray-600 mb-3">Qualifies</p>
              <p className="text-4xl font-extrabold text-gray-900">
                {contacts.filter((c: any) => c.status === 'Qualifie').length}
              </p>
            </div>
            <div className="bg-white p-6 rounded-xl shadow-sm border">
              <p className="text-sm font-bold text-gray-600 mb-3">Opportunites</p>
              <p className="text-4xl font-extrabold text-gray-900">
                {contacts.filter((c: any) => c.status === 'Opportunite').length}
              </p>
            </div>
          </div>

          {/* Filters */}
          <div className="bg-white p-4 rounded-xl shadow-sm border mb-6 flex items-center gap-4">
            <select className="border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none">
              <option>Tous les segments</option>
              <option>Enterprise</option>
              <option>PME</option>
              <option>Startup</option>
            </select>
            <select className="border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none">
              <option>Tous les scores</option>
              <option>Score 80+</option>
              <option>Score 60-80</option>
              <option>Score -60</option>
            </select>
            <button className="text-blue-600 text-sm">
              Suggestions IA
            </button>
          </div>

          {/* Contacts Table */}
          <div className="bg-white rounded-xl shadow-sm border">
            {contacts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                <p className="text-sm">Aucun contact disponible</p>
                <p className="text-xs mt-1">Cliquez sur "Ajouter Contact" pour commencer</p>
              </div>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="p-4 text-left text-xs text-gray-500 uppercase">Contact</th>
                    <th className="p-4 text-left text-xs text-gray-500 uppercase">Entreprise</th>
                    <th className="p-4 text-left text-xs text-gray-500 uppercase">Segment</th>
                    <th className="p-4 text-left text-xs text-gray-500 uppercase">Score IA</th>
                    <th className="p-4 text-left text-xs text-gray-500 uppercase">Statut</th>
                    <th className="p-4 text-left text-xs text-gray-500 uppercase">Derniere Activite</th>
                    <th className="p-4 text-left text-xs text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {contacts.map((contact: any, index: number) => (
                    <tr key={index} className="border-t hover:bg-gray-50">
                      <td className="p-4">
                        <p className="font-bold text-sm">{contact.name}</p>
                        <p className="text-gray-400 text-xs">{contact.email}</p>
                      </td>
                      <td className="p-4">
                        <p className="text-sm">{contact.company}</p>
                        <p className="text-gray-400 text-xs">{contact.job}</p>
                      </td>
                      <td className="p-4">
                        <span className="bg-gray-100 text-gray-600 px-3 py-1 rounded-full text-xs">
                          {contact.segment}
                        </span>
                      </td>
                      <td className="p-4">
                        <span className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold ${
                          contact.score >= 90 ? 'bg-green-500' :
                          contact.score >= 75 ? 'bg-blue-500' :
                          'bg-orange-400'
                        }`}>
                          {contact.score}
                        </span>
                      </td>
                      <td className="p-4">
                        <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                          contact.status === 'Opportunite' ? 'bg-orange-100 text-orange-600' :
                          contact.status === 'Qualifie' ? 'bg-purple-100 text-purple-600' :
                          contact.status === 'Prospect' ? 'bg-blue-100 text-blue-600' :
                          'bg-gray-100 text-gray-600'
                        }`}>
                          {contact.status}
                        </span>
                      </td>
                      <td className="p-4 text-gray-500 text-sm">{contact.activity}</td>
                      <td className="p-4">
                        <div className="flex gap-2">
                          <button className="text-gray-400 hover:text-blue-600 text-sm">Email</button>
                          <button className="text-gray-400 hover:text-green-600 text-sm">Tel</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Modal Ajouter Contact */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 w-96 shadow-xl">
            <h2 className="text-xl font-bold mb-6">Ajouter un Contact</h2>

            <div className="mb-4">
              <label className="text-sm text-gray-600 mb-1 block">Nom complet</label>
              <input
                placeholder="Ex: Marie Dubois"
                value={form.name}
                onChange={e => setForm({...form, name: e.target.value})}
                className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:border-blue-500"
              />
            </div>

            <div className="mb-4">
              <label className="text-sm text-gray-600 mb-1 block">Email</label>
              <input
                placeholder="Ex: marie@company.com"
                value={form.email}
                onChange={e => setForm({...form, email: e.target.value})}
                className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:border-blue-500"
              />
            </div>

            <div className="mb-4">
              <label className="text-sm text-gray-600 mb-1 block">Entreprise</label>
              <input
                placeholder="Ex: TechFlow SAS"
                value={form.company}
                onChange={e => setForm({...form, company: e.target.value})}
                className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:border-blue-500"
              />
            </div>

            <div className="mb-4">
              <label className="text-sm text-gray-600 mb-1 block">Poste</label>
              <input
                placeholder="Ex: CEO, CMO..."
                value={form.job}
                onChange={e => setForm({...form, job: e.target.value})}
                className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:border-blue-500"
              />
            </div>

            <div className="mb-4">
              <label className="text-sm text-gray-600 mb-1 block">Segment</label>
              <select
                value={form.segment}
                onChange={e => setForm({...form, segment: e.target.value})}
                className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:border-blue-500"
              >
                <option>Enterprise</option>
                <option>PME</option>
                <option>Startup</option>
              </select>
            </div>

            <div className="mb-6">
              <label className="text-sm text-gray-600 mb-1 block">Statut</label>
              <select
                value={form.status}
                onChange={e => setForm({...form, status: e.target.value})}
                className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:border-blue-500"
              >
                <option>Nouveau</option>
                <option>Prospect</option>
                <option>Qualifie</option>
                <option>Opportunite</option>
              </select>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowModal(false)}
                className="flex-1 border border-gray-200 text-gray-600 py-2 rounded-xl text-sm hover:bg-gray-50"
              >
                Annuler
              </button>
              <button
                onClick={handleAdd}
                className="flex-1 bg-blue-600 text-white py-2 rounded-xl text-sm hover:bg-blue-700"
              >
                Ajouter
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}