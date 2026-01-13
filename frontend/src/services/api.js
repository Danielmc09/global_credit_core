import axios from 'axios';
import { API_URL, ENDPOINTS } from '../utils/constants';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
const DEV_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vLXVzZXItZml4IiwiZW1haWwiOiJkZW1vQGV4YW1wbGUuY29tIiwicm9sZSI6ImFkbWluIiwiZXhwIjoxNzk5NzEyMDUzLCJpYXQiOjE3NjgxNzYwNTN9.KuxGwQiupx0IxeCC5LO09I7aGOV3pBWBQYTvn5MOvvU";

// Request interceptor for logging and authentication
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method.toUpperCase()} ${config.url}`);

    // Get token from localStorage or use dev token
    const token = localStorage.getItem('token') || DEV_TOKEN;

    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// Application API calls
export const applicationAPI = {
  // Get all applications with optional filters
  getApplications: async (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.country) params.append('country', filters.country);
    if (filters.status) params.append('status', filters.status);
    if (filters.page) params.append('page', filters.page);
    if (filters.page_size) params.append('page_size', filters.page_size);

    const response = await api.get(`${ENDPOINTS.APPLICATIONS}?${params.toString()}`);
    return response.data;
  },

  // Get single application
  getApplication: async (id) => {
    const response = await api.get(ENDPOINTS.APPLICATION_BY_ID(id));
    return response.data;
  },

  // Create new application
  createApplication: async (data) => {
    const response = await api.post(ENDPOINTS.APPLICATIONS, data);
    return response.data;
  },

  // Update application
  updateApplication: async (id, data) => {
    const response = await api.patch(ENDPOINTS.APPLICATION_BY_ID(id), data);
    return response.data;
  },

  // Delete application
  deleteApplication: async (id) => {
    const response = await api.delete(ENDPOINTS.APPLICATION_BY_ID(id));
    return response.data;
  },

  // Get audit logs
  getAuditLogs: async (id) => {
    const response = await api.get(ENDPOINTS.APPLICATION_AUDIT(id));
    return response.data;
  },

  // Get country statistics
  getCountryStats: async (country) => {
    const response = await api.get(ENDPOINTS.APPLICATION_STATS_COUNTRY(country));
    return response.data;
  },

  // Get supported countries
  getSupportedCountries: async () => {
    const response = await api.get(ENDPOINTS.APPLICATION_SUPPORTED_COUNTRIES);
    return response.data;
  },
};

export default api;
