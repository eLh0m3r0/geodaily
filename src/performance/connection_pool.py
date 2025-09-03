"""
Connection pooling and performance optimization for HTTP requests.
"""

import time
import threading
from typing import Dict, Any, List, Optional
from urllib3 import PoolManager, HTTPSConnectionPool, Retry
from urllib3.util import Retry as RetryConfig
import requests.adapters
import ssl

from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage


class ConnectionPoolManager:
    """
    Manages HTTP connection pools for improved performance and resource usage.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_structured_logger("connection_pool")
        self.pools: Dict[str, PoolManager] = {}
        self.pool_configs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

        # Default pool configuration
        self.default_config = {
            'maxsize': 10,  # Maximum connections per pool
            'block': True,  # Block when pool is full
            'retries': Retry(
                total=3,
                backoff_factor=0.3,
                status_forcelist=[500, 502, 503, 504]
            ),
            'timeout': 30.0
        }

    def get_pool(self, domain: str, config: Optional[Dict[str, Any]] = None, ssl_config: Optional[Dict[str, Any]] = None) -> PoolManager:
        """
        Get or create a connection pool for a domain.

        Args:
            domain: Domain name
            config: Custom pool configuration
            ssl_config: SSL configuration for HTTPS requests

        Returns:
            Connection pool for the domain
        """
        with self._lock:
            pool_key = f"{domain}_{str(ssl_config) if ssl_config else 'default'}"

            if pool_key not in self.pools:
                pool_config = {**self.default_config}
                if config:
                    pool_config.update(config)

                self.pool_configs[pool_key] = pool_config

                try:
                    # Handle SSL configuration for HTTPS domains
                    if ssl_config:
                        # Create HTTPSConnectionPool with SSL configuration
                        pool_kwargs = {
                            'host': domain,
                            'port': 443,
                            'maxsize': pool_config['maxsize'],
                            'block': pool_config['block'],
                            'retries': pool_config['retries']
                        }

                        # Configure SSL context
                        if 'cert_reqs' in ssl_config and ssl_config['cert_reqs'] == 'CERT_NONE':
                            ssl_context = ssl.create_default_context()
                            ssl_context.check_hostname = False
                            ssl_context.verify_mode = ssl.CERT_NONE
                            pool_kwargs['ssl_context'] = ssl_context

                        if 'assert_hostname' in ssl_config and not ssl_config['assert_hostname']:
                            if 'ssl_context' not in pool_kwargs:
                                pool_kwargs['ssl_context'] = ssl.create_default_context()
                            pool_kwargs['ssl_context'].check_hostname = False

                        pool = HTTPSConnectionPool(**pool_kwargs)

                        self.logger.debug("Created SSL-configured HTTPS connection pool",
                                        structured_data={
                                            'domain': domain,
                                            'ssl_config': ssl_config,
                                            'ssl_context_configured': 'ssl_context' in pool_kwargs
                                        })
                    else:
                        # Create regular PoolManager for HTTP or default HTTPS
                        pool = PoolManager(
                            maxsize=pool_config['maxsize'],
                            block=pool_config['block'],
                            retries=pool_config['retries']
                        )

                    self.pools[pool_key] = pool

                    self.logger.debug("Created connection pool",
                                    structured_data={
                                        'domain': domain,
                                        'pool_key': pool_key,
                                        'maxsize': pool_config['maxsize'],
                                        'retries': pool_config['retries'].total if hasattr(pool_config['retries'], 'total') else 3,
                                        'ssl_configured': ssl_config is not None
                                    })

                except Exception as e:
                    self.logger.error("Failed to create connection pool",
                                    error_category=ErrorCategory.UNKNOWN_ERROR,
                                    structured_data={
                                        'domain': domain,
                                        'pool_key': pool_key,
                                        'error': str(e)
                                    })
                    raise

            return self.pools[pool_key]

    def make_request(self, url: str, method: str = 'GET', **kwargs) -> requests.Response:
        """
        Make HTTP request using connection pooling.

        Args:
            url: Request URL
            method: HTTP method
            **kwargs: Additional request parameters

        Returns:
            HTTP response
        """
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc

        # Extract SSL parameters from kwargs for HTTPS requests
        ssl_config = None
        request_kwargs = kwargs.copy()

        if parsed.scheme == 'https':
            ssl_params = {}
            if 'cert_reqs' in request_kwargs:
                ssl_params['cert_reqs'] = request_kwargs.pop('cert_reqs')
            if 'assert_hostname' in request_kwargs:
                ssl_params['assert_hostname'] = request_kwargs.pop('assert_hostname')

            if ssl_params:
                ssl_config = ssl_params

        pool = self.get_pool(domain, ssl_config=ssl_config)

        # Set default timeout if not provided
        pool_key = f"{domain}_{str(ssl_config) if ssl_config else 'default'}"
        if 'timeout' not in request_kwargs:
            request_kwargs['timeout'] = self.pool_configs[pool_key]['timeout']

        start_time = time.time()

        try:
            # For HTTPS requests, use the pool
            if parsed.scheme == 'https':
                self.logger.debug("Making HTTPS request via connection pool",
                           structured_data={
                               'url': url,
                               'method': method,
                               'ssl_config': ssl_config,
                               'pool_type': type(pool).__name__,
                               'request_kwargs_keys': list(request_kwargs.keys())
                           })

                if isinstance(pool, HTTPSConnectionPool):
                    # For HTTPSConnectionPool, we need to extract path from URL
                    from urllib.parse import urlparse
                    parsed_url = urlparse(url)
                    path = parsed_url.path
                    if parsed_url.query:
                        path += '?' + parsed_url.query

                    response = pool.request(method, path, **request_kwargs)
                else:
                    # For regular PoolManager
                    response = pool.request(method, url, **request_kwargs)

                # Convert urllib3 response to requests-like response for compatibility
                return self._convert_urllib3_response(response)
            else:
                # For HTTP or other schemes, fall back to requests
                return requests.request(method, url, **request_kwargs)

        except Exception as e:
            response_time = time.time() - start_time
            self.logger.error("Connection pool request failed",
                            error_category=ErrorCategory.NETWORK_ERROR,
                            structured_data={
                                'url': url,
                                'method': method,
                                'domain': domain,
                                'ssl_config': ssl_config,
                                'response_time': response_time,
                                'error': str(e)
                            })
            raise

    def _convert_urllib3_response(self, urllib3_response) -> requests.Response:
        """Convert urllib3 response to requests.Response for compatibility."""
        # This is a simplified conversion - in production you'd want a more complete implementation
        class CompatibleResponse:
            def __init__(self, urllib3_resp):
                self.status_code = urllib3_resp.status
                self.content = urllib3_resp.data
                self.headers = dict(urllib3_resp.headers)
                self.url = urllib3_resp.geturl()
                self.text = urllib3_resp.data.decode('utf-8', errors='ignore')

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.exceptions.HTTPError(f"{self.status_code} Client Error")

            def json(self):
                import json
                return json.loads(self.text)

        return CompatibleResponse(urllib3_response)

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get statistics for all connection pools."""
        with self._lock:
            stats = {}
            for domain, pool in self.pools.items():
                pool_stats = {
                    'domain': domain,
                    'config': self.pool_configs.get(domain, {}),
                    'active_connections': getattr(pool, 'num_connections', 0),
                    'available_connections': getattr(pool, 'num_connections', 0)  # Simplified
                }
                stats[domain] = pool_stats

            return {
                'total_pools': len(self.pools),
                'pools': stats,
                'timestamp': time.time()
            }

    def cleanup(self):
        """Clean up connection pools."""
        with self._lock:
            for domain, pool in self.pools.items():
                try:
                    pool.clear()
                    self.logger.debug("Cleaned up connection pool",
                                    structured_data={'domain': domain})
                except Exception as e:
                    self.logger.warning("Error cleaning up connection pool",
                                      structured_data={
                                          'domain': domain,
                                          'error': str(e)
                                      })

            self.pools.clear()
            self.pool_configs.clear()


