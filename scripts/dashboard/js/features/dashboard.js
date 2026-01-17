/**
 * Dashboard Feature
 * Main dashboard updates and pipeline stats
 */

import { state } from '../state.js';
import { CONFIG } from '../config.js';
import { api } from '../api.js';
import { formatNumber } from '../utils.js';
import { hideLoadingScreen, updateLoadingStatus } from '../components/loading.js';
import { updateSourcesList, populateSourcesDropdown } from './sources.js';
import { updateLogSourceList, refreshLogNow } from './logs.js';
import { updateRalphStatus } from './ralph.js';
import { checkForErrorsAndAnalyze } from './errors.js';

/**
 * Update pipeline stage display
 * @param {string} id - Stage element ID
 * @param {number} current - Current value
 * @param {number} total - Total value (for completion check)
 */
function updateStage(id, current, total) {
  const stage = document.getElementById(id);
  const valueEl = stage.querySelector('.header-stage-value');

  if (current !== null && current !== undefined && current !== 'null') {
    valueEl.textContent = formatNumber(current);
    if (total && current >= total) {
      stage.className = 'header-stage complete';
    } else if (current > 0) {
      stage.className = 'header-stage active';
    } else {
      stage.className = 'header-stage';
    }
  } else {
    valueEl.textContent = '--';
    stage.className = 'header-stage';
  }
}

/**
 * Main dashboard update function
 */
export async function updateDashboard() {
  try {
    if (state.isInitialLoad) updateLoadingStatus('Fetching data...');

    const data = await api.getStatus();

    // Update status
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    if (data.running) {
      statusDot.className = 'status-dot running';
      statusText.textContent = 'Running';
    } else {
      statusDot.className = 'status-dot stopped';
      statusText.textContent = 'Stopped';
    }

    // Update stats
    document.getElementById('totalSources').textContent = data.sources.total;
    document.getElementById('completedSources').textContent = data.sources.completed;
    document.getElementById('inProgressSources').textContent = data.sources.in_progress;

    // Update pipeline stages
    let totalUrls = 0;
    if (data.all_sources && data.all_sources.length > 0) {
      data.all_sources.forEach(source => {
        const pipeline = source.pipeline || {};
        totalUrls += pipeline.urlsFound || 0;
      });
    }

    const totalHtml = data.html_files || 0;
    const totalBuilds = data.total_builds || data.builds || 0;
    const totalMods = data.total_mods || data.mods || 0;

    updateStage('stage1', totalUrls, null);
    updateStage('stage2', totalHtml, totalUrls);
    updateStage('stage3', totalBuilds, null);
    updateStage('stage4', totalMods, null);

    // Update sources list
    updateSourcesList(data.all_sources || []);

    // Populate Ralph source selector
    if (data.all_sources) {
      state.allSources = data.all_sources;
      populateSourcesDropdown(data.all_sources);
      updateLogSourceList(data.all_sources);

      // Check for errors
      checkForErrorsAndAnalyze(data.all_sources, data.log_tail || []);
    }

    // Update log
    if (state.autoRefreshEnabled) {
      refreshLogNow();
    }

    // Update Ralph status
    updateRalphStatus();

    // Update refresh times
    const now = new Date().toLocaleTimeString();
    document.getElementById('sourcesRefreshText').textContent = `Live · ${now}`;
    document.getElementById('sourcesLiveDot').className = 'live-dot';

    // Hide loading screen on first successful load
    if (state.isInitialLoad) {
      state.isInitialLoad = false;
      hideLoadingScreen();
    }

  } catch (error) {
    console.error('Failed to fetch status:', error);

    document.getElementById('statusDot').className = 'status-dot stopped';
    document.getElementById('statusText').textContent = 'API Offline';
    document.getElementById('sourcesLiveDot').className = 'live-dot error';
    document.getElementById('sourcesRefreshText').textContent = 'Offline';

    // Hide loading after timeout so UI is usable
    if (state.isInitialLoad) {
      updateLoadingStatus('Connecting...');
      setTimeout(() => {
        if (state.isInitialLoad) {
          state.isInitialLoad = false;
          hideLoadingScreen();
        }
      }, 3000);
    }
  }
}

/**
 * Start dashboard refresh interval
 */
export function startDashboardRefresh() {
  updateDashboard();
  setInterval(updateDashboard, CONFIG.REFRESH_INTERVAL);
}

export default {
  updateDashboard,
  startDashboardRefresh
};
