/**
 * API Communication Layer
 * All HTTP requests to the dashboard server
 */

import { CONFIG } from './config.js';

const { API_BASE } = CONFIG;

/**
 * Generic fetch wrapper with error handling
 */
async function fetchAPI(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    },
    ...options
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Dashboard API
 */
export const api = {
  // Status
  async getStatus() {
    return fetchAPI('/status');
  },

  // Logs
  async getLog(lines = CONFIG.LOG_LINES) {
    return fetchAPI(`/log/fresh?lines=${lines}`);
  },

  // Ralph Control
  async startRalph(config) {
    return fetchAPI('/ralph/start', {
      method: 'POST',
      body: JSON.stringify(config)
    });
  },

  async stopRalph() {
    return fetchAPI('/ralph/stop', {
      method: 'POST'
    });
  },

  async getRalphStatus() {
    return fetchAPI('/ralph/status');
  },

  async killAllRalphs() {
    return fetchAPI('/ralph/kill-all', {
      method: 'POST'
    });
  },

  // Source Control
  async retrySource(sourceId) {
    return fetchAPI(`/source/${sourceId}/retry`, {
      method: 'POST'
    });
  },

  // Error Analysis
  async analyzeError(data) {
    return fetchAPI('/analyze-error', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },

  // PRD Operations
  async checkPrdFile(filename) {
    return fetchAPI('/prd/check-file', {
      method: 'POST',
      body: JSON.stringify({ filename })
    });
  },

  async analyzeDomain(data) {
    return fetchAPI('/prd/analyze-domain', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },

  async generatePrdFromAnalysis(data) {
    return fetchAPI('/prd/generate-from-analysis', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },

  async generatePrd(data) {
    return fetchAPI('/prd/generate', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },

  async savePrd(prd) {
    return fetchAPI('/prd/save', {
      method: 'POST',
      body: JSON.stringify({ prd })
    });
  },

  // Browser Control
  async startBrowser() {
    return fetchAPI('/browser/start', {
      method: 'POST'
    });
  },

  async stopBrowser() {
    return fetchAPI('/browser/stop', {
      method: 'POST'
    });
  },

  async browserNavigate(url) {
    return fetchAPI('/browser/navigate', {
      method: 'POST',
      body: JSON.stringify({ url })
    });
  },

  async browserScreenshot() {
    return fetchAPI('/browser/screenshot');
  },

  async browserSaveDom(html, url) {
    return fetchAPI('/browser/save-dom', {
      method: 'POST',
      body: JSON.stringify({ html, url })
    });
  }
};

export default api;
