#!/usr/bin/env python3
"""
Ralph's DuckDB Helper Module
============================
Provides robust, efficient, and logged DuckDB operations for data analysis.

Features:
- Connection management with automatic error handling
- Efficient data ingestion/export (CSV, JSON, Parquet)
- Integrated logging for all operations
- Transaction support for data integrity
- Pandas integration for easy data manipulation
- Build/Mod specific operations for RalphOS

Usage:
    from ralph_duckdb import RalphDuckDB

    db = RalphDuckDB("ralph_data.duckdb")
    db.import_file("data/source/builds.json", "builds")
    df = db.query_to_df("SELECT * FROM builds WHERE year > 2020")
    db.export_table("builds", "output.parquet")
"""

import json
import os
from pathlib import Path
from typing import Union, Optional, List, Dict, Any
import logging
from datetime import datetime

# Try to import ralph_utils logger
try:
    from ralph_utils import logger as ralph_logger
except ImportError:
    ralph_logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

# ==========================================
# DUCKDB CLIENT
# ==========================================

class RalphDuckDB:
    """
    A robust DuckDB interface for Ralph's data operations.

    Features:
    - Connection management with automatic error handling
    - Efficient data ingestion/export
    - Integrated logging for all operations
    - Transaction support for data integrity
    - Pandas integration for easy data manipulation
    """

    def __init__(self, db_path: str = ":memory:", read_only: bool = False):
        """
        Initialize DuckDB connection.

        Args:
            db_path: Path to database file (":memory:" for in-memory)
            read_only: Whether to open in read-only mode
        """
        self.db_path = db_path
        self.read_only = read_only
        self.con = None
        self._connect()
        self._init_extensions()

    def _connect(self):
        """Establish database connection with error handling."""
        try:
            import duckdb
            self.con = duckdb.connect(database=self.db_path, read_only=self.read_only)

            if hasattr(ralph_logger, 'log'):
                ralph_logger.log("INFO", f"DuckDB connection established", {"db_path": self.db_path})
            else:
                ralph_logger.info(f"DuckDB connection established to {self.db_path}")

        except ImportError:
            msg = "DuckDB not installed. Run: pip install duckdb"
            if hasattr(ralph_logger, 'log'):
                ralph_logger.log("ERROR", msg)
            raise ImportError(msg)
        except Exception as e:
            if hasattr(ralph_logger, 'log'):
                ralph_logger.log("ERROR", f"DuckDB connection failed: {str(e)}")
            raise

    def _init_extensions(self):
        """Initialize commonly used extensions."""
        try:
            # JSON extension for JSON operations
            self.con.execute("INSTALL json; LOAD json;")
            # Parquet for efficient storage
            self.con.execute("INSTALL parquet; LOAD parquet;")
        except Exception as e:
            # Extensions might already be loaded
            pass

    # ==========================================
    # CORE OPERATIONS
    # ==========================================

    def execute(self, query: str, params: Optional[tuple] = None):
        """
        Execute SQL query with error handling and logging.

        Args:
            query: SQL query to execute
            params: Optional parameters for parameterized queries

        Returns:
            DuckDB result object
        """
        try:
            if params:
                result = self.con.execute(query, params)
            else:
                result = self.con.execute(query)

            if hasattr(ralph_logger, 'log'):
                ralph_logger.log("DEBUG", "SQL executed", {"query": query[:100]})

            return result

        except Exception as e:
            if hasattr(ralph_logger, 'log'):
                ralph_logger.log("ERROR", f"SQL execution failed: {str(e)}", {"query": query[:200]})
            raise

    def query(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """
        Execute query and return results as list of dicts.

        Args:
            query: SQL query
            params: Optional query parameters

        Returns:
            List of dictionaries (one per row)
        """
        result = self.execute(query, params)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def query_to_df(self, query: str, params: Optional[tuple] = None):
        """
        Execute query and return results as pandas DataFrame.

        Args:
            query: SQL query
            params: Optional query parameters

        Returns:
            pandas DataFrame
        """
        try:
            import pandas as pd
            result = self.execute(query, params)
            return result.df()
        except ImportError:
            raise ImportError("pandas required. Run: pip install pandas")

    def query_scalar(self, query: str, params: Optional[tuple] = None) -> Any:
        """
        Execute query and return single value.

        Args:
            query: SQL query returning single value
            params: Optional query parameters

        Returns:
            Single value
        """
        result = self.execute(query, params)
        row = result.fetchone()
        return row[0] if row else None

    # ==========================================
    # DATA IMPORT
    # ==========================================

    def import_file(self, file_path: str, table_name: str,
                    create_table: bool = True,
                    if_exists: str = "replace") -> int:
        """
        Import data from file into table.
        Automatically detects format from extension.

        Args:
            file_path: Path to data file (CSV, JSON, Parquet)
            table_name: Target table name
            create_table: Whether to create table if not exists
            if_exists: 'replace', 'append', or 'fail'

        Returns:
            Number of rows imported
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = path.suffix.lower()

        # Determine import method based on extension
        if suffix == '.json':
            return self._import_json(file_path, table_name, if_exists)
        elif suffix == '.jsonl':
            return self._import_jsonl(file_path, table_name, if_exists)
        elif suffix == '.csv':
            return self._import_csv(file_path, table_name, if_exists)
        elif suffix == '.parquet':
            return self._import_parquet(file_path, table_name, if_exists)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def _import_json(self, file_path: str, table_name: str, if_exists: str) -> int:
        """Import JSON file (handles both array and single object)."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Handle different JSON structures
        if isinstance(data, dict):
            # Check for common wrapper patterns
            for key in ['builds', 'mods', 'urls', 'data', 'items', 'records']:
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
            else:
                # Single object, wrap in list
                data = [data]

        if not data:
            return 0

        # Create table from first record
        if if_exists == 'replace':
            self.execute(f"DROP TABLE IF EXISTS {table_name}")

        # Register and insert
        import duckdb
        self.con.register('temp_data', data)

        self.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} AS
            SELECT * FROM temp_data
        """)

        count = self.query_scalar(f"SELECT COUNT(*) FROM {table_name}")

        if hasattr(ralph_logger, 'log'):
            ralph_logger.log("INFO", f"Imported JSON to {table_name}", {"rows": count, "file": file_path})

        return count

    def _import_jsonl(self, file_path: str, table_name: str, if_exists: str) -> int:
        """Import JSON Lines file."""
        if if_exists == 'replace':
            self.execute(f"DROP TABLE IF EXISTS {table_name}")

        self.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} AS
            SELECT * FROM read_json_auto('{file_path}', format='newline_delimited')
        """)

        count = self.query_scalar(f"SELECT COUNT(*) FROM {table_name}")

        if hasattr(ralph_logger, 'log'):
            ralph_logger.log("INFO", f"Imported JSONL to {table_name}", {"rows": count})

        return count

    def _import_csv(self, file_path: str, table_name: str, if_exists: str) -> int:
        """Import CSV file."""
        if if_exists == 'replace':
            self.execute(f"DROP TABLE IF EXISTS {table_name}")

        self.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} AS
            SELECT * FROM read_csv_auto('{file_path}')
        """)

        count = self.query_scalar(f"SELECT COUNT(*) FROM {table_name}")

        if hasattr(ralph_logger, 'log'):
            ralph_logger.log("INFO", f"Imported CSV to {table_name}", {"rows": count})

        return count

    def _import_parquet(self, file_path: str, table_name: str, if_exists: str) -> int:
        """Import Parquet file."""
        if if_exists == 'replace':
            self.execute(f"DROP TABLE IF EXISTS {table_name}")

        self.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} AS
            SELECT * FROM read_parquet('{file_path}')
        """)

        count = self.query_scalar(f"SELECT COUNT(*) FROM {table_name}")

        if hasattr(ralph_logger, 'log'):
            ralph_logger.log("INFO", f"Imported Parquet to {table_name}", {"rows": count})

        return count

    def register_df(self, df, name: str):
        """
        Register a pandas DataFrame for querying.

        Args:
            df: pandas DataFrame
            name: Name to use in queries
        """
        self.con.register(name, df)

    # ==========================================
    # DATA EXPORT
    # ==========================================

    def export_table(self, table_name: str, file_path: str,
                     format: str = None) -> bool:
        """
        Export table to file.

        Args:
            table_name: Source table name
            file_path: Output file path
            format: Output format (auto-detected from extension if None)

        Returns:
            True if successful
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        suffix = format or path.suffix.lower().lstrip('.')

        if suffix in ('parquet', 'pq'):
            self.execute(f"COPY {table_name} TO '{file_path}' (FORMAT PARQUET)")
        elif suffix == 'csv':
            self.execute(f"COPY {table_name} TO '{file_path}' (FORMAT CSV, HEADER)")
        elif suffix == 'json':
            self.execute(f"COPY {table_name} TO '{file_path}' (FORMAT JSON, ARRAY true)")
        else:
            raise ValueError(f"Unsupported export format: {suffix}")

        if hasattr(ralph_logger, 'log'):
            ralph_logger.log("INFO", f"Exported {table_name} to {file_path}")

        return True

    def export_query(self, query: str, file_path: str,
                     format: str = None) -> bool:
        """
        Export query results to file.

        Args:
            query: SQL query
            file_path: Output file path
            format: Output format (auto-detected from extension if None)

        Returns:
            True if successful
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        suffix = format or path.suffix.lower().lstrip('.')

        if suffix in ('parquet', 'pq'):
            self.execute(f"COPY ({query}) TO '{file_path}' (FORMAT PARQUET)")
        elif suffix == 'csv':
            self.execute(f"COPY ({query}) TO '{file_path}' (FORMAT CSV, HEADER)")
        elif suffix == 'json':
            self.execute(f"COPY ({query}) TO '{file_path}' (FORMAT JSON, ARRAY true)")
        else:
            raise ValueError(f"Unsupported export format: {suffix}")

        return True

    # ==========================================
    # TABLE MANAGEMENT
    # ==========================================

    def list_tables(self) -> List[str]:
        """List all tables in the database."""
        result = self.query("SHOW TABLES")
        return [row['name'] for row in result]

    def get_table_info(self, table_name: str) -> Dict:
        """
        Get table schema information.

        Args:
            table_name: Table name

        Returns:
            Dict with column info
        """
        result = self.query(f"DESCRIBE {table_name}")
        count = self.query_scalar(f"SELECT COUNT(*) FROM {table_name}")

        return {
            "table_name": table_name,
            "row_count": count,
            "columns": result
        }

    def summarize_table(self, table_name: str) -> Dict:
        """
        Get quick statistical summary of a table.

        Args:
            table_name: Table name

        Returns:
            Summary statistics
        """
        result = self.query(f"SUMMARIZE SELECT * FROM {table_name}")
        return result

    def drop_table(self, table_name: str, if_exists: bool = True):
        """Drop a table."""
        if_clause = "IF EXISTS " if if_exists else ""
        self.execute(f"DROP TABLE {if_clause}{table_name}")

    def create_index(self, table_name: str, column: str, index_name: str = None):
        """Create an index on a column."""
        idx_name = index_name or f"idx_{table_name}_{column}"
        self.execute(f"CREATE INDEX {idx_name} ON {table_name}({column})")

    # ==========================================
    # RALPHOS-SPECIFIC OPERATIONS
    # ==========================================

    def import_builds(self, source_dir: str, source_name: str = None) -> int:
        """
        Import builds.json from a source directory.

        Args:
            source_dir: Source data directory (e.g., "data/luxury4play")
            source_name: Optional source name (defaults to directory name)

        Returns:
            Number of builds imported
        """
        builds_file = Path(source_dir) / "builds.json"
        if not builds_file.exists():
            return 0

        table_name = f"builds_{source_name or Path(source_dir).name}"
        return self.import_file(str(builds_file), table_name)

    def import_mods(self, source_dir: str, source_name: str = None) -> int:
        """
        Import mods.json from a source directory.

        Args:
            source_dir: Source data directory
            source_name: Optional source name

        Returns:
            Number of mods imported
        """
        mods_file = Path(source_dir) / "mods.json"
        if not mods_file.exists():
            return 0

        table_name = f"mods_{source_name or Path(source_dir).name}"
        return self.import_file(str(mods_file), table_name)

    def import_urls(self, source_dir: str, source_name: str = None) -> int:
        """
        Import urls.json from a source directory.

        Args:
            source_dir: Source data directory
            source_name: Optional source name

        Returns:
            Number of URLs imported
        """
        urls_file = Path(source_dir) / "urls.json"
        if not urls_file.exists():
            return 0

        with open(urls_file, 'r') as f:
            data = json.load(f)

        urls = data.get('urls', [])
        if not urls:
            return 0

        # Convert to records
        records = [{'url': url, 'source': source_name or Path(source_dir).name}
                   for url in urls]

        table_name = f"urls_{source_name or Path(source_dir).name}"
        self.con.register('url_data', records)
        self.execute(f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM url_data")

        return len(records)

    def get_build_stats(self, table_name: str = "builds") -> Dict:
        """
        Get statistics for builds table.

        Returns:
            Dict with build statistics
        """
        try:
            stats = {
                "total_builds": self.query_scalar(f"SELECT COUNT(*) FROM {table_name}"),
                "by_make": self.query(f"""
                    SELECT make, COUNT(*) as count
                    FROM {table_name}
                    GROUP BY make
                    ORDER BY count DESC
                    LIMIT 10
                """),
                "by_year": self.query(f"""
                    SELECT year, COUNT(*) as count
                    FROM {table_name}
                    GROUP BY year
                    ORDER BY year DESC
                    LIMIT 10
                """),
                "by_source": self.query(f"""
                    SELECT build_source, COUNT(*) as count
                    FROM {table_name}
                    GROUP BY build_source
                    ORDER BY count DESC
                """) if 'build_source' in [c['column_name'] for c in self.query(f"DESCRIBE {table_name}")] else []
            }
            return stats
        except Exception as e:
            return {"error": str(e)}

    def deduplicate_builds(self, table_name: str = "builds",
                          key_columns: List[str] = None) -> int:
        """
        Remove duplicate builds based on key columns.

        Args:
            table_name: Table to deduplicate
            key_columns: Columns to use for deduplication (default: build_id)

        Returns:
            Number of duplicates removed
        """
        key_cols = key_columns or ['build_id']
        key_str = ', '.join(key_cols)

        # Get count before
        before_count = self.query_scalar(f"SELECT COUNT(*) FROM {table_name}")

        # Create deduplicated table
        self.execute(f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT DISTINCT ON ({key_str}) *
            FROM {table_name}
        """)

        # Get count after
        after_count = self.query_scalar(f"SELECT COUNT(*) FROM {table_name}")
        removed = before_count - after_count

        if hasattr(ralph_logger, 'log'):
            ralph_logger.log("INFO", f"Deduplicated {table_name}", {"removed": removed})

        return removed

    # ==========================================
    # ANALYTICS
    # ==========================================

    def get_scraping_progress(self, source_name: str) -> Dict:
        """
        Get scraping progress metrics for a source.

        Args:
            source_name: Source identifier

        Returns:
            Progress metrics
        """
        metrics = {}

        # Check for URLs table
        urls_table = f"urls_{source_name}"
        if urls_table in self.list_tables():
            metrics['urls_discovered'] = self.query_scalar(f"SELECT COUNT(*) FROM {urls_table}")

        # Check for builds table
        builds_table = f"builds_{source_name}"
        if builds_table in self.list_tables():
            metrics['builds_extracted'] = self.query_scalar(f"SELECT COUNT(*) FROM {builds_table}")

        # Check for mods table
        mods_table = f"mods_{source_name}"
        if mods_table in self.list_tables():
            metrics['mods_extracted'] = self.query_scalar(f"SELECT COUNT(*) FROM {mods_table}")

        return metrics

    # ==========================================
    # TRANSACTIONS
    # ==========================================

    def begin_transaction(self):
        """Begin a transaction."""
        self.execute("BEGIN TRANSACTION")

    def commit(self):
        """Commit the current transaction."""
        self.execute("COMMIT")

    def rollback(self):
        """Rollback the current transaction."""
        self.execute("ROLLBACK")

    # ==========================================
    # CLEANUP
    # ==========================================

    def vacuum(self):
        """Vacuum the database to reclaim space."""
        self.execute("VACUUM")

    def checkpoint(self):
        """Force a checkpoint to disk."""
        self.execute("CHECKPOINT")

    def close(self):
        """Close the database connection."""
        if self.con:
            self.con.close()
            self.con = None

            if hasattr(ralph_logger, 'log'):
                ralph_logger.log("INFO", "DuckDB connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ==========================================
# CONVENIENCE FUNCTIONS
# ==========================================

def get_db(db_path: str = "ralph_data.duckdb") -> RalphDuckDB:
    """
    Get a RalphDuckDB instance.
    Convenience function for quick access.

    Args:
        db_path: Path to database file

    Returns:
        RalphDuckDB instance
    """
    return RalphDuckDB(db_path)


def quick_query(query: str, db_path: str = ":memory:") -> List[Dict]:
    """
    Execute a quick one-off query.

    Args:
        query: SQL query
        db_path: Database path

    Returns:
        Query results as list of dicts
    """
    with RalphDuckDB(db_path) as db:
        return db.query(query)


# ==========================================
# CLI
# ==========================================

if __name__ == "__main__":
    import sys

    print("Testing RalphDuckDB...")

    # Test in-memory database
    db = RalphDuckDB(":memory:")

    # Create test table
    db.execute("""
        CREATE TABLE test_builds AS SELECT * FROM (
            VALUES
                (1, 2024, 'Toyota', 'Supra'),
                (2, 2023, 'Ford', 'Mustang'),
                (3, 2024, 'Chevrolet', 'Corvette')
        ) AS t(build_id, year, make, model)
    """)

    # Query test
    result = db.query("SELECT * FROM test_builds WHERE year = 2024")
    print(f"Query result: {result}")

    # Stats
    print(f"Tables: {db.list_tables()}")
    print(f"Table info: {db.get_table_info('test_builds')}")

    # Export test
    db.export_table("test_builds", "/tmp/test_builds.csv")
    print("Export: OK")

    db.close()
    print("\n✅ All DuckDB tests passed!")
