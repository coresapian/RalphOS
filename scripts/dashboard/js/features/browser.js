/**
 * Browser Preview Feature
 * CDP WebSocket connection and browser automation
 */

import { state } from '../state.js';
import { CONFIG } from '../config.js';
import { api } from '../api.js';

/**
 * Log browser action
 * @param {string} message - Log message
 * @param {string} type - Log type
 */
function browserLog(message, type = 'info') {
  const log = document.getElementById('browserLog');
  const time = new Date().toLocaleTimeString();
  const typeClass = type === 'error' ? 'browser-log-error' :
    type === 'success' ? 'browser-log-success' :
      type === 'url' ? 'browser-log-url' :
        type === 'action' ? 'browser-log-action' : '';

  const entry = document.createElement('div');
  entry.className = 'browser-log-entry';
  entry.innerHTML = `<span class="browser-log-time">[${time}]</span><span class="${typeClass}">${message}</span>`;
  log.appendChild(entry);
  log.scrollTop = log.scrollHeight;
}

/**
 * Update browser status display
 * @param {boolean} connected - Connection status
 * @param {string} text - Status text
 */
function updateBrowserStatus(connected, text) {
  state.browserConnected = connected;
  const dot = document.getElementById('browserStatusDot');
  const statusText = document.getElementById('browserStatusText');
  dot.className = 'browser-status-dot' + (connected ? ' connected' : '');
  statusText.textContent = text || (connected ? 'Connected' : 'Disconnected');
}

/**
 * Start browser session
 */
export async function startBrowserSession() {
  browserLog('🚀 Starting browser session...', 'action');
  updateBrowserStatus(false, 'Starting...');

  document.getElementById('browserLoading').style.display = 'block';
  document.getElementById('browserPlaceholder').style.display = 'none';

  try {
    const data = await api.startBrowser();

    if (data.success) {
      browserLog(`✓ Browser started on port ${data.port}`, 'success');

      // Try WebSocket connection, fall back to polling mode
      try {
        browserLog(`🔌 Attempting WebSocket connection...`, 'action');
        await connectToCDP(data.ws_url);
      } catch (wsError) {
        browserLog(`⚠ WebSocket unavailable, using polling mode`, 'action');
        state.browserConnected = true;
        updateBrowserStatus(true, 'Connected (Polling)');
        document.getElementById('browserLoading').style.display = 'none';

        // Start polling for screenshots
        startScreenshotPolling();
      }

      document.getElementById('startBrowserBtn').style.display = 'none';
      document.getElementById('stopBrowserBtn').style.display = 'inline-block';

      // Auto-navigate to source URL if in PRD modal
      if (state.currentPrdSource && state.currentPrdSource.url) {
        const urlBar = document.getElementById('browserUrlBar');
        urlBar.value = state.currentPrdSource.url;
        setTimeout(() => browserNavigate(), 500);
      }
    } else {
      throw new Error(data.error || 'Failed to start browser');
    }
  } catch (error) {
    browserLog(`❌ Error: ${error.message}`, 'error');
    updateBrowserStatus(false, 'Error');
    document.getElementById('browserLoading').style.display = 'none';
    document.getElementById('browserPlaceholder').style.display = 'block';
  }
}

/**
 * Connect to Chrome DevTools Protocol
 * @param {string} wsUrl - WebSocket URL
 */
async function connectToCDP(wsUrl) {
  return new Promise((resolve, reject) => {
    browserLog(`🔌 Connecting to CDP: ${wsUrl}`, 'action');

    state.browserWs = new WebSocket(wsUrl);

    state.browserWs.onopen = () => {
      browserLog('✓ CDP WebSocket connected', 'success');
      updateBrowserStatus(true, 'Connected');
      document.getElementById('browserLoading').style.display = 'none';

      // Enable page events
      sendCDPCommand('Page.enable');
      sendCDPCommand('Runtime.enable');
      sendCDPCommand('DOM.enable');

      // Start screencast for live preview
      startScreencast();

      resolve();
    };

    state.browserWs.onmessage = (event) => {
      handleCDPMessage(JSON.parse(event.data));
    };

    state.browserWs.onerror = (error) => {
      browserLog(`❌ WebSocket error: ${error?.message || 'Connection failed'}`, 'error');
      browserLog(`⚠ This may be due to browser security restrictions on localhost WebSocket connections`, 'error');
      updateBrowserStatus(false, 'Error');
      reject(error);
    };

    state.browserWs.onclose = () => {
      browserLog('🔌 WebSocket disconnected', 'action');
      updateBrowserStatus(false, 'Disconnected');
      state.browserWs = null;
      state.screencastEnabled = false;
    };
  });
}

/**
 * Send CDP command
 * @param {string} method - CDP method
 * @param {Object} params - Command parameters
 */
