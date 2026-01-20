/**
 * Ralph Feature
 * Ralph agent controls and status
 */

import { state } from '../state.js';
import { CONFIG } from '../config.js';
import { api } from '../api.js';
import { showToast } from '../components/notifications.js';
import { updateDashboard } from './dashboard.js';

/**
 * Start Ralph with configuration
 */
export async function startRalph() {
  const iterations = parseInt(document.getElementById('ralphIterations').value) || 25;
  const sourceSelect = document.getElementById('ralphSource');
  const selectedSources = Array.from(sourceSelect.selectedOptions).map(o => o.value).filter(v => v);

  const config = {
    iterations: iterations,
    sources: selectedSources
  };

  try {
    const data = await api.startRalph(config);

    if (data.success) {
      updateRalphUI(true, data.pid);
    } else {
      alert('Failed to start Ralph: ' + (data.error || 'Unknown error'));
    }
  } catch (error) {
    alert('Error starting Ralph: ' + error.message);
  }
}

/**
 * Stop Ralph
 */
export async function stopRalph() {
  try {
    const data = await api.stopRalph();
    updateRalphUI(false);
  } catch (error) {
    alert('Error stopping Ralph: ' + error.message);
  }
}

/**
 * Update Ralph UI state
 * @param {boolean} running - Is Ralph running
 * @param {string} pid - Process ID if running
 */
export function updateRalphUI(running, pid = null) {
  const statusDot = document.getElementById('ralphStatusDot');
  const statusDot2 = document.getElementById('ralphStatusDot2');
  const statusText = document.getElementById('ralphStatusText');
  const pidText = document.getElementById('ralphPid');
  const startBtn = document.getElementById('startRalphBtn');
  const stopBtn = document.getElementById('stopRalphBtn');

  if (running) {
    statusDot.className = 'status-dot running';
    statusDot2.className = 'scraper-status-dot running';
    statusText.textContent = 'Running';
    if (pidText) pidText.textContent = pid ? `PID: ${pid}` : '';
    startBtn.style.display = 'none';
    stopBtn.style.display = 'flex';
  } else {
    statusDot.className = 'status-dot stopped';
    statusDot2.className = 'scraper-status-dot stopped';
    statusText.textContent = 'Stopped';
    if (pidText) pidText.textContent = '';
    startBtn.style.display = 'flex';
    stopBtn.style.display = 'none';
  }
}

/**
 * Update Ralph status from server
 */
export async function updateRalphStatus() {
  try {
    const data = await api.getRalphStatus();

    updateRalphUI(data.running, data.pid);

    if (data.prd && data.prd.project) {
      document.getElementById('ralphProject').textContent = data.prd.project;
      document.getElementById('ralphStoryProgress').textContent =
        `Stories: ${data.prd.stories_completed}/${data.prd.stories_total} | Source: ${data.prd.source || 'N/A'}`;
    } else {
      document.getElementById('ralphProject').textContent = 'No active project';
      document.getElementById('ralphStoryProgress').textContent = '--';
    }
  } catch (error) {
    console.error('Failed to fetch Ralph status:', error);
  }
}

/**
 * Kill all Ralph processes
 */
export async function killAllRalphs() {
  const btn = document.getElementById('killAllBtn');
  const originalText = btn.innerHTML;

  btn.classList.add('killing');
  btn.innerHTML = '⏳ Killing...';

  // Add message to log
  const logOutput = document.getElementById('logOutput');
  const killMsg = document.createElement('div');
  killMsg.innerHTML = `<span class="error">[${new Date().toLocaleTimeString()}] ☠ KILL ALL initiated...</span>`;
  logOutput.appendChild(killMsg);
  logOutput.scrollTop = logOutput.scrollHeight;

  try {
    const data = await api.killAllRalphs();

    if (data.success) {
      btn.innerHTML = '🔍 Verifying...';
      verifyAllKilled(btn, originalText);
    } else {
      throw new Error(data.error || 'Unknown error');
    }
  } catch (error) {
    console.error('Kill all failed:', error);
    btn.innerHTML = '❌ Failed - Retry';
  }
}

