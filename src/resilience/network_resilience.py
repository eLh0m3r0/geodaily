"""
Network resilience layer with multiple failure handling strategies.
"""

import time
import random
import socket
import requests
from typing import Any, Callable, Optional, Dict, List, Union
from urllib.parse import urlparse
from dataclasses import dataclass, field

from ..logging_system import get_structured_logger, ErrorCategory, PipelineStage
from .circuit_breaker import get_circuit_breaker, CircuitBreakerOpen
from .retry_mechanisms import RetryConfig, retry_with_config


@dataclass
class NetworkEndpoint:
    """Network endpoint configuration."""
    url: str
    timeout: float = 30.0
    retries: int = 3
    backoff_factor: float = 2.0
    headers: Dict[str, str] = field(default_factory=dict)
    proxies: Optional[Dict[str, str]] = None
    verify_ssl: bool = True


@dataclass
class NetworkStats:
    """Network operation statistics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_errors: int = 0
    connection_errors: int = 0
    dns_errors: int = 0
    ssl_errors: int = 0
    rate_limit_errors: int = 0
    total_response_time: float = 0.0


class NetworkResilienceManager:
    """
    Manages network operations with multiple resilience strategies.
    """

    def __init__(self, logger=None):
        self.logger = logger or get_structured_logger("network_resilience")
        self.stats = NetworkStats()
        self.circuits = {}

        # Default retry configuration
        self.default_retry_config = RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=60.0,
            backoff_factor=2.0,
            jitter_range=0.1,
            retryable_exceptions=[
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.TooManyRedirects,
                requests.exceptions.RequestException
            ]
        )

    def _get_circuit_breaker(self, endpoint: NetworkEndpoint) -> Any:
        """Get or create circuit breaker for endpoint."""
        domain = urlparse(endpoint.url).netloc
        circuit_name = f"network_{domain}"

        if circuit_name not in self.circuits:
            self.circuits[circuit_name] = get_circuit_breaker(
                circuit_name,
                failure_threshold=5,
                recovery_timeout=120.0  # 2 minutes
            )

        return self.circuits[circuit_name]

    def _record_request_stats(self, success: bool, response_time: float, error_type: str = None):
        """Record network request statistics."""
        self.stats.total_requests += 1
        self.stats.total_response_time += response_time

        if success:
            self.stats.successful_requests += 1
        else:
            self.stats.failed_requests += 1

            if error_type:
                if 'timeout' in error_type.lower():
                    self.stats.timeout_errors += 1
                elif 'connection' in error_type.lower():
                    self.stats.connection_errors += 1
                elif 'dns' in error_type.lower() or 'name resolution' in error_type.lower():
                    self.stats.dns_errors += 1
                elif 'ssl' in error_type.lower():
                    self.stats.ssl_errors += 1
                elif 'rate' in error_type.lower() or '429' in error_type:
                    self.stats.rate_limit_errors += 1

    def make_resilient_request(self,
                             endpoint: NetworkEndpoint,
                             method: str = 'GET',
                             data: Any = None,
                             json_data: Any = None,
                             retry_config: Optional[RetryConfig] = None) -> requests.Response:
        """
        Make HTTP request with resilience features.

        Args:
            endpoint: Network endpoint configuration
            method: HTTP method
            data: Request data
            json_data: JSON request data
            retry_config: Custom retry configuration

        Returns:
            HTTP response

        Raises:
            CircuitBreakerOpen: If circuit breaker is open
            Exception: If request fails after all retries
        """
        config = retry_config or self.default_retry_config
        circuit_breaker = self._get_circuit_breaker(endpoint)

        # Prepare request parameters
        request_params = {
            'method': method,
            'url': endpoint.url,
            'timeout': endpoint.timeout,
            'headers': endpoint.headers,
            'proxies': endpoint.proxies,
            'verify': endpoint.verify_ssl
        }

        if data is not None:
            request_params['data'] = data
        if json_data is not None:
            request_params['json'] = json_data

        last_exception = None
        start_time = time.time()

        for attempt in range(config.max_attempts):
            try:
                # Check circuit breaker
                with circuit_breaker.protect():
                    response = requests.request(**request_params)

                    # Record success
                    response_time = time.time() - start_time
                    self._record_request_stats(True, response_time)

                    self.logger.debug("Network request successful",
                                    structured_data={
                                        'url': endpoint.url,
                                        'method': method,
                                        'status_code': response.status_code,
                                        'response_time': response_time,
                                        'attempt': attempt + 1
                                    })

                    return response

            except CircuitBreakerOpen as e:
                self.logger.warning("Network circuit breaker open",
                                  error_category=ErrorCategory.NETWORK_ERROR,
                                  structured_data={
                                      'endpoint': endpoint.url,
                                      'circuit_breaker': circuit_breaker.name
                                  })
                raise e

            except requests.exceptions.Timeout as e:
                last_exception = e
                error_type = 'timeout'
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                error_type = 'connection'
            except requests.exceptions.SSLError as e:
                last_exception = e
                error_type = 'ssl'
            except requests.exceptions.TooManyRedirects as e:
                last_exception = e
                error_type = 'redirect'
            except requests.exceptions.RequestException as e:
                last_exception = e
                error_type = 'request'

            # Record failure
            response_time = time.time() - start_time
            self._record_request_stats(False, response_time, error_type)

            # Don't retry on last attempt
            if attempt == config.max_attempts - 1:
                break

            # Calculate delay
            delay = min(config.base_delay * (config.backoff_factor ** attempt), config.max_delay)

            # Add jitter
            if config.jitter_range > 0:
                jitter = random.uniform(-config.jitter_range, config.jitter_range) * delay
                delay += jitter

            self.logger.warning("Network request failed, retrying",
                              error_category=ErrorCategory.NETWORK_ERROR,
                              structured_data={
                                  'endpoint': endpoint.url,
                                  'method': method,
                                  'attempt': attempt + 1,
                                  'max_attempts': config.max_attempts,
                                  'delay_seconds': delay,
                                  'error_type': error_type,
                                  'error_message': str(last_exception)
                              })

            time.sleep(delay)

        # All attempts failed
        self.logger.error("Network request failed after all retries",
                         error_category=ErrorCategory.NETWORK_ERROR,
                         structured_data={
                             'endpoint': endpoint.url,
                             'method': method,
                             'total_attempts': config.max_attempts,
                             'total_time': time.time() - start_time,
                             'last_error': str(last_exception)
                         })

        raise last_exception

    def test_connectivity(self, endpoint: NetworkEndpoint) -> Dict[str, Any]:
        """
        Test network connectivity to endpoint.

        Args:
            endpoint: Network endpoint to test

        Returns:
            Connectivity test results
        """
        results = {
            'endpoint': endpoint.url,
            'reachable': False,
            'response_time': None,
            'error': None,
            'dns_resolved': False,
            'port_open': False
        }

        try:
            parsed = urlparse(endpoint.url)
            hostname = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)

            # Test DNS resolution
            start_time = time.time()
            try:
                ip_address = socket.gethostbyname(hostname)
                results['dns_resolved'] = True
                results['ip_address'] = ip_address
            except socket.gaierror as e:
                results['error'] = f"DNS resolution failed: {e}"
                return results

            # Test port connectivity
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)

            try:
                sock.connect((ip_address, port))
                results['port_open'] = True
                sock.close()
            except (socket.timeout, socket.error) as e:
                results['error'] = f"Port connection failed: {e}"
                sock.close()
                return results

            # Test HTTP connectivity
            try:
                response = self.make_resilient_request(
                    endpoint,
                    method='HEAD',
                    retry_config=RetryConfig(max_attempts=1, base_delay=0)
                )
                results['reachable'] = True
                results['response_time'] = time.time() - start_time
                results['status_code'] = response.status_code

            except Exception as e:
                results['error'] = f"HTTP request failed: {e}"

        except Exception as e:
            results['error'] = f"Connectivity test failed: {e}"

        self.logger.info("Connectivity test completed",
                        structured_data=results)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get network resilience statistics."""
        circuit_stats = {}
        for name, circuit in self.circuits.items():
            circuit_stats[name] = circuit.get_stats()

        return {
            'network_stats': {
                'total_requests': self.stats.total_requests,
                'successful_requests': self.stats.successful_requests,
                'failed_requests': self.stats.failed_requests,
                'success_rate': (self.stats.successful_requests / max(self.stats.total_requests, 1)) * 100,
                'average_response_time': self.stats.total_response_time / max(self.stats.total_requests, 1),
                'timeout_errors': self.stats.timeout_errors,
                'connection_errors': self.stats.connection_errors,
                'dns_errors': self.stats.dns_errors,
                'ssl_errors': self.stats.ssl_errors,
                'rate_limit_errors': self.stats.rate_limit_errors
            },
            'circuit_breakers': circuit_stats
        }


