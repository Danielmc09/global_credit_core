// API Configuration
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const API_VERSION = '/api/v1';
export const API_URL = `${API_BASE_URL}${API_VERSION}`;

// WebSocket Configuration
export const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
export const WS_URL = `${WS_BASE_URL}${API_VERSION}/ws`;

// API Endpoints
export const ENDPOINTS = {
  APPLICATIONS: '/applications',
  APPLICATION_BY_ID: (id) => `/applications/${id}`,
  APPLICATION_AUDIT: (id) => `/applications/${id}/audit`,
  APPLICATION_STATS_COUNTRY: (country) => `/applications/stats/country/${country}`,
  APPLICATION_SUPPORTED_COUNTRIES: '/applications/meta/supported-countries',
};

// WebSocket Actions
export const WS_ACTIONS = {
  SUBSCRIBE: 'subscribe',
  UNSUBSCRIBE: 'unsubscribe',
  PING: 'ping',
};

// WebSocket Message Types
export const WS_MESSAGE_TYPES = {
  CONNECTION: 'connection',
  APPLICATION_UPDATE: 'application_update',
  PONG: 'pong',
  SUBSCRIBED: 'subscribed',
};

// Connection Status
export const CONNECTION_STATUS = {
  CONNECTED: 'connected',
  DISCONNECTED: 'disconnected',
  ERROR: 'error',
};