/**
 * Verify all Ralph processes are killed
 * @param {HTMLElement} btn - Kill button element
 * @param {string} originalText - Original button text
 */
async function verifyAllKilled(btn, originalText) {
  let attempts = 0;

  // Clear any existing interval
  if (state.killCheckInterval) clearInterval(state.killCheckInterval);

  state.killCheckInterval = setInterval(async () => {
    attempts++;

    try {
      const data = await api.getRalphStatus();

      if (!data.running) {
        // All processes confirmed dead
        clearInterval(state.killCheckInterval);
        state.killCheckInterval = null;

        btn.innerHTML = '✓ All Dead';
        btn.classList.remove('killing');
        btn.classList.add('killed-success');

        const logOutput = document.getElementById('logOutput');
        const doneMsg = document.createElement('div');
        doneMsg.innerHTML = `<span class="success">[${new Date().toLocaleTimeString()}] ✓ All Ralph processes terminated</span>`;
        logOutput.appendChild(doneMsg);
        logOutput.scrollTop = logOutput.scrollHeight;

        // Reset button after brief success indication
        setTimeout(() => {
          btn.classList.remove('killed-success');
          btn.innerHTML = originalText;
        }, CONFIG.SUCCESS_INDICATOR_DURATION);

        // Refresh dashboard
        updateDashboard();
      } else if (attempts >= CONFIG.KILL_MAX_ATTEMPTS) {
        // Timeout
        clearInterval(state.killCheckInterval);
        state.killCheckInterval = null;

        btn.innerHTML = '⚠ Check Manually';
        setTimeout(() => {
          btn.classList.remove('killing');
          btn.innerHTML = originalText;
        }, 3000);
      } else {
        btn.innerHTML = `⏳ Killing... (${attempts})`;
      }
    } catch (error) {
      console.error('Status check failed:', error);
    }
  }, CONFIG.KILL_CHECK_INTERVAL);
}

/**
 * Generate PRD using browser analysis
 */
export async function generatePRD() {
  const sourceSelect = document.getElementById('ralphSource');
  const selectedSources = Array.from(sourceSelect.selectedOptions).map(o => o.value).filter(v => v);

  if (selectedSources.length === 0) {
    alert('Please select a source first');
    return;
  }

  if (selectedSources.length > 1) {
    alert('Please select only one source for PRD generation');
    return;
  }

  const sourceId = selectedSources[0];
  const source = state.allSources.find(s => s.id === sourceId);

  if (!source) {
    alert('Source not found');
    return;
  }

  // Show status
  const statusDiv = document.getElementById('prdGenStatus');
  const statusText = document.getElementById('prdGenStatusText');
  statusDiv.style.display = 'block';
  statusText.textContent = `Analyzing ${source.name}...`;

  try {
    const data = await api.generatePrd({
      sourceId: sourceId,
      url: source.url,
      name: source.name,
      useBrowser: true
    });

    if (data.success) {
      statusText.innerHTML = `<span class="success">✓ PRD generated for ${source.name}</span>`;
      setTimeout(() => {
        statusDiv.style.display = 'none';
        updateRalphStatus();
      }, 3000);
    } else {
      statusText.innerHTML = `<span class="error">✗ ${data.error || 'Failed to generate PRD'}</span>`;
    }
  } catch (error) {
    statusText.innerHTML = `<span class="error">✗ Error: ${error.message}</span>`;
  }
}

// Make functions available globally for onclick handlers
window.startRalph = startRalph;
window.stopRalph = stopRalph;
window.killAllRalphs = killAllRalphs;
window.generatePRD = generatePRD;

export default {
  startRalph,
  stopRalph,
  updateRalphStatus,
  updateRalphUI,
  killAllRalphs,
  generatePRD
};