function sendCDPCommand(method, params = {}) {
  if (!state.browserWs || state.browserWs.readyState !== WebSocket.OPEN) {
    browserLog('❌ Not connected to browser', 'error');
    return Promise.reject(new Error('Not connected'));
  }

  const id = state.cdpCommandId++;

  return new Promise((resolve, reject) => {
    state.cdpCallbacks[id] = { resolve, reject };

    state.browserWs.send(JSON.stringify({
      id,
      method,
      params
    }));
  });
}

/**
 * Handle CDP message
 * @param {Object} msg - CDP message
 */
function handleCDPMessage(msg) {
  // Handle command responses
  if (msg.id && state.cdpCallbacks[msg.id]) {
    if (msg.error) {
      state.cdpCallbacks[msg.id].reject(new Error(msg.error.message));
    } else {
      state.cdpCallbacks[msg.id].resolve(msg.result);
    }
    delete state.cdpCallbacks[msg.id];
    return;
  }

  // Handle events
  if (msg.method) {
    switch (msg.method) {
      case 'Page.screencastFrame':
        handleScreencastFrame(msg.params);
        break;
      case 'Page.loadEventFired':
        browserLog('✓ Page loaded', 'success');
        break;
      case 'Page.frameNavigated':
        if (msg.params.frame.url) {
          document.getElementById('browserUrlBar').value = msg.params.frame.url;
          browserLog(`→ Navigated to: ${msg.params.frame.url}`, 'url');
        }
        break;
    }
  }
}

/**
 * Start screencast
 */
function startScreencast() {
  if (state.screencastEnabled) return;

  sendCDPCommand('Page.startScreencast', {
    format: 'jpeg',
    quality: 60,
    maxWidth: 1200,
    maxHeight: 800,
    everyNthFrame: 2
  }).then(() => {
    state.screencastEnabled = true;
    browserLog('📺 Screencast started', 'success');
  }).catch(err => {
    browserLog(`❌ Screencast error: ${err.message}`, 'error');
  });
}

/**
 * Handle screencast frame
 * @param {Object} params - Frame parameters
 */
function handleScreencastFrame(params) {
  const img = document.getElementById('browserScreenshot');
  const placeholder = document.getElementById('browserPlaceholder');
  const loading = document.getElementById('browserLoading');

  img.src = 'data:image/jpeg;base64,' + params.data;
  img.style.display = 'block';
  placeholder.style.display = 'none';
  loading.style.display = 'none';

  // Acknowledge the frame
  sendCDPCommand('Page.screencastFrameAck', {
    sessionId: params.sessionId
  });
}

/**
 * Start screenshot polling (fallback mode)
 */
function startScreenshotPolling() {
  if (state.screenshotPollingInterval) return;

  browserLog('📸 Starting screenshot polling mode', 'action');

  takePolledScreenshot();

  state.screenshotPollingInterval = setInterval(takePolledScreenshot, CONFIG.SCREENSHOT_POLL_INTERVAL);
}

/**
 * Stop screenshot polling
 */
function stopScreenshotPolling() {
  if (state.screenshotPollingInterval) {
    clearInterval(state.screenshotPollingInterval);
    state.screenshotPollingInterval = null;
  }
}

/**
 * Take polled screenshot
 */
async function takePolledScreenshot() {
  try {
    const data = await api.browserScreenshot();

    if (data.success && data.screenshot) {
      const img = document.getElementById('browserScreenshot');
      const placeholder = document.getElementById('browserPlaceholder');
      const loading = document.getElementById('browserLoading');

      img.src = `data:image/jpeg;base64,${data.screenshot}`;
      img.style.display = 'block';
      placeholder.style.display = 'none';
      loading.style.display = 'none';
    }
  } catch (err) {
    // Silent fail for polling
  }
}

/**
 * Stop browser session
 */
export async function stopBrowserSession() {
  browserLog('⏹ Stopping browser session...', 'action');

  // Stop screencast if running
  if (state.screencastEnabled) {
    await sendCDPCommand('Page.stopScreencast').catch(() => { });
    state.screencastEnabled = false;
  }

  // Stop screenshot polling
  stopScreenshotPolling();

  if (state.browserWs) {
    state.browserWs.close();
    state.browserWs = null;
  }

  state.browserConnected = false;

  // Tell backend to stop browser
  try {
    await api.stopBrowser();
  } catch (e) {
    console.error('Error stopping browser:', e);
  }

  updateBrowserStatus(false, 'Stopped');
  document.getElementById('browserScreenshot').style.display = 'none';
  document.getElementById('browserPlaceholder').style.display = 'block';
  document.getElementById('startBrowserBtn').style.display = 'inline-block';
  document.getElementById('stopBrowserBtn').style.display = 'none';
  browserLog('✓ Browser session stopped', 'success');
}

/**
 * Navigate browser to URL
 */
