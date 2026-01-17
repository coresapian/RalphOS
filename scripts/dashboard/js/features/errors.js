/**
 * Error Detection and Analysis
 * LLM-powered error analysis and notifications
 */

import { state } from '../state.js';
import { api } from '../api.js';
import { getDefaultSuggestion } from '../utils.js';
import { addNotification } from '../components/notifications.js';

/**
 * Check for errors and analyze with LLM
 * @param {Array} sources - Source data array
 * @param {Array} logTail - Recent log lines
 */
export async function checkForErrorsAndAnalyze(sources, logTail) {
  for (const source of sources) {
    const prevStatus = state.previousSourceStatuses[source.id];
    const currentStatus = source.status;

    // Check if source just went into error/blocked/hitl state
    if ((currentStatus === 'blocked' || currentStatus === 'error' || currentStatus === 'hitl')
      && prevStatus !== currentStatus) {

      const errorKey = `${source.id}-${currentStatus}-${Date.now().toString().slice(0, -4)}`;

      if (!state.analyzedErrors.has(errorKey)) {
        state.analyzedErrors.add(errorKey);

        // Get relevant log lines for this source
        const relevantLogs = logTail
          .filter(line => line.toLowerCase().includes(source.id.toLowerCase()) ||
            line.toLowerCase().includes(source.name?.toLowerCase() || '') ||
            line.includes('error') || line.includes('Error') ||
            line.includes('blocked') || line.includes('403') || line.includes('429'))
          .slice(-20)
          .join('\n');

        // Analyze with LLM
        analyzeErrorWithLLM(source, relevantLogs, currentStatus);
      }
    }

    // Update tracking
    state.previousSourceStatuses[source.id] = currentStatus;
  }
}

/**
 * Analyze error with LLM and create notification
 * @param {Object} source - Source data
 * @param {string} logContext - Relevant log lines
 * @param {string} errorType - Type of error
 */
async function analyzeErrorWithLLM(source, logContext, errorType) {
  try {
    const result = await api.analyzeError({
      sourceId: source.id,
      sourceName: source.name,
      sourceUrl: source.url,
      errorType: errorType,
      logContext: logContext,
      pipeline: source.pipeline
    });

    addNotification({
      type: 'error',
      source: source.name,
      sourceId: source.id,
      sourceUrl: source.url,
      message: result.summary || `Source entered ${errorType} state`,
      suggestion: result.suggestion,
      actions: result.actions || [
        { label: '📄 View PRD', action: `openPrdModal('${source.id}', '${source.name}', '${source.url}')` },
        { label: '🔄 Retry', action: `retrySource('${source.id}')` }
      ]
    });
  } catch (error) {
    // Fallback notification without LLM analysis
    console.error('Error analyzing with LLM:', error);
    addNotification({
      type: 'error',
      source: source.name,
      sourceId: source.id,
      sourceUrl: source.url,
      message: `Source entered ${errorType} state`,
      suggestion: getDefaultSuggestion(errorType)
    });
  }
}

/**
 * Retry a source
 * @param {string} sourceId - Source ID to retry
 */
export async function retrySource(sourceId) {
  const { showToast } = await import('../components/notifications.js');
  showToast(`🔄 Retrying ${sourceId}...`, 'info');

  try {
    await api.retrySource(sourceId);
    showToast(`✓ Retry initiated for ${sourceId}`, 'success');
  } catch (err) {
    showToast(`✗ Failed to retry: ${err.message}`, 'error');
  }
}

// Make function available globally
window.retrySource = retrySource;

export default {
  checkForErrorsAndAnalyze,
  retrySource
};