class RSSResilienceManager(NetworkResilienceManager):
    """
    Specialized resilience manager for RSS feed operations.
    """

    def __init__(self, logger=None):
        super().__init__(logger)
        self.feed_circuits = {}

    def fetch_rss_feed(self, feed_url: str, timeout: float = 30.0) -> str:
        """
        Fetch RSS feed with resilience features.

        Args:
            feed_url: RSS feed URL
            timeout: Request timeout

        Returns:
            RSS feed content
        """
        endpoint = NetworkEndpoint(
            url=feed_url,
            timeout=timeout,
            headers={
                'User-Agent': 'GeopoliticalDaily/1.0 (RSS Reader)',
                'Accept': 'application/rss+xml, application/xml, text/xml'
            }
        )

        try:
            response = self.make_resilient_request(endpoint)
            response.raise_for_status()

            self.logger.debug("RSS feed fetched successfully",
                            structured_data={
                                'feed_url': feed_url,
                                'content_length': len(response.text),
                                'status_code': response.status_code
                            })

            return response.text

        except Exception as e:
            self.logger.error("Failed to fetch RSS feed",
                            error_category=ErrorCategory.NETWORK_ERROR,
                            structured_data={
                                'feed_url': feed_url,
                                'error': str(e)
                            })
            raise e


