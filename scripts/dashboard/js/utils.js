/**
 * Utility Functions
 * Shared helper functions for the dashboard
 */

import { ANSI_COLORS } from './config.js';

/**
 * Debounce function calls
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {Function} Debounced function
 */
export function debounce(func, wait) {
  let timeout;
  return function(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}

/**
 * Format number with commas
 * @param {number|string} num - Number to format
 * @returns {string} Formatted number
 */
export function formatNumber(num) {
  if (num === null || num === undefined || num === 'null') return '--';
  return parseInt(num).toLocaleString();
}

/**
 * Format relative time
 * @param {Date|string} date - Date to format
 * @returns {string} Relative time string
 */
export function formatTimeAgo(date) {
  const seconds = Math.floor((new Date() - new Date(date)) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

/**
 * Convert ANSI escape codes to HTML spans
 * @param {string} text - Text with ANSI codes
 * @returns {string} HTML with styled spans
 */
export function ansiToHtml(text) {
  let result = text;
  let openSpans = 0;

  // Match ANSI escape sequences
  result = result.replace(/\x1b\[([0-9;]*)m|\[([0-9]+;?[0-9]*)m/g, (match, p1, p2) => {
    const codes = (p1 || p2 || '').split(';').filter(c => c);

    // Reset code
    if (codes.length === 0 || codes.includes('0')) {
      const closeSpans = '</span>'.repeat(openSpans);
      openSpans = 0;
      return closeSpans;
    }

    // Build style from codes
    let styles = [];
    for (const code of codes) {
      if (code === '1') styles.push('font-weight: bold');
      else if (code === '2') styles.push('opacity: 0.7');
      else if (code === '3') styles.push('font-style: italic');
      else if (code === '4') styles.push('text-decoration: underline');
      else if (ANSI_COLORS[code]) styles.push(ANSI_COLORS[code]);
    }

    if (styles.length > 0) {
      openSpans++;
      return `<span style="${styles.join('; ')}">`;
    }
    return '';
  });

  // Close any remaining open spans
  result += '</span>'.repeat(openSpans);

  return result;
}

/**
 * Colorize log output with keyword highlighting
 * @param {string} text - Log text
 * @returns {string} HTML with colored keywords
 */
export function colorizeLog(text) {
  // First convert ANSI codes to HTML
  let result = ansiToHtml(text);

  // Then apply keyword highlighting
  return result
    .replace(/✓|✔|SUCCESS|COMPLETE/gi, '<span class="success">$&</span>')
    .replace(/✗|ERROR|FAIL|BLOCKED/gi, '<span class="error">$&</span>')
    .replace(/⚠|WARNING|WARN/gi, '<span class="warning">$&</span>')
    .replace(/ℹ|INFO|→/gi, '<span class="info">$&</span>')
    .replace(/(Stage \d)/gi, '<span class="info">$1</span>')
    .replace(/(\d+\/\d+)/g, '<span class="success">$1</span>');
}

/**
 * Filter log lines by source
 * @param {string} logText - Full log text
 * @param {string} sourceId - Source ID to filter by
 * @returns {string} Filtered log text
 */
export function filterLogBySource(logText, sourceId) {
  if (sourceId === '_all' || !sourceId) {
    return logText;
  }

  const lines = logText.split('\n');
  const sourcePatterns = [
    sourceId.toLowerCase(),
    sourceId.replace(/_/g, '-').toLowerCase(),
    sourceId.replace(/-/g, '_').toLowerCase()
  ];

  const filteredLines = lines.filter(line => {
    const lineLower = line.toLowerCase();
    return sourcePatterns.some(pattern => lineLower.includes(pattern)) ||
      lineLower.includes('ralph') ||
      lineLower.includes('iteration') ||
      lineLower.includes('stage') ||
      /^\s*[-=]+\s*$/.test(line);
  });

  if (filteredLines.length === 0) {
    return `No recent log entries for ${sourceId}\n\n(Showing system messages only)`;
  }

  return filteredLines.join('\n');
}

/**
 * Get default suggestion for error type
 * @param {string} errorType - Type of error
 * @returns {string} Suggestion text
 */
export function getDefaultSuggestion(errorType) {
  const suggestions = {
    'blocked': 'Try increasing delays in PRD (min_delay: 5-10s), enable stealth mode, or rotate proxies.',
    'error': 'Check if website structure changed. May need to update selectors in the extractor.',
    'hitl': 'Human verification needed. Check for CAPTCHA or login requirements.'
  };
  return suggestions[errorType] || 'Review logs and PRD configuration.';
}

/**
 * Escape HTML special characters
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
export function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Create element with classes
 * @param {string} tag - HTML tag name
 * @param {string|string[]} classes - CSS class(es)
 * @param {string} content - Inner HTML content
 * @returns {HTMLElement} Created element
 */
export function createElement(tag, classes, content = '') {
  const el = document.createElement(tag);
  if (classes) {
    if (Array.isArray(classes)) {
      el.classList.add(...classes);
    } else {
      el.className = classes;
    }
  }
  if (content) {
    el.innerHTML = content;
  }
  return el;
}
