/**
 * PRD Editor Feature
 * PRD modal, generation, and editing
 */

import { state } from '../state.js';
import { CONFIG } from '../config.js';
import { api } from '../api.js';
import { showToast } from '../components/notifications.js';
import { startRalph } from './ralph.js';

/**
 * Open PRD modal for a source
 * @param {string} sourceId - Source ID
 * @param {string} sourceName - Source name
 * @param {string} sourceUrl - Source URL
 */
export async function openPrdModal(sourceId, sourceName, sourceUrl) {
  state.currentPrdSource = { id: sourceId, name: sourceName, url: sourceUrl };

  // Update modal header
  document.getElementById('prdSourceBadge').textContent = sourceId;

  // Pre-fill variables
  document.getElementById('varSourceId').value = sourceId;
  document.getElementById('varSourceName').value = sourceName;
  document.getElementById('varSourceUrl').value = sourceUrl || '';
  document.getElementById('varOutputDir').value = `data/${sourceId}`;

  // Reset button text
  document.getElementById('btnDomainAnalysis').textContent = '🔍 Run Domain Analysis';
  document.getElementById('btnGeneratePrd').textContent = '⚡ Generate PRD';

  // Check if files exist
  let analysisExists = false;
  let prdExists = false;

  try {
    const analysisResult = await api.checkPrdFile(`${sourceId}_domain_analysis.md`);
    analysisExists = analysisResult.exists;

    const prdResult = await api.checkPrdFile(`${sourceId}_prd.md`);
    prdExists = prdResult.exists;
  } catch (e) {
    console.log('Could not check file existence:', e);
  }

  // Update button text based on file existence
  if (analysisExists) {
    document.getElementById('btnDomainAnalysis').textContent = '🔄 Reanalyze Domain';
  }
  if (prdExists) {
    document.getElementById('btnGeneratePrd').textContent = '🔄 Regenerate PRD';
  }

  // Build status message
  let statusMsg = `📋 PRD Generator for ${sourceName}\n\n` +
    `Source ID: ${sourceId}\n` +
    `URL: ${sourceUrl || 'Not set'}\n\n` +
    `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n` +
    `📊 Status:\n\n` +
    `  Domain Analysis: ${analysisExists ? '✓ Exists' : '✗ Not found'}\n` +
    `  PRD: ${prdExists ? '✓ Exists' : '✗ Not found'}\n\n` +
    `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n` +
    `📝 Available Actions:\n\n` +
    `  🔍 ${analysisExists ? 'Reanalyze Domain' : 'Run Domain Analysis'}\n` +
    `     Analyzes the website structure using browser automation\n\n` +
    `  ⚡ ${prdExists ? 'Regenerate PRD' : 'Generate PRD'}\n` +
    `     Creates a PRD from the domain analysis\n\n` +
    `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n` +
    `Click a button to start.`;

  document.getElementById('prdStreamText').textContent = statusMsg;
  document.getElementById('prdEditorContent').value = '';
  document.getElementById('prdPreviewContent').innerHTML = '<p style="color: var(--text-muted);">Generate a PRD to see the preview...</p>';
  document.getElementById('prdStreamStatus').style.display = 'none';
  document.getElementById('prdCursor').style.display = 'none';
  document.getElementById('prdStatus').textContent = 'Ready';
  document.getElementById('prdTimestamp').textContent = '--';

  // Show modal
  document.getElementById('prdModal').classList.add('visible');
  switchPrdTab('stream');
}

/**
 * Close PRD modal
 */
export function closePrdModal() {
  document.getElementById('prdModal').classList.remove('visible');
  if (state.prdGenerationAbort) {
    state.prdGenerationAbort.abort();
    state.prdGenerationAbort = null;
  }
  state.currentPrdSource = null;
}

/**
 * Switch PRD tab
 * @param {string} tab - Tab name
 */
