import axios from 'axios';
import { API_URL, ENDPOINTS } from '../utils/constants';

/**
 * Generate a UUID v4 for idempotency keys.
 * This ensures that retry requests can be safely deduplicated by the backend.
 * @returns {string} UUID v4 string
 */
function generateIdempotencyKey() {
  // Use crypto.randomUUID() if available (modern browsers)
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  // Fallback: Generate UUID v4 manually
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

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
    const errorData = error.response?.data;
    const status = error.response?.status;
    const url = error.config?.url;

    // Format error message for console
    if (errorData) {
      if (status === 422 && Array.isArray(errorData.detail)) {
        // Validation errors - format nicely
        console.error(`API Validation Error (${status}) ${url}:`);
        errorData.detail.forEach((err, index) => {
          const field = err.loc?.slice(-1)[0] || 'unknown';
          const message = err.msg || 'Validation error';
          console.error(`  ${index + 1}. ${field}: ${message}`);
        });
      } else if (errorData.detail) {
        // Single error message
        console.error(`API Error (${status}) ${url}:`, errorData.detail);
      } else {
        // Other error formats
        console.error(`API Error (${status}) ${url}:`, errorData);
      }
    } else {
      // Network or other errors
      console.error('API Error:', error.message || 'Unknown error');
    }

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
    // Generate idempotency key if not provided (UUID v4)
    const requestData = {
      ...data,
      idempotency_key: data.idempotency_key || generateIdempotencyKey(),
    };

    const response = await api.post(ENDPOINTS.APPLICATIONS, requestData);
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

  // Get pending jobs (DB Trigger -> Queue flow)
  getPendingJobs: async (id) => {
    const response = await api.get(ENDPOINTS.APPLICATION_PENDING_JOBS(id));
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