export async function browserNavigate() {
  const url = document.getElementById('browserUrlBar').value.trim();
  if (!url) return;

  // Add protocol if missing
  const fullUrl = url.startsWith('http') ? url : 'https://' + url;

  browserLog(`→ Navigating to: ${fullUrl}`, 'action');
  document.getElementById('browserLoading').style.display = 'block';

  try {
    // Try WebSocket first if connected
    if (state.browserWs && state.browserWs.readyState === WebSocket.OPEN) {
      await sendCDPCommand('Page.navigate', { url: fullUrl });
    } else {
      // Use API fallback
      const data = await api.browserNavigate(fullUrl);

      if (data.success) {
        browserLog(`✓ Navigation started`, 'success');
        setTimeout(takePolledScreenshot, 1500);
      } else {
        throw new Error(data.error || 'Navigation failed');
      }
    }
  } catch (error) {
    browserLog(`❌ Navigation error: ${error.message}`, 'error');
  }

  document.getElementById('browserLoading').style.display = 'none';
}

/**
 * Browser back navigation
 */
export async function browserBack() {
  browserLog('← Going back', 'action');
  try {
    const history = await sendCDPCommand('Page.getNavigationHistory');
    if (history.currentIndex > 0) {
      await sendCDPCommand('Page.navigateToHistoryEntry', {
        entryId: history.entries[history.currentIndex - 1].id
      });
    }
  } catch (error) {
    browserLog(`❌ Error: ${error.message}`, 'error');
  }
}

/**
 * Browser forward navigation
 */
export async function browserForward() {
  browserLog('→ Going forward', 'action');
  try {
    const history = await sendCDPCommand('Page.getNavigationHistory');
    if (history.currentIndex < history.entries.length - 1) {
      await sendCDPCommand('Page.navigateToHistoryEntry', {
        entryId: history.entries[history.currentIndex + 1].id
      });
    }
  } catch (error) {
    browserLog(`❌ Error: ${error.message}`, 'error');
  }
}

/**
 * Browser refresh
 */
export async function browserRefresh() {
  browserLog('🔄 Refreshing page', 'action');
  try {
    await sendCDPCommand('Page.reload');
  } catch (error) {
    browserLog(`❌ Error: ${error.message}`, 'error');
  }
}

/**
 * Take browser snapshot
 */
export async function browserSnapshot() {
  browserLog('📸 Taking screenshot...', 'action');
  try {
    const result = await sendCDPCommand('Page.captureScreenshot', {
      format: 'png',
      quality: 100
    });

    // Create download link
    const link = document.createElement('a');
    link.href = 'data:image/png;base64,' + result.data;
    link.download = `screenshot_${Date.now()}.png`;
    link.click();

    browserLog('✓ Screenshot saved', 'success');
  } catch (error) {
    browserLog(`❌ Error: ${error.message}`, 'error');
  }
}

/**
 * Execute JavaScript in browser
 */
export async function browserExecuteJS() {
  const js = prompt('Enter JavaScript to execute:');
  if (!js) return;

  browserLog(`⚡ Executing: ${js.substring(0, 50)}...`, 'action');
  try {
    const result = await sendCDPCommand('Runtime.evaluate', {
      expression: js,
      returnByValue: true
    });

    const value = result.result.value;
    browserLog(`✓ Result: ${JSON.stringify(value).substring(0, 200)}`, 'success');
    console.log('JS Result:', value);
  } catch (error) {
    browserLog(`❌ Error: ${error.message}`, 'error');
  }
}

/**
 * Extract DOM structure
 */
export async function browserExtractDOM() {
  browserLog('📄 Extracting DOM structure...', 'action');
  try {
    const doc = await sendCDPCommand('DOM.getDocument', { depth: -1 });

    // Get outer HTML
    const html = await sendCDPCommand('DOM.getOuterHTML', {
      nodeId: doc.root.nodeId
    });

    // Save to file via API
    const data = await api.browserSaveDom(html.outerHTML, document.getElementById('browserUrlBar').value);
    browserLog(`✓ DOM saved to: ${data.path}`, 'success');
  } catch (error) {
    browserLog(`❌ Error: ${error.message}`, 'error');
  }
}

// Make functions available globally for onclick handlers
window.startBrowserSession = startBrowserSession;
window.stopBrowserSession = stopBrowserSession;
window.browserNavigate = browserNavigate;
window.browserBack = browserBack;
window.browserForward = browserForward;
window.browserRefresh = browserRefresh;
window.browserSnapshot = browserSnapshot;
window.browserExecuteJS = browserExecuteJS;
window.browserExtractDOM = browserExtractDOM;

export default {
  startBrowserSession,
  stopBrowserSession,
  browserNavigate,
  browserBack,
  browserForward,
  browserRefresh,
  browserSnapshot,
  browserExecuteJS,
  browserExtractDOM
};