export function switchPrdTab(tab) {
  // Update tabs
  document.querySelectorAll('.prd-tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`.prd-tab[onclick="switchPrdTab('${tab}')"]`).classList.add('active');

  // Update panels
  document.querySelectorAll('.prd-panel').forEach(p => p.classList.remove('active'));
  document.getElementById(`prd${tab.charAt(0).toUpperCase() + tab.slice(1)}Panel`).classList.add('active');
}

/**
 * Run domain analysis
 */
export async function runDomainAnalysis() {
  if (!state.currentPrdSource) return;
  const { id: sourceId, name: sourceName, url: sourceUrl } = state.currentPrdSource;

  const streamEl = document.getElementById('prdStreamText');
  document.getElementById('prdStreamStatus').style.display = 'flex';
  document.getElementById('prdCursor').style.display = 'inline-block';
  document.getElementById('prdStatus').textContent = 'Analyzing...';

  streamEl.textContent = `🔍 Starting domain analysis for ${sourceName}...\n`;
  streamEl.textContent += `🌐 Target: ${sourceUrl || 'No URL'}\n\n`;

  try {
    const result = await api.analyzeDomain({ sourceId, sourceName, sourceUrl });

    if (result.success) {
      streamEl.textContent += result.analysis || '✓ Analysis complete.\n';
      streamEl.textContent += `\n\n📁 Saved to: ${result.path}\n`;
      streamEl.textContent += `\nMethod: ${result.method || 'unknown'}\n`;
    } else {
      streamEl.textContent += `\n❌ Error: ${result.error}\n`;
    }
  } catch (error) {
    streamEl.textContent += `\n❌ Error: ${error.message}\n`;
  }

  document.getElementById('prdStreamStatus').style.display = 'none';
  document.getElementById('prdCursor').style.display = 'none';
  document.getElementById('prdStatus').textContent = 'Ready';
  document.getElementById('prdTimestamp').textContent = new Date().toLocaleTimeString();

  setTimeout(() => switchPrdTab('preview'), 1000);
}

/**
 * Run PRD generation
 */
export async function runPrdGeneration() {
  if (!state.currentPrdSource) return;
  const { id: sourceId, name: sourceName, url: sourceUrl } = state.currentPrdSource;

  const streamEl = document.getElementById('prdStreamText');
  document.getElementById('prdStreamStatus').style.display = 'flex';
  document.getElementById('prdCursor').style.display = 'inline-block';
  document.getElementById('prdStatus').textContent = 'Generating...';

  streamEl.textContent = `⚡ Generating PRD for ${sourceName}...\n\n`;

  try {
    const result = await api.generatePrdFromAnalysis({ sourceId, sourceName, sourceUrl });

    if (result.success || result.prd) {
      const prd = result.prd;
      const prdJson = JSON.stringify(prd, null, 2);
      streamEl.textContent += prdJson;
      streamEl.textContent += `\n\n✓ PRD generated!\n`;

      document.getElementById('prdEditorContent').value = prdJson;
      updatePrdPreview(prd);
      state.currentPrdContent = prdJson;
    } else {
      streamEl.textContent += `\n❌ Error: ${result.error}\n`;
    }
  } catch (error) {
    streamEl.textContent += `\n❌ Error: ${error.message}\n`;
  }

  document.getElementById('prdStreamStatus').style.display = 'none';
  document.getElementById('prdCursor').style.display = 'none';
  document.getElementById('prdStatus').textContent = 'Ready';
  document.getElementById('prdTimestamp').textContent = new Date().toLocaleTimeString();

  setTimeout(() => switchPrdTab('preview'), 1000);
}

/**
 * Update PRD preview
 * @param {Object} prd - PRD data
 */
function updatePrdPreview(prd) {
  const previewEl = document.getElementById('prdPreviewContent');

  if (!prd) {
    previewEl.innerHTML = '<p style="color: var(--text-muted);">No PRD data available</p>';
    return;
  }

  const stories = prd.userStories || [];
  const storiesHtml = stories.length > 0 ? stories.map(story => `
    <div class="prd-story">
      <div class="prd-story-header">
        <span class="prd-story-id">${story.id || '?'}</span>
        <span class="prd-story-title">${story.title || 'Untitled'}</span>
      </div>
      <ul class="prd-story-criteria">
        ${(story.acceptanceCriteria || []).map(c => `<li>✓ ${c}</li>`).join('')}
      </ul>
    </div>
  `).join('') : '<p style="color: var(--text-muted);">No user stories defined</p>';

  previewEl.innerHTML = `
    <h4>📋 ${prd.projectName || 'Unnamed Project'}</h4>
    <div style="margin-bottom: 16px; font-size: 13px; color: var(--text-secondary);">
      <strong>Target:</strong> ${prd.targetUrl || 'Not set'}<br>
      <strong>Output:</strong> ${prd.outputDir || 'Not set'}<br>
      <strong>Mode:</strong> ${prd.scrapeMode || 'Not set'}
    </div>
    <h4 style="margin-top: 20px;">📝 User Stories</h4>
    <div class="prd-stories">
      ${storiesHtml}
    </div>
  `;
}

/**
 * Get variables from form
 */
function getVariables() {
  return {
    source_id: document.getElementById('varSourceId').value,
    source_name: document.getElementById('varSourceName').value,
    source_url: document.getElementById('varSourceUrl').value,
    output_dir: document.getElementById('varOutputDir').value,
    scrape_mode: document.getElementById('varScrapeMode').value,
    priority: document.getElementById('varPriority').value
  };
}

/**
 * Clear PRD editor
 */
export function clearPrdEditor() {
  state.currentPrdContent = '';
  document.getElementById('prdStreamText').textContent = 'Click "Generate PRD" to start...';
  document.getElementById('prdEditorContent').value = '';
  document.getElementById('prdPreviewContent').innerHTML = '<p style="color: var(--text-muted);">Generate a PRD to see the preview...</p>';
  document.getElementById('prdStatus').textContent = 'Ready';
  document.getElementById('prdTimestamp').textContent = '--';
}

/**
 * Save PRD to file
 */
export async function savePrdToFile() {
  const content = document.getElementById('prdEditorContent').value;
  if (!content) {
    showToast('❌ No PRD content to save', 'error');
    return;
  }

  try {
    const prd = JSON.parse(content);
    await api.savePrd(prd);
    showToast('✓ PRD saved to scripts/ralph/prd.json', 'success');
  } catch (err) {
    // Fallback: download as file
    const blob = new Blob([content], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `prd_${state.currentPrdSource?.id || 'unknown'}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('📁 PRD downloaded as file', 'info');
  }
}

/**
 * Save PRD to Ralph
 */
export async function savePrdToRalph() {
  await savePrdToFile();
}

/**
 * Use PRD and start Ralph
 */
export async function usePrdAndStartRalph() {
  const content = document.getElementById('prdEditorContent').value;
  if (!content) {
    showToast('❌ No PRD content', 'error');
    return;
  }

  try {
    const prd = JSON.parse(content);

    // Save PRD first
    await api.savePrd(prd);

    closePrdModal();

    // Start Ralph
    showToast(`🚀 Starting Ralph for ${prd.sourceId}...`, 'info');

    const data = await api.startRalph({
      iterations: 25,
      sources: [prd.sourceId]
    });

    if (data.success) {
      showToast(`✓ Ralph started for ${prd.sourceId}`, 'success');
    } else {
      showToast(`✗ Failed: ${data.error}`, 'error');
    }
  } catch (err) {
    showToast(`✗ Error: ${err.message}`, 'error');
  }
}

/**
 * Initialize PRD modal
 */
export function initPrdModal() {
  // Close modal on overlay click
  document.getElementById('prdModal').addEventListener('click', (e) => {
    if (e.target.id === 'prdModal') {
      closePrdModal();
    }
  });

  // Close modal on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.getElementById('prdModal').classList.contains('visible')) {
      closePrdModal();
    }
  });
}

// Make functions available globally for onclick handlers
window.openPrdModal = openPrdModal;
window.closePrdModal = closePrdModal;
window.switchPrdTab = switchPrdTab;
window.runDomainAnalysis = runDomainAnalysis;
window.runPrdGeneration = runPrdGeneration;
window.clearPrdEditor = clearPrdEditor;
window.savePrdToFile = savePrdToFile;
window.savePrdToRalph = savePrdToRalph;
window.usePrdAndStartRalph = usePrdAndStartRalph;

export default {
  openPrdModal,
  closePrdModal,
  switchPrdTab,
  runDomainAnalysis,
  runPrdGeneration,
  clearPrdEditor,
  savePrdToFile,
  savePrdToRalph,
  usePrdAndStartRalph,
  initPrdModal
};
