/**
 * Configuration Constants
 * Central configuration for the Ralph Dashboard
 */

export const CONFIG = {
  // API
  API_BASE: 'http://localhost:8765',

  // Refresh intervals (ms)
  REFRESH_INTERVAL: 5000,
  SCREENSHOT_POLL_INTERVAL: 2000,
  KILL_CHECK_INTERVAL: 500,

  // UI
  BATCH_SIZE: 30,
  MAX_NOTIFICATIONS: 50,
  LOG_LINES: 200,

  // Timeouts
  LOADING_FAILSAFE_TIMEOUT: 5000,
  NOTIFICATION_DURATION: 4000,
  SUCCESS_INDICATOR_DURATION: 2000,
  KILL_MAX_ATTEMPTS: 20,

  // Animation delays
  STREAM_CHAR_DELAY: 5,
  STREAM_NEWLINE_DELAY: 20,
};

export const ANSI_COLORS = {
  '30': 'color: #1a1a2e', // black
  '31': 'color: #ff6b6b', // red
  '32': 'color: #4ade80', // green
  '33': 'color: #fbbf24', // yellow
  '34': 'color: #60a5fa', // blue
  '35': 'color: #c084fc', // magenta
  '36': 'color: #22d3ee', // cyan
  '37': 'color: #e5e5e5', // white
  '90': 'color: #6b7280', // bright black (gray)
  '91': 'color: #f87171', // bright red
  '92': 'color: #4ade80', // bright green
  '93': 'color: #facc15', // bright yellow
  '94': 'color: #93c5fd', // bright blue
  '95': 'color: #e879f9', // bright magenta
  '96': 'color: #67e8f9', // bright cyan
  '97': 'color: #ffffff', // bright white
};

export const STATUS_ORDER = {
  in_progress: 0,
  pending: 1,
  blocked: 2,
  completed: 3
};

export default CONFIG;