class WebScrapingResilienceManager(NetworkResilienceManager):
    """
    Specialized resilience manager for web scraping operations.
    """

    def __init__(self, logger=None):
        super().__init__(logger)

        # Configure for web scraping
        self.default_retry_config.retryable_exceptions.extend([
            requests.exceptions.HTTPError,
            ValueError,  # For parsing errors
        ])

    def scrape_webpage(self,
                      url: str,
                      timeout: float = 30.0,
                      user_agent: str = None) -> str:
        """
        Scrape webpage with resilience features.

        Args:
            url: Webpage URL
            timeout: Request timeout
            user_agent: Custom user agent string

        Returns:
            Webpage HTML content
        """
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        if user_agent:
            headers['User-Agent'] = user_agent
        else:
            headers['User-Agent'] = 'Mozilla/5.0 (compatible; GeopoliticalDaily/1.0)'

        endpoint = NetworkEndpoint(
            url=url,
            timeout=timeout,
            headers=headers
        )

        try:
            response = self.make_resilient_request(endpoint)
            response.raise_for_status()

            self.logger.debug("Webpage scraped successfully",
                            structured_data={
                                'url': url,
                                'content_length': len(response.text),
                                'status_code': response.status_code,
                                'content_type': response.headers.get('content-type', 'unknown')
                            })

            return response.text

        except Exception as e:
            self.logger.error("Failed to scrape webpage",
                            error_category=ErrorCategory.NETWORK_ERROR,
                            structured_data={
                                'url': url,
                                'error': str(e)
                            })
            raise e


# Global instances
network_manager = NetworkResilienceManager()
rss_manager = RSSResilienceManager()
scraping_manager = WebScrapingResilienceManager()