class EnhancedThreadPoolExecutor:
    """
    Enhanced thread pool executor with performance monitoring and optimization.
    """

    def __init__(self, max_workers: int = 10, logger=None):
        self.logger = logger or get_structured_logger("thread_pool")
        self.max_workers = max_workers
        self.executor = None
        self.task_stats = {
            'submitted': 0,
            'completed': 0,
            'failed': 0,
            'total_execution_time': 0.0,
            'average_execution_time': 0.0
        }
        self._lock = threading.RLock()

    def __enter__(self):
        from concurrent.futures import ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.logger.debug("Enhanced thread pool executor started",
                        structured_data={'max_workers': self.max_workers})
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.executor:
            self.executor.shutdown(wait=True)
            self.logger.debug("Enhanced thread pool executor shut down",
                            structured_data=self.task_stats)

    def submit(self, fn, *args, **kwargs):
        """Submit task with monitoring."""
        with self._lock:
            self.task_stats['submitted'] += 1

        future = self.executor.submit(self._monitored_task, fn, *args, **kwargs)
        return future

    def _monitored_task(self, fn, *args, **kwargs):
        """Execute task with monitoring."""
        start_time = time.time()
        try:
            result = fn(*args, **kwargs)
            execution_time = time.time() - start_time

            with self._lock:
                self.task_stats['completed'] += 1
                self.task_stats['total_execution_time'] += execution_time
                self.task_stats['average_execution_time'] = (
                    self.task_stats['total_execution_time'] / self.task_stats['completed']
                )

            return result

        except Exception as e:
            execution_time = time.time() - start_time

            with self._lock:
                self.task_stats['failed'] += 1
                self.task_stats['total_execution_time'] += execution_time

            self.logger.error("Task execution failed",
                            error_category=ErrorCategory.UNKNOWN_ERROR,
                            structured_data={
                                'execution_time': execution_time,
                                'error': str(e)
                            })
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        with self._lock:
            return {
                **self.task_stats,
                'success_rate': (self.task_stats['completed'] /
                               max(self.task_stats['submitted'], 1)) * 100,
                'max_workers': self.max_workers,
                'timestamp': time.time()
            }


