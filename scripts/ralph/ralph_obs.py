#!/usr/bin/env python3
"""
Ralph Observability Instrumentation Library
==========================================
Provides full observability for Ralph operations including:
- HTTP request/response logging with full bodies
- LLM call tracking with prompts and costs
- Iteration and decision tracking
- File operation logging

Usage:
    from ralph_obs import get_observer, instrumented_session

    # Start a run
    obs = get_observer()
    run_id = obs.start_run(prd=prd_json, config=config_json)

    # Track iterations
    with obs.iteration(story_id="US-001", stage="html-scraper", source_id="bringatrailer") as iter_ctx:
        session = instrumented_session()
        response = session.get(url)
        iter_ctx.set_decision("continue", "More URLs to scrape")

    # End run
    obs.end_run(status="completed")
"""

import gzip
import json
import re
import time
import uuid
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
import duckdb

# ==========================================
# CONFIGURATION
# ==========================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # motormia-etl/
DATABASE_PATH = PROJECT_ROOT / "database" / "ralph_observability.duckdb"

# Body compression threshold (bytes)
COMPRESSION_THRESHOLD = 10000

# Secret redaction patterns
SECRET_PATTERNS = [
    (r'authorization:\s*bearer\s+[^\s]+', 'authorization: bearer [REDACTED]'),
    (r'cookie:\s*[^\r\n]+', 'cookie: [REDACTED]'),
    (r'set-cookie:\s*[^\r\n]+', 'set-cookie: [REDACTED]'),
    (r'x-api-key:\s*[^\s]+', 'x-api-key: [REDACTED]'),
    (r'proxy-authorization:\s*[^\s]+', 'proxy-authorization: [REDACTED]'),
    (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^\s"\']+', 'api_key: [REDACTED]'),
    (r'token["\']?\s*[:=]\s*["\']?[^\s"\']+', 'token: [REDACTED]'),
    (r'secret["\']?\s*[:=]\s*["\']?[^\s"\']+', 'secret: [REDACTED]'),
    (r'password["\']?\s*[:=]\s*["\']?[^\s"\']+', 'password: [REDACTED]'),
]


# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def _generate_id() -> str:
    """Generate a unique ID for events."""
    return str(uuid.uuid4())


def _now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    """Get current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _get_git_info() -> Dict[str, str]:
    """Get current git SHA and branch."""
    result = {"sha": None, "branch": None}
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5
        )
        if sha.returncode == 0:
            result["sha"] = sha.stdout.strip()[:12]

        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5
        )
        if branch.returncode == 0:
            result["branch"] = branch.stdout.strip()
    except Exception:
        pass
    return result


def _compress_body(body: Union[bytes, str, None], threshold: int = COMPRESSION_THRESHOLD) -> tuple:
    """
    Compress body if over threshold.

    Returns:
        Tuple of (compressed_body, is_compressed, original_size)
    """
    if body is None:
        return None, False, 0

    if isinstance(body, str):
        body = body.encode('utf-8', errors='replace')

    original_size = len(body)

    if original_size < threshold:
        return body, False, original_size

    compressed = gzip.compress(body)
    return compressed, True, original_size


def _redact_secrets(data: Union[str, Dict, None]) -> Union[str, Dict, None]:
    """Redact sensitive information from headers or text."""
    if data is None:
        return None

    if isinstance(data, dict):
        redacted = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(s in key_lower for s in ['authorization', 'cookie', 'api-key', 'apikey', 'token', 'secret', 'password']):
                redacted[key] = '[REDACTED]'
            else:
                redacted[key] = value
        return redacted

    if isinstance(data, str):
        result = data
        for pattern, replacement in SECRET_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    return data


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""


def _extract_path(url: str) -> str:
    """Extract path from URL."""
    try:
        parsed = urlparse(url)
        return parsed.path
    except Exception:
        return ""


# ==========================================
# RALPH OBSERVER (SINGLETON)
# ==========================================

class RalphObserver:
    """
    Central observability hub for Ralph operations.

    Tracks:
    - Runs (sessions)
    - Iterations (Claude CLI calls)
    - HTTP events (requests/responses)
    - LLM events (Claude/Gemini calls)
    - Decisions (Ralph choices)
    - File operations
    """

    _instance: Optional["RalphObserver"] = None

    def __new__(cls, db_path: Optional[Path] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: Optional[Path] = None):
        if self._initialized:
            return

        self._db_path = db_path or DATABASE_PATH
        self._db: Optional[duckdb.DuckDBPyConnection] = None
        self._current_run_id: Optional[str] = None
        self._current_iteration_id: Optional[str] = None
        self._current_iteration_ctx: Optional["IterationContext"] = None
        self._webhook_callbacks: Dict[str, List[str]] = {}
        self._initialized = True

    def _get_db(self) -> duckdb.DuckDBPyConnection:
        """Get or create database connection."""
        if self._db is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = duckdb.connect(str(self._db_path))
        return self._db

    def close(self):
        """Close database connection."""
        if self._db is not None:
            self._db.close()
            self._db = None

    # ==========================================
    # RUN MANAGEMENT
    # ==========================================

    def start_run(
        self,
        prd: Optional[Dict] = None,
        config: Optional[Dict] = None,
        notes: Optional[str] = None,
        max_iterations: int = 0
    ) -> str:
        """
        Start a new Ralph run.

        Args:
            prd: PRD JSON data
            config: Config JSON data
            notes: Optional notes about this run
            max_iterations: Expected max iterations

        Returns:
            run_id string
        """
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{_generate_id()[:8]}"
        git_info = _get_git_info()

        db = self._get_db()
        db.execute("""
            INSERT INTO ralph_runs (
                run_id, started_at, status, total_iterations,
                git_sha, branch, prd_json, config_json, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            run_id,
            _now(),
            'running',
            max_iterations,
            git_info.get('sha'),
            git_info.get('branch'),
            json.dumps(prd) if prd else None,
            json.dumps(config) if config else None,
            notes
        ])

        self._current_run_id = run_id
        print(f"[ralph_obs] Started run: {run_id}")
        return run_id

    def end_run(self, status: str = "completed", notes: Optional[str] = None):
        """
        End the current run.

        Args:
            status: Final status ('completed', 'failed', 'cancelled')
            notes: Optional notes
        """
        if not self._current_run_id:
            return

        db = self._get_db()

        # Count completed iterations
        result = db.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'success' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
            FROM ralph_iterations
            WHERE run_id = ?
        """, [self._current_run_id]).fetchone()

        total, completed, failed = result if result else (0, 0, 0)

        db.execute("""
            UPDATE ralph_runs
            SET ended_at = ?,
                status = ?,
                total_iterations = ?,
                completed_stories = ?,
                failed_stories = ?,
                notes = COALESCE(notes || ' | ', '') || COALESCE(?, '')
            WHERE run_id = ?
        """, [_now(), status, total, completed, failed, notes, self._current_run_id])

        print(f"[ralph_obs] Ended run: {self._current_run_id} ({status})")
        self._current_run_id = None

    @property
    def current_run_id(self) -> Optional[str]:
        """Get current run ID."""
        return self._current_run_id

    # ==========================================
    # ITERATION MANAGEMENT
    # ==========================================

    @contextmanager
    def iteration(
        self,
        story_id: Optional[str] = None,
        stage: Optional[str] = None,
        source_id: Optional[str] = None,
        source_name: Optional[str] = None,
        story_title: Optional[str] = None,
        iteration_number: Optional[int] = None
    ):
        """
        Context manager for tracking an iteration.

        Usage:
            with obs.iteration(story_id="US-001", stage="html-scraper") as ctx:
                # Do work
                ctx.set_decision("continue", "More URLs to process")
        """
        iteration_id = _generate_id()
        started_at = _now()

        db = self._get_db()
        db.execute("""
            INSERT INTO ralph_iterations (
                iteration_id, run_id, iteration_number, started_at,
                story_id, story_title, stage, source_id, source_name, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            iteration_id,
            self._current_run_id,
            iteration_number or 0,
            started_at,
            story_id,
            story_title,
            stage,
            source_id,
            source_name,
            'running'
        ])

        self._current_iteration_id = iteration_id
        ctx = IterationContext(self, iteration_id)
        self._current_iteration_ctx = ctx

        try:
            yield ctx
            # Mark as success if no exception
            ctx._finalize('success')
        except Exception as e:
            ctx._error_type = type(e).__name__
            ctx._error_message = str(e)
            ctx._finalize('failed')
            raise
        finally:
            self._current_iteration_id = None
            self._current_iteration_ctx = None

    @property
    def current_iteration_id(self) -> Optional[str]:
        """Get current iteration ID."""
        return self._current_iteration_id

    # ==========================================
    # HTTP EVENT LOGGING
    # ==========================================

    def log_http_event(
        self,
        method: str,
        url: str,
        status_code: Optional[int] = None,
        request_headers: Optional[Dict] = None,
        request_body: Optional[Union[bytes, str]] = None,
        response_headers: Optional[Dict] = None,
        response_body: Optional[Union[bytes, str]] = None,
        duration_ms: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        request_type: Optional[str] = None,
        is_navigation: bool = False,
        is_build_page: bool = False,
        is_blocked: bool = False,
        blocked_reason: Optional[str] = None,
        retry_attempt: int = 0,
        browser_session_id: Optional[str] = None,
        initiator: Optional[str] = None,
        source_id: Optional[str] = None,
        stage: Optional[str] = None
    ) -> str:
        """
        Log an HTTP request/response event.

        Returns:
            event_id
        """
        event_id = _generate_id()

        # Redact secrets from headers
        req_headers = _redact_secrets(request_headers)
        resp_headers = _redact_secrets(response_headers)

        # Compress bodies if needed
        req_body, req_compressed, req_size = _compress_body(request_body)
        resp_body, resp_compressed, resp_size = _compress_body(response_body)

        # Detect blocked responses
        if not is_blocked and status_code in (403, 429, 503):
            is_blocked = True
            if status_code == 403:
                blocked_reason = blocked_reason or 'forbidden'
            elif status_code == 429:
                blocked_reason = blocked_reason or 'rate_limit'
            elif status_code == 503:
                blocked_reason = blocked_reason or 'service_unavailable'

        db = self._get_db()
        db.execute("""
            INSERT INTO ralph_http_events (
                event_id, run_id, iteration_id, timestamp,
                source_id, stage,
                method, url, url_domain, url_path,
                request_headers, request_body, request_body_size, request_body_compressed,
                status_code, response_headers, response_body, response_body_size, response_body_compressed,
                duration_ms, request_type, is_navigation, is_build_page,
                is_blocked, blocked_reason, retry_attempt,
                browser_session_id, initiator,
                error_type, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            event_id,
            self._current_run_id,
            self._current_iteration_id,
            _now(),
            source_id or (self._current_iteration_ctx.source_id if self._current_iteration_ctx else None),
            stage or (self._current_iteration_ctx.stage if self._current_iteration_ctx else None),
            method,
            url,
            _extract_domain(url),
            _extract_path(url),
            json.dumps(req_headers) if req_headers else None,
            req_body,
            req_size,
            req_compressed,
            status_code,
            json.dumps(resp_headers) if resp_headers else None,
            resp_body,
            resp_size,
            resp_compressed,
            duration_ms,
            request_type,
            is_navigation,
            is_build_page,
            is_blocked,
            blocked_reason,
            retry_attempt,
            browser_session_id,
            initiator,
            error_type,
            error_message
        ])

        return event_id

    # ==========================================
    # LLM EVENT LOGGING
    # ==========================================

    def log_llm_event(
        self,
        model: str,
        prompt: Optional[str] = None,
        response: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        response_tokens: Optional[int] = None,
        latency_ms: Optional[int] = None,
        cost_usd: Optional[float] = None,
        provider: Optional[str] = None,
        purpose: Optional[str] = None,
        system_prompt: Optional[str] = None,
        finish_reason: Optional[str] = None,
        tools_called: Optional[List] = None,
        tool_results: Optional[List] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        source_id: Optional[str] = None,
        stage: Optional[str] = None
    ) -> str:
        """
        Log an LLM API call event.

        Returns:
            event_id
        """
        event_id = _generate_id()

        # Infer provider from model name if not provided
        if not provider:
            if 'claude' in model.lower():
                provider = 'anthropic'
            elif 'gemini' in model.lower() or 'palm' in model.lower():
                provider = 'google'
            elif 'gpt' in model.lower():
                provider = 'openai'

        db = self._get_db()
        db.execute("""
            INSERT INTO ralph_llm_events (
                event_id, run_id, iteration_id, timestamp,
                source_id, stage, purpose,
                model, provider, prompt, prompt_tokens, system_prompt,
                response, response_tokens, finish_reason,
                latency_ms, cost_usd,
                tools_called, tool_results,
                error_type, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            event_id,
            self._current_run_id,
            self._current_iteration_id,
            _now(),
            source_id or (self._current_iteration_ctx.source_id if self._current_iteration_ctx else None),
            stage or (self._current_iteration_ctx.stage if self._current_iteration_ctx else None),
            purpose,
            model,
            provider,
            prompt,
            prompt_tokens,
            system_prompt,
            response,
            response_tokens,
            finish_reason,
            latency_ms,
            cost_usd,
            json.dumps(tools_called) if tools_called else None,
            json.dumps(tool_results) if tool_results else None,
            error_type,
            error_message
        ])

        return event_id

    # ==========================================
    # DECISION LOGGING
    # ==========================================

    def log_decision(
        self,
        decision_type: str,
        decision_value: Optional[str] = None,
        reasoning: Optional[str] = None,
        urls_discovered: Optional[int] = None,
        urls_scraped: Optional[int] = None,
        builds_extracted: Optional[int] = None,
        mods_extracted: Optional[int] = None,
        success_rate: Optional[float] = None,
        related_event_ids: Optional[List[str]] = None,
        source_id: Optional[str] = None,
        stage: Optional[str] = None,
        story_id: Optional[str] = None
    ) -> str:
        """
        Log a Ralph decision.

        Args:
            decision_type: Type of decision ('select_story', 'select_source', 'retry', 'skip', 'block_detected', 'complete', 'fail')
            decision_value: The choice made
            reasoning: Why this decision was made

        Returns:
            decision_id
        """
        decision_id = _generate_id()

        db = self._get_db()
        db.execute("""
            INSERT INTO ralph_decisions (
                decision_id, run_id, iteration_id, timestamp,
                decision_type, decision_value, reasoning,
                source_id, stage, story_id,
                urls_discovered, urls_scraped, builds_extracted, mods_extracted, success_rate,
                related_event_ids
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            decision_id,
            self._current_run_id,
            self._current_iteration_id,
            _now(),
            decision_type,
            decision_value,
            reasoning,
            source_id or (self._current_iteration_ctx.source_id if self._current_iteration_ctx else None),
            stage or (self._current_iteration_ctx.stage if self._current_iteration_ctx else None),
            story_id or (self._current_iteration_ctx.story_id if self._current_iteration_ctx else None),
            urls_discovered,
            urls_scraped,
            builds_extracted,
            mods_extracted,
            success_rate,
            json.dumps(related_event_ids) if related_event_ids else None
        ])

        return decision_id

    # ==========================================
    # FILE OPERATION LOGGING
    # ==========================================

    def log_file_op(
        self,
        operation: str,
        file_path: str,
        file_type: Optional[str] = None,
        bytes_written: Optional[int] = None,
        lines_written: Optional[int] = None,
        records_written: Optional[int] = None,
        content_before: Optional[str] = None,
        content_after: Optional[str] = None,
        diff: Optional[str] = None,
        git_staged: bool = False
    ) -> str:
        """
        Log a file operation.

        Args:
            operation: 'create', 'update', 'delete', 'read'
            file_path: Path to the file
            file_type: File extension or type

        Returns:
            op_id
        """
        op_id = _generate_id()

        # Infer file type from extension if not provided
        if not file_type:
            suffix = Path(file_path).suffix.lower()
            file_type = suffix[1:] if suffix else None

        db = self._get_db()
        db.execute("""
            INSERT INTO ralph_file_ops (
                op_id, run_id, iteration_id, timestamp,
                operation, file_path, file_type,
                bytes_written, lines_written, records_written,
                content_before, content_after, diff, git_staged
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            op_id,
            self._current_run_id,
            self._current_iteration_id,
            _now(),
            operation,
            file_path,
            file_type,
            bytes_written,
            lines_written,
            records_written,
            content_before,
            content_after,
            diff,
            git_staged
        ])

        return op_id

    # ==========================================
    # METRICS SNAPSHOTS
    # ==========================================

    def take_metrics_snapshot(self) -> str:
        """
        Take a snapshot of current metrics for the dashboard.

        Returns:
            snapshot_id
        """
        if not self._current_run_id:
            return None

        snapshot_id = _generate_id()
        db = self._get_db()

        # Calculate metrics from events
        http_stats = db.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN status_code BETWEEN 200 AND 299 THEN 1 END) as successful,
                COUNT(CASE WHEN status_code >= 400 OR error_type IS NOT NULL THEN 1 END) as failed,
                COUNT(CASE WHEN is_blocked THEN 1 END) as blocked,
                ROUND(AVG(duration_ms), 0) as avg_latency,
                COALESCE(SUM(response_body_size), 0) as bytes_downloaded,
                COALESCE(SUM(request_body_size), 0) as bytes_uploaded
            FROM ralph_http_events
            WHERE run_id = ?
        """, [self._current_run_id]).fetchone()

        llm_stats = db.execute("""
            SELECT
                COUNT(*) as calls,
                COALESCE(SUM(prompt_tokens), 0) as tokens_in,
                COALESCE(SUM(response_tokens), 0) as tokens_out,
                COALESCE(SUM(cost_usd), 0) as cost
            FROM ralph_llm_events
            WHERE run_id = ?
        """, [self._current_run_id]).fetchone()

        # Get latest decision metrics
        decision_stats = db.execute("""
            SELECT urls_discovered, urls_scraped, builds_extracted, mods_extracted
            FROM ralph_decisions
            WHERE run_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, [self._current_run_id]).fetchone()

        db.execute("""
            INSERT INTO ralph_metrics_snapshots (
                snapshot_id, run_id, timestamp,
                total_requests, successful_requests, failed_requests, blocked_requests,
                avg_latency_ms, bytes_downloaded, bytes_uploaded,
                llm_calls, llm_tokens_in, llm_tokens_out, llm_cost_usd,
                urls_discovered, urls_scraped, builds_extracted, mods_extracted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            snapshot_id,
            self._current_run_id,
            _now(),
            http_stats[0] if http_stats else 0,
            http_stats[1] if http_stats else 0,
            http_stats[2] if http_stats else 0,
            http_stats[3] if http_stats else 0,
            int(http_stats[4]) if http_stats and http_stats[4] else None,
            http_stats[5] if http_stats else 0,
            http_stats[6] if http_stats else 0,
            llm_stats[0] if llm_stats else 0,
            llm_stats[1] if llm_stats else 0,
            llm_stats[2] if llm_stats else 0,
            llm_stats[3] if llm_stats else 0,
            decision_stats[0] if decision_stats else None,
            decision_stats[1] if decision_stats else None,
            decision_stats[2] if decision_stats else None,
            decision_stats[3] if decision_stats else None
        ])

        return snapshot_id


# ==========================================
# ITERATION CONTEXT
# ==========================================

class IterationContext:
    """Context object for an iteration, used within the context manager."""

    def __init__(self, observer: RalphObserver, iteration_id: str):
        self._observer = observer
        self._iteration_id = iteration_id
        self._decision: Optional[str] = None
        self._decision_reasoning: Optional[str] = None
        self._files_changed: List[str] = []
        self._learnings: Optional[str] = None
        self._error_type: Optional[str] = None
        self._error_message: Optional[str] = None
        self.source_id: Optional[str] = None
        self.stage: Optional[str] = None
        self.story_id: Optional[str] = None

    def set_decision(self, decision: str, reasoning: Optional[str] = None):
        """Set the decision made during this iteration."""
        self._decision = decision
        self._decision_reasoning = reasoning

    def add_file_changed(self, file_path: str):
        """Record a file that was changed."""
        self._files_changed.append(file_path)

    def set_learnings(self, learnings: str):
        """Record learnings from this iteration."""
        self._learnings = learnings

    def _finalize(self, status: str):
        """Finalize the iteration with final status."""
        db = self._observer._get_db()
        db.execute("""
            UPDATE ralph_iterations
            SET ended_at = ?,
                status = ?,
                decision = ?,
                decision_reasoning = ?,
                files_changed = ?,
                learnings = ?,
                error_type = ?,
                error_message = ?
            WHERE iteration_id = ?
        """, [
            _now(),
            status,
            self._decision,
            self._decision_reasoning,
            json.dumps(self._files_changed) if self._files_changed else None,
            self._learnings,
            self._error_type,
            self._error_message,
            self._iteration_id
        ])


# ==========================================
# INSTRUMENTED SESSION
# ==========================================

class InstrumentedSession:
    """
    Wrapper around requests.Session that automatically logs all HTTP requests.

    Usage:
        session = instrumented_session()
        response = session.get("https://example.com")
    """

    def __init__(self, session, observer: RalphObserver):
        self._session = session
        self._observer = observer

    def request(self, method: str, url: str, **kwargs) -> "Response":
        """Make a request and log it."""
        import requests

        start_time = time.time()
        error_type = None
        error_message = None
        response = None

        try:
            response = self._session.request(method, url, **kwargs)
        except requests.RequestException as e:
            error_type = type(e).__name__
            error_message = str(e)
            raise
        finally:
            duration_ms = int((time.time() - start_time) * 1000)

            # Extract request body
            request_body = kwargs.get('data') or kwargs.get('json')
            if isinstance(request_body, dict):
                request_body = json.dumps(request_body)

            # Log the event
            self._observer.log_http_event(
                method=method,
                url=url,
                status_code=response.status_code if response else None,
                request_headers=dict(self._session.headers),
                request_body=request_body,
                response_headers=dict(response.headers) if response else None,
                response_body=response.content if response else None,
                duration_ms=duration_ms,
                error_type=error_type,
                error_message=error_message,
                request_type='fetch'
            )

        return response

    def get(self, url: str, **kwargs):
        return self.request('GET', url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request('POST', url, **kwargs)

    def put(self, url: str, **kwargs):
        return self.request('PUT', url, **kwargs)

    def delete(self, url: str, **kwargs):
        return self.request('DELETE', url, **kwargs)

    def head(self, url: str, **kwargs):
        return self.request('HEAD', url, **kwargs)

    @property
    def headers(self):
        return self._session.headers


# ==========================================
# MODULE-LEVEL FUNCTIONS
# ==========================================

_observer: Optional[RalphObserver] = None


def get_observer(db_path: Optional[Path] = None) -> RalphObserver:
    """Get the global RalphObserver singleton."""
    global _observer
    if _observer is None:
        _observer = RalphObserver(db_path)
    return _observer


def instrumented_session(retries: int = 3, backoff_factor: float = 1.0, timeout: int = 30):
    """
    Create an instrumented session that logs all HTTP requests.

    This is a drop-in replacement for ralph_utils.get_robust_session()
    that adds automatic HTTP event logging.
    """
    # Import here to avoid circular dependency
    from ralph_utils import get_robust_session as _get_robust_session

    session = _get_robust_session(retries=retries, backoff_factor=backoff_factor, timeout=timeout)
    return InstrumentedSession(session, get_observer())


# ==========================================
# CLI FOR TESTING
# ==========================================

if __name__ == "__main__":
    print("Testing ralph_obs.py...")

    obs = get_observer()

    # Test run management
    run_id = obs.start_run(
        prd={"project": "test"},
        config={"timeout": 30},
        notes="Test run"
    )
    print(f"Started run: {run_id}")

    # Test iteration
    with obs.iteration(story_id="US-001", stage="test", source_id="test_source") as ctx:
        ctx.set_decision("continue", "Testing iteration context")

        # Test HTTP logging
        event_id = obs.log_http_event(
            method="GET",
            url="https://example.com/test",
            status_code=200,
            duration_ms=150
        )
        print(f"Logged HTTP event: {event_id}")

        # Test LLM logging
        llm_id = obs.log_llm_event(
            model="claude-3-opus",
            prompt="Test prompt",
            response="Test response",
            prompt_tokens=10,
            response_tokens=20,
            latency_ms=500
        )
        print(f"Logged LLM event: {llm_id}")

        # Test decision logging
        decision_id = obs.log_decision(
            decision_type="test",
            decision_value="test_value",
            reasoning="Testing decision logging"
        )
        print(f"Logged decision: {decision_id}")

    # Take metrics snapshot
    snapshot_id = obs.take_metrics_snapshot()
    print(f"Took metrics snapshot: {snapshot_id}")

    # End run
    obs.end_run(status="completed")

    print("\n✅ All tests passed!")
    print(f"Database: {DATABASE_PATH}")
