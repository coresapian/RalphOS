/**
 * Sources Feature
 * Source list rendering, filtering, and sorting
 */

import { state } from '../state.js';
import { CONFIG, STATUS_ORDER } from '../config.js';
import { formatNumber, debounce } from '../utils.js';

/**
 * Render a single source item
 * @param {Object} source - Source data
 * @returns {string} HTML string
 */
function renderSourceItem(source) {
  const pipeline = source.pipeline || {};
  const progress = pipeline.urlsFound ?
    Math.round((pipeline.htmlScraped || 0) / pipeline.urlsFound * 100) : 0;

  return `
    <div class="source-item" data-source-id="${source.id}"
      onclick="openPrdModal('${source.id}', '${source.name.replace(/'/g, "\\'")}', '${(source.url || '').replace(/'/g, "\\'")}')"
      title="Click to view PRD for ${source.name}">
      <div class="source-info">
        <div class="source-status ${source.status}"
          data-source-id="${source.id}"
          data-source-name="${source.name}"
          data-source-url="${source.url || ''}"
          data-source-status="${source.status}"
          onclick="event.stopPropagation(); showSourceMenu(event, this)"
          title="Click for actions"></div>
        <div>
          <div class="source-name">${source.name}</div>
          <div class="source-stats">
            URLs: ${formatNumber(pipeline.urlsFound)} |
            HTML: ${formatNumber(pipeline.htmlScraped)} |
            Builds: ${formatNumber(pipeline.builds)} |
            Mods: ${formatNumber(pipeline.mods)}
          </div>
        </div>
      </div>
      <div class="progress-bar">
        <div class="progress-bar-fill" style="width: ${progress}%"></div>
      </div>
    </div>
  `;
}

/**
 * Render sources list with filtering and sorting
 */
export function renderSourcesList() {
  const container = document.getElementById('sourcesList');

  // Filter sources
  let filtered = state.allSourcesData.filter(source => {
    if (!state.currentFilter) return true;
    return source.name.toLowerCase().includes(state.currentFilter) ||
      (source.id && source.id.toLowerCase().includes(state.currentFilter));
  });

  // Sort sources
  filtered.sort((a, b) => {
    const pipeA = a.pipeline || {};
    const pipeB = b.pipeline || {};

    switch (state.currentSort) {
      case 'name':
        return a.name.localeCompare(b.name);
      case 'urls':
        return (pipeB.urlsFound || 0) - (pipeA.urlsFound || 0);
      case 'html':
        return (pipeB.htmlScraped || 0) - (pipeA.htmlScraped || 0);
      case 'builds':
        return (pipeB.builds || 0) - (pipeA.builds || 0);
      case 'progress':
        const progA = pipeA.urlsFound ? (pipeA.htmlScraped || 0) / pipeA.urlsFound : 0;
        const progB = pipeB.urlsFound ? (pipeB.htmlScraped || 0) / pipeB.urlsFound : 0;
        return progB - progA;
      case 'status':
      default:
        const diff = (STATUS_ORDER[a.status] || 99) - (STATUS_ORDER[b.status] || 99);
        if (diff !== 0) return diff;
        return a.name.localeCompare(b.name);
    }
  });

  // Render with lazy loading
  if (filtered.length === 0) {
    container.innerHTML = `<div class="no-results">No sources matching "${state.currentFilter}"</div>`;
    return;
  }

  const visibleSources = filtered.slice(0, CONFIG.BATCH_SIZE);
  const hasMore = filtered.length > CONFIG.BATCH_SIZE;

  container.innerHTML = visibleSources.map(source => renderSourceItem(source)).join('') +
    (hasMore ? `<div class="load-more" onclick="loadMoreSources()">Load ${filtered.length - CONFIG.BATCH_SIZE} more...</div>` : '');

  // Store filtered for load more
  state._filteredSources = filtered;
  state._loadedCount = CONFIG.BATCH_SIZE;
}

/**
 * Load more sources (pagination)
 */
export function loadMoreSources() {
  const container = document.getElementById('sourcesList');
  const filtered = state._filteredSources || [];
  const loaded = state._loadedCount || CONFIG.BATCH_SIZE;

  const nextBatch = filtered.slice(loaded, loaded + CONFIG.BATCH_SIZE);
  const hasMore = filtered.length > loaded + CONFIG.BATCH_SIZE;

  // Remove load more button
  const loadMoreBtn = container.querySelector('.load-more');
  if (loadMoreBtn) loadMoreBtn.remove();

  // Append new items
  container.insertAdjacentHTML('beforeend',
    nextBatch.map(source => renderSourceItem(source)).join('') +
    (hasMore ? `<div class="load-more" onclick="loadMoreSources()">Load ${filtered.length - loaded - CONFIG.BATCH_SIZE} more...</div>` : '')
  );

  state._loadedCount = loaded + CONFIG.BATCH_SIZE;
}

/**
 * Update sources list data
 * @param {Array} sources - Source data array
 */
export function updateSourcesList(sources) {
  state.allSourcesData = sources;
  renderSourcesList();
}

/**
 * Populate Ralph source selector dropdown
 * @param {Array} sources - Source data array
 */
export function populateSourcesDropdown(sources) {
  populateRalphSourceSelector(sources);
}

/**
 * Populate Ralph source selector (multi-select)
 * @param {Array} sources - Source data array
 */
function populateRalphSourceSelector(sources) {
  const select = document.getElementById('ralphSource');
  const currentSelections = Array.from(select.selectedOptions).map(o => o.value);

  select.innerHTML = '';

  // Sort by status then name
  const sortedSources = [...sources].sort((a, b) => {
    const aOrder = STATUS_ORDER[a.status] ?? 99;
    const bOrder = STATUS_ORDER[b.status] ?? 99;
    if (aOrder !== bOrder) return aOrder - bOrder;
    return a.name.localeCompare(b.name);
  });

  sortedSources.forEach(source => {
    const option = document.createElement('option');
    option.value = source.id;
    const pipeline = source.pipeline || {};
    const urlCount = pipeline.urlsFound || 0;
    const htmlCount = pipeline.htmlScraped || 0;
    const buildCount = pipeline.builds || 0;
    const modCount = pipeline.mods || 0;

    // Status indicator
    const statusIcon = {
      'in_progress': '🟢',
      'pending': '⏳',
      'blocked': '🔴',
      'completed': '✓'
    }[source.status] || '';

    option.textContent = `${statusIcon} ${source.name} (URLs:${urlCount} HTML:${htmlCount} Builds:${buildCount} Mods:${modCount})`;

    // Restore selection
    if (currentSelections.includes(source.id)) {
      option.selected = true;
    }

    select.appendChild(option);
  });
}

/**
 * Initialize sources filter and sort event listeners
 */
export function initSourcesControls() {
  const debouncedFilter = debounce((value) => {
    state.currentFilter = value.toLowerCase();
    renderSourcesList();
  }, 150);

  document.getElementById('sourcesFilter').addEventListener('input', (e) => {
    debouncedFilter(e.target.value);
  });

  document.getElementById('sourcesSort').addEventListener('change', (e) => {
    state.currentSort = e.target.value;
    renderSourcesList();
  });
}

// Make functions available globally for onclick handlers
window.loadMoreSources = loadMoreSources;

export default {
  renderSourcesList,
  loadMoreSources,
  updateSourcesList,
  populateSourcesDropdown,
  initSourcesControls
};