class PerformanceOptimizer:
    """
    Performance optimization utilities for the newsletter pipeline.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_structured_logger("performance_optimizer")
        self.connection_pool = ConnectionPoolManager(logger=self.logger)
        self.metrics = {
            'requests_total': 0,
            'requests_successful': 0,
            'requests_failed': 0,
            'total_response_time': 0.0,
            'average_response_time': 0.0
        }

    def optimize_collection_batch_size(self, total_items: int, max_workers: int = 10) -> int:
        """
        Calculate optimal batch size for parallel processing.

        Args:
            total_items: Total number of items to process
            max_workers: Maximum number of workers

        Returns:
            Optimal batch size
        """
        if total_items <= max_workers:
            return 1

        # Aim for 2-3 batches per worker for optimal throughput
        optimal_batches = max_workers * 2
        batch_size = max(1, total_items // optimal_batches)

        self.logger.debug("Calculated optimal batch size",
                        structured_data={
                            'total_items': total_items,
                            'max_workers': max_workers,
                            'optimal_batches': optimal_batches,
                            'batch_size': batch_size
                        })

        return batch_size

    def create_optimized_thread_pool(self, max_workers: int = 10) -> EnhancedThreadPoolExecutor:
        """Create optimized thread pool executor."""
        return EnhancedThreadPoolExecutor(max_workers=max_workers, logger=self.logger)

    def get_connection_pool(self) -> ConnectionPoolManager:
        """Get connection pool manager."""
        return self.connection_pool

    def record_request_metrics(self, success: bool, response_time: float):
        """Record HTTP request metrics."""
        self.metrics['requests_total'] += 1

        if success:
            self.metrics['requests_successful'] += 1
        else:
            self.metrics['requests_failed'] += 1

        self.metrics['total_response_time'] += response_time
        self.metrics['average_response_time'] = (
            self.metrics['total_response_time'] / self.metrics['requests_total']
        )

    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report."""
        return {
            'http_metrics': {
                **self.metrics,
                'success_rate': (self.metrics['requests_successful'] /
                               max(self.metrics['requests_total'], 1)) * 100
            },
            'connection_pools': self.connection_pool.get_pool_stats(),
            'timestamp': time.time()
        }

    def cleanup(self):
        """Clean up resources."""
        self.connection_pool.cleanup()
        self.logger.info("Performance optimizer cleaned up")


# Global instances
connection_pool_manager = ConnectionPoolManager()
performance_optimizer = PerformanceOptimizer()