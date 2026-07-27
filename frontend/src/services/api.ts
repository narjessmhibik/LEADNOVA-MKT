import axios from 'axios'

const API = axios.create({
  baseURL: (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'),
})

API.interceptors.request.use((config) => {
  const token = localStorage.getItem('token') || sessionStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Auth
export const login = (email: string, password: string) =>
  API.post('/auth/login', { email, password })

export const register = (email: string, password: string, full_name: string) =>
  API.post('/auth/register', { email, password, full_name })

// Leads
export interface LeadsParams {
  page?: number
  limit?: number
  search?: string
  segment?: string
  sector?: string
  status?: string
  has_email?: boolean
  source?: string
}

export const getLeads = (params: LeadsParams = {}) =>
  API.get('/leads/', { params })

export const getLeadStats = () =>
  API.get('/leads/stats')

export const getLead = (id: number) =>
  API.get(`/leads/${id}`)

export const updateLeadStatus = (id: number, status: string) =>
  API.put(`/leads/${id}/status`, { status })

export const createLead = (data: object) =>
  API.post('/leads/', data)

// Campaigns
export const getCampaigns = () => API.get('/campaigns/')
export const createCampaign = (data: object) => API.post('/campaigns/', data)

export default API
