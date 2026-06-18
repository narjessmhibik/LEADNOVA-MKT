import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Leads from './pages/Leads'
import Campaigns from './pages/Campaigns'
import Scraping from './pages/Scraping'
import CRM from './pages/CRM'
import Ventes from './pages/Ventes'
import Automation from './pages/Automation'
import Rapports from './pages/Rapports'
import Parametres from './pages/Parametres'

function PrivateRoute({ children }: { children: JSX.Element }) {
  const token = localStorage.getItem('token') || sessionStorage.getItem('token')
  return token ? children : <Navigate to="/" />
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/dashboard" element={
          <PrivateRoute><Dashboard /></PrivateRoute>
        } />
        <Route path="/leads" element={
          <PrivateRoute><Leads /></PrivateRoute>
        } />
        <Route path="/campaigns" element={
          <PrivateRoute><Campaigns /></PrivateRoute>
        } />
        <Route path="/scraping" element={
          <PrivateRoute><Scraping /></PrivateRoute>
        } />
        <Route path="/crm" element={
          <PrivateRoute><CRM /></PrivateRoute>
        } />
        <Route path="/ventes" element={
          <PrivateRoute><Ventes /></PrivateRoute>
        } />
        <Route path="/automation" element={
          <PrivateRoute><Automation /></PrivateRoute>
        } />
        <Route path="/rapports" element={
          <PrivateRoute><Rapports /></PrivateRoute>
        } />
        <Route path="/parametres" element={
          <PrivateRoute><Parametres /></PrivateRoute>
        } />
      </Routes>
    </BrowserRouter>
  )
}

export default App