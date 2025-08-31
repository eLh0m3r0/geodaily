"""
Database resilience layer with connection pooling, retry mechanisms, and circuit breaker integration.
"""

import sqlite3
import threading
import time
from typing import Any, Callable, Optional, Dict, List
from contextlib import contextmanager
from dataclasses import dataclass
from queue import Queue, Empty

from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage
from .circuit_breaker import get_circuit_breaker, CircuitBreakerOpen
from .retry_mechanisms import retry_database_operation


@dataclass
class ConnectionPoolStats:
    """Statistics for connection pool."""
    total_connections_created: int = 0
    active_connections: int = 0
    available_connections: int = 0
    connection_requests: int = 0
    connection_timeouts: int = 0
    connection_errors: int = 0


class ConnectionPool:
    """
    Thread-safe connection pool for SQLite database connections.
    """

    def __init__(self,
                 database_path: str,
                 max_connections: int = 10,
                 connection_timeout: float = 30.0,
                 max_idle_time: float = 300.0,  # 5 minutes
                 logger=None):
        """
        Initialize connection pool.

        Args:
            database_path: Path to SQLite database file
            max_connections: Maximum number of connections in pool
            connection_timeout: Timeout for getting connection from pool
            max_idle_time: Maximum idle time before connection is closed
            logger: Structured logger instance
        """
        self.database_path = database_path
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.max_idle_time = max_idle_time

        self.logger = logger or get_structured_logger("connection_pool")

        # Thread-safe components
        self._pool = Queue(maxsize=max_connections)
        self._lock = threading.RLock()
        self._stats = ConnectionPoolStats()

        # Connection tracking
        self._active_connections = set()
        self._connection_timestamps = {}

        # Initialize pool with minimum connections
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize pool with minimum connections."""
        try:
            # Create initial connections
            for _ in range(min(2, self.max_connections)):
                conn = self._create_connection()
                if conn:
                    self._pool.put(conn)
                    self._stats.available_connections += 1

            self.logger.info("Connection pool initialized",
                           structured_data={
                               'database_path': self.database_path,
                               'max_connections': self.max_connections,
                               'initial_connections': self._stats.available_connections
                           })

        except Exception as e:
            self.logger.error("Failed to initialize connection pool",
                            error_category=ErrorCategory.DATABASE_ERROR,
                            structured_data={'error': str(e)})

    def _create_connection(self) -> Optional[sqlite3.Connection]:
        """Create a new database connection."""
        try:
            conn = sqlite3.connect(
                self.database_path,
                timeout=30.0,
                isolation_level=None  # Enable autocommit mode
            )

            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")

            # Set connection properties for better performance
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = 1000")
            conn.execute("PRAGMA temp_store = memory")

            with self._lock:
                self._stats.total_connections_created += 1
                self._active_connections.add(id(conn))
                self._connection_timestamps[id(conn)] = time.time()

            self.logger.debug("Database connection created",
                            structured_data={
                                'connection_id': id(conn),
                                'total_created': self._stats.total_connections_created
                            })

            return conn

        except Exception as e:
            self.logger.error("Failed to create database connection",
                            error_category=ErrorCategory.DATABASE_ERROR,
                            structured_data={'error': str(e)})
            return None

    def _close_connection(self, conn: sqlite3.Connection):
        """Close a database connection."""
        try:
            conn_id = id(conn)
            with self._lock:
                self._active_connections.discard(conn_id)
                self._connection_timestamps.pop(conn_id, None)

            conn.close()

            self.logger.debug("Database connection closed",
                            structured_data={'connection_id': conn_id})

        except Exception as e:
            self.logger.warning("Error closing database connection",
                              error_category=ErrorCategory.DATABASE_ERROR,
                              structured_data={'error': str(e)})

    def _is_connection_valid(self, conn: sqlite3.Connection) -> bool:
        """Check if connection is still valid."""
        try:
            # Simple query to test connection
            conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def _cleanup_idle_connections(self):
        """Clean up idle connections."""
        current_time = time.time()
        connections_to_close = []

        with self._lock:
            for conn_id, timestamp in self._connection_timestamps.items():
                if current_time - timestamp > self.max_idle_time:
                    connections_to_close.append(conn_id)

        # Close idle connections
        for conn_id in connections_to_close:
            try:
                # Find connection in pool
                temp_pool = []
                closed_conn = None

                while not self._pool.empty():
                    try:
                        conn = self._pool.get_nowait()
                        if id(conn) == conn_id:
                            closed_conn = conn
                        else:
                            temp_pool.append(conn)
                    except Empty:
                        break

                # Put back non-idle connections
                for conn in temp_pool:
                    try:
                        self._pool.put_nowait(conn)
                    except:
                        self._close_connection(conn)

                # Close idle connection
                if closed_conn:
                    self._close_connection(closed_conn)
                    self._stats.available_connections -= 1

            except Exception as e:
                self.logger.warning("Error cleaning up idle connection",
                                  error_category=ErrorCategory.DATABASE_ERROR,
                                  structured_data={'connection_id': conn_id, 'error': str(e)})

    @contextmanager
    def get_connection(self):
        """
        Get a database connection from the pool.

        Yields:
            SQLite connection object

        Raises:
            ConnectionPoolTimeout: If no connection available within timeout
        """
        conn = None
        conn_id = None

        try:
            with self._lock:
                self._stats.connection_requests += 1

            # Try to get connection from pool
            try:
                conn = self._pool.get(timeout=self.connection_timeout)
                conn_id = id(conn)

                with self._lock:
                    self._stats.available_connections -= 1
                    self._connection_timestamps[conn_id] = time.time()

                # Validate connection
                if not self._is_connection_valid(conn):
                    self.logger.warning("Invalid connection retrieved from pool, creating new one")
                    self._close_connection(conn)
                    conn = self._create_connection()
                    if not conn:
                        raise ConnectionPoolError("Failed to create replacement connection")

            except Empty:
                # Pool is empty, create new connection if under limit
                with self._lock:
                    if len(self._active_connections) < self.max_connections:
                        conn = self._create_connection()
                        if conn:
                            conn_id = id(conn)
                        else:
                            raise ConnectionPoolError("Failed to create new connection")
                    else:
                        self._stats.connection_timeouts += 1
                        raise ConnectionPoolTimeout(
                            f"No connections available within {self.connection_timeout}s timeout"
                        )

            # Update stats
            with self._lock:
                self._stats.active_connections = len(self._active_connections)

            yield conn

        except Exception as e:
            with self._lock:
                self._stats.connection_errors += 1
            raise e

        finally:
            # Return connection to pool
            if conn:
                try:
                    # Validate connection before returning to pool
                    if self._is_connection_valid(conn):
                        try:
                            self._pool.put_nowait(conn)
                            with self._lock:
                                self._stats.available_connections += 1
                        except:
                            # Pool is full, close connection
                            self._close_connection(conn)
                    else:
                        # Connection is invalid, close it
                        self._close_connection(conn)
                except Exception as e:
                    self.logger.warning("Error returning connection to pool",
                                      error_category=ErrorCategory.DATABASE_ERROR,
                                      structured_data={'error': str(e)})
                    try:
                        self._close_connection(conn)
                    except:
                        pass

    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        with self._lock:
            return {
                'total_connections_created': self._stats.total_connections_created,
                'active_connections': self._stats.active_connections,
                'available_connections': self._stats.available_connections,
                'connection_requests': self._stats.connection_requests,
                'connection_timeouts': self._stats.connection_timeouts,
                'connection_errors': self._stats.connection_errors,
                'pool_utilization': (self._stats.active_connections / self.max_connections) * 100 if self.max_connections > 0 else 0
            }

    def close_all(self):
        """Close all connections in the pool."""
        closed_count = 0

        while True:
            try:
                conn = self._pool.get_nowait()
                self._close_connection(conn)
                closed_count += 1
            except Empty:
                break

        with self._lock:
            self._active_connections.clear()
            self._connection_timestamps.clear()

        self.logger.info("Closed all connections in pool",
                        structured_data={'connections_closed': closed_count})


class ConnectionPoolTimeout(Exception):
    """Exception raised when connection pool times out."""
    pass


class ConnectionPoolError(Exception):
    """Exception raised for connection pool errors."""
    pass


class ResilientDatabase:
    """
    Database wrapper with resilience features including connection pooling,
    retry mechanisms, and circuit breaker integration.
    """

    def __init__(self,
                 database_path: str,
                 circuit_breaker_name: str = "database",
                 max_connections: int = 10,
                 logger=None):
        """
        Initialize resilient database.

        Args:
            database_path: Path to SQLite database file
            circuit_breaker_name: Name for circuit breaker
            max_connections: Maximum connections in pool
            logger: Structured logger instance
        """
        self.database_path = database_path
        self.circuit_breaker_name = circuit_breaker_name
        self.logger = logger or get_structured_logger("resilient_database")

        # Initialize connection pool
        self.connection_pool = ConnectionPool(
            database_path=database_path,
            max_connections=max_connections,
            logger=self.logger
        )

        # Initialize circuit breaker
        self.circuit_breaker = get_circuit_breaker(
            circuit_breaker_name,
            failure_threshold=5,
            recovery_timeout=60.0
        )

        self.logger.info("Resilient database initialized",
                        structured_data={
                            'database_path': database_path,
                            'circuit_breaker': circuit_breaker_name,
                            'max_connections': max_connections
                        })

    @contextmanager
    def get_connection(self):
        """
        Get a database connection with resilience features.

        Yields:
            SQLite connection object
        """
        try:
            # Use circuit breaker
            with self.circuit_breaker.protect():
                with self.connection_pool.get_connection() as conn:
                    yield conn

        except CircuitBreakerOpen as e:
            self.logger.warning("Database circuit breaker is open",
                              error_category=ErrorCategory.DATABASE_ERROR,
                              structured_data={'circuit_breaker': self.circuit_breaker_name})
            raise e

        except Exception as e:
            self.logger.error("Database connection error",
                            error_category=ErrorCategory.DATABASE_ERROR,
                            structured_data={'error': str(e)})
            raise e

    @retry_database_operation
    def execute_query(self, query: str, parameters: tuple = None) -> List[tuple]:
        """
        Execute a SELECT query with resilience.

        Args:
            query: SQL query string
            parameters: Query parameters

        Returns:
            Query results as list of tuples
        """
        with self.get_connection() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(query, parameters or ())
                results = cursor.fetchall()
                cursor.close()
                return results
            except Exception as e:
                self.logger.error("Query execution failed",
                                error_category=ErrorCategory.DATABASE_ERROR,
                                structured_data={
                                    'query': query[:100] + '...' if len(query) > 100 else query,
                                    'error': str(e)
                                })
                raise e

    @retry_database_operation
    def execute_update(self, query: str, parameters: tuple = None) -> int:
        """
        Execute an INSERT/UPDATE/DELETE query with resilience.

        Args:
            query: SQL query string
            parameters: Query parameters

        Returns:
            Number of affected rows
        """
        with self.get_connection() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(query, parameters or ())
                affected_rows = cursor.rowcount
                conn.commit()
                cursor.close()
                return affected_rows
            except Exception as e:
                conn.rollback()
                self.logger.error("Update execution failed",
                                error_category=ErrorCategory.DATABASE_ERROR,
                                structured_data={
                                    'query': query[:100] + '...' if len(query) > 100 else query,
                                    'error': str(e)
                                })
                raise e

    @retry_database_operation
    def execute_script(self, script: str) -> None:
        """
        Execute a SQL script with resilience.

        Args:
            script: SQL script to execute
        """
        with self.get_connection() as conn:
            try:
                conn.executescript(script)
                conn.commit()
            except Exception as e:
                conn.rollback()
                self.logger.error("Script execution failed",
                                error_category=ErrorCategory.DATABASE_ERROR,
                                structured_data={
                                    'script_length': len(script),
                                    'error': str(e)
                                })
                raise e

    def get_stats(self) -> Dict[str, Any]:
        """Get database resilience statistics."""
        return {
            'connection_pool': self.connection_pool.get_stats(),
            'circuit_breaker': self.circuit_breaker.get_stats()
        }

    def close(self):
        """Close database and cleanup resources."""
        try:
            self.connection_pool.close_all()
            self.logger.info("Resilient database closed")
        except Exception as e:
            self.logger.error("Error closing resilient database",
                            error_category=ErrorCategory.DATABASE_ERROR,
                            structured_data={'error': str(e)})


# Global database instances registry
_database_instances = {}
_database_lock = threading.RLock()


def get_resilient_database(database_path: str,
                          circuit_breaker_name: str = None,
                          **kwargs) -> ResilientDatabase:
    """
    Get or create a resilient database instance.

    Args:
        database_path: Path to database file
        circuit_breaker_name: Optional circuit breaker name
        **kwargs: Additional arguments for ResilientDatabase

    Returns:
        ResilientDatabase instance
    """
    if circuit_breaker_name is None:
        circuit_breaker_name = f"db_{hash(database_path) % 1000}"

    key = f"{database_path}:{circuit_breaker_name}"

    with _database_lock:
        if key not in _database_instances:
            _database_instances[key] = ResilientDatabase(
                database_path=database_path,
                circuit_breaker_name=circuit_breaker_name,
                **kwargs
            )

        return _database_instances[key]


def close_all_databases():
    """Close all resilient database instances."""
    with _database_lock:
        for db in _database_instances.values():
            try:
                db.close()
            except Exception:
                pass
        _database_instances.clear()