"""
Log analysis tools for debugging, optimization, and insights.
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict, Counter
import statistics

from .structured_logger import StructuredLogger, ErrorCategory, PipelineStage
from ..config import Config


class LogAnalyzer:
    """Analyzes log files for insights and debugging."""

    def __init__(self, logs_dir: Optional[Path] = None):
        """Initialize log analyzer."""
        self.logs_dir = logs_dir or Config.LOGS_DIR
        self.logger = StructuredLogger("log_analyzer")

    def analyze_logs(self, hours: int = 24, pipeline_stages: Optional[List[str]] = None) -> Dict[str, Any]:
        """Analyze recent logs for comprehensive insights."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        analysis = {
            'time_range': {'start': cutoff_time.isoformat(), 'end': datetime.now().isoformat()},
            'summary': {
                'total_entries': 0,
                'error_count': 0,
                'warning_count': 0,
                'info_count': 0,
                'debug_count': 0
            },
            'performance': {
                'slow_operations': [],
                'average_execution_times': {},
                'memory_usage_trends': [],
                'cpu_usage_trends': []
            },
            'errors': {
                'by_category': {},
                'by_stage': {},
                'error_patterns': {},
                'most_common_errors': []
            },
            'pipeline': {
                'stage_execution_times': {},
                'stage_success_rates': {},
                'bottlenecks': []
            },
            'system': {
                'log_file_sizes': {},
                'log_rotation_events': [],
                'configuration_issues': []
            }
        }

        # Analyze each log file
        for log_file in self.logs_dir.glob("*.log"):
            try:
                file_stats = self._analyze_log_file(log_file, cutoff_time, pipeline_stages)
                self._merge_analysis(analysis, file_stats)

            except Exception as e:
                self.logger.error(f"Failed to analyze log file {log_file.name}: {e}",
                                error_category=ErrorCategory.UNKNOWN_ERROR)

        # Post-process analysis
        self._post_process_analysis(analysis)

        return analysis

    def _analyze_log_file(self, log_file: Path, cutoff_time: datetime,
                         pipeline_stages: Optional[List[str]] = None) -> Dict[str, Any]:
        """Analyze a single log file."""
        file_stats = {
            'entries': [],
            'performance_data': [],
            'error_data': [],
            'stage_data': defaultdict(list)
        }

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        entry = json.loads(line.strip())
                        entry_time = datetime.fromisoformat(entry['timestamp'])

                        if entry_time < cutoff_time:
                            continue

                        # Filter by pipeline stages if specified
                        if pipeline_stages and entry.get('pipeline_stage') not in pipeline_stages:
                            continue

                        file_stats['entries'].append(entry)

                        # Collect performance data
                        if entry.get('performance_data'):
                            file_stats['performance_data'].append(entry['performance_data'])

                        # Collect error data
                        if entry.get('error_category'):
                            file_stats['error_data'].append({
                                'category': entry['error_category'],
                                'stage': entry.get('pipeline_stage'),
                                'level': entry['level'],
                                'timestamp': entry['timestamp']
                            })

                        # Collect stage data
                        if entry.get('pipeline_stage'):
                            stage = entry['pipeline_stage']
                            file_stats['stage_data'][stage].append(entry)

                    except json.JSONDecodeError:
                        # Log malformed lines
                        self.logger.warning(f"Malformed log entry in {log_file.name}:{line_num}")
                        continue

        except Exception as e:
            self.logger.error(f"Error reading log file {log_file.name}: {e}")

        return file_stats

    def _merge_analysis(self, analysis: Dict[str, Any], file_stats: Dict[str, Any]):
        """Merge file statistics into main analysis."""
        # Update summary counts
        for entry in file_stats['entries']:
            analysis['summary']['total_entries'] += 1
            level = entry['level']
            if level == 'ERROR':
                analysis['summary']['error_count'] += 1
            elif level == 'WARNING':
                analysis['summary']['warning_count'] += 1
            elif level == 'INFO':
                analysis['summary']['info_count'] += 1
            elif level == 'DEBUG':
                analysis['summary']['debug_count'] += 1

        # Merge performance data
        analysis['performance']['memory_usage_trends'].extend(
            [p.get('memory_delta_mb', 0) for p in file_stats['performance_data']]
        )
        analysis['performance']['cpu_usage_trends'].extend(
            [p.get('cpu_usage_percent', 0) for p in file_stats['performance_data']]
        )

        # Merge error data
        for error in file_stats['error_data']:
            category = error['category']
            stage = error['stage']

            # Count by category
            analysis['errors']['by_category'][category] = \
                analysis['errors']['by_category'].get(category, 0) + 1

            # Count by stage
            if stage:
                if stage not in analysis['errors']['by_stage']:
                    analysis['errors']['by_stage'][stage] = {}
                analysis['errors']['by_stage'][stage][category] = \
                    analysis['errors']['by_stage'][stage].get(category, 0) + 1

    def _post_process_analysis(self, analysis: Dict[str, Any]):
        """Post-process analysis data for insights."""
        # Calculate error rates
        total_entries = analysis['summary']['total_entries']
        if total_entries > 0:
            analysis['summary']['error_rate'] = analysis['summary']['error_count'] / total_entries
            analysis['summary']['warning_rate'] = analysis['summary']['warning_count'] / total_entries

        # Find most common errors
        error_categories = analysis['errors']['by_category']
        analysis['errors']['most_common_errors'] = sorted(
            error_categories.items(), key=lambda x: x[1], reverse=True
        )[:10]

        # Calculate average memory and CPU usage
        if analysis['performance']['memory_usage_trends']:
            analysis['performance']['avg_memory_delta_mb'] = statistics.mean(
                analysis['performance']['memory_usage_trends']
            )

        if analysis['performance']['cpu_usage_trends']:
            analysis['performance']['avg_cpu_usage_percent'] = statistics.mean(
                analysis['performance']['cpu_usage_trends']
            )

        # Identify potential bottlenecks
        analysis['pipeline']['bottlenecks'] = self._identify_bottlenecks(analysis)

    def _identify_bottlenecks(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify potential performance bottlenecks."""
        bottlenecks = []

        # Check for high error rates by stage
        for stage, errors in analysis['errors']['by_stage'].items():
            total_errors = sum(errors.values())
            if total_errors > 5:  # Threshold for bottleneck detection
                bottlenecks.append({
                    'type': 'high_error_rate',
                    'stage': stage,
                    'error_count': total_errors,
                    'severity': 'high' if total_errors > 10 else 'medium'
                })

        # Check for memory issues
        if analysis['performance'].get('avg_memory_delta_mb', 0) > 50:  # 50MB threshold
            bottlenecks.append({
                'type': 'memory_usage',
                'average_delta_mb': analysis['performance']['avg_memory_delta_mb'],
                'severity': 'high'
            })

        # Check for CPU issues
        if analysis['performance'].get('avg_cpu_usage_percent', 0) > 80:  # 80% threshold
            bottlenecks.append({
                'type': 'cpu_usage',
                'average_percent': analysis['performance']['avg_cpu_usage_percent'],
                'severity': 'high'
            })

        return bottlenecks

    def find_error_patterns(self, hours: int = 24) -> Dict[str, Any]:
        """Find recurring error patterns."""
        analysis = self.analyze_logs(hours)

        patterns = {
            'recurring_errors': [],
            'error_sequences': [],
            'stage_correlations': {},
            'temporal_patterns': {}
        }

        # Group errors by type and message
        error_groups = defaultdict(list)
        for entry in analysis.get('entries', []):
            if entry.get('level') in ['ERROR', 'CRITICAL']:
                key = f"{entry.get('error_category', 'unknown')}:{entry.get('message', '')[:100]}"
                error_groups[key].append(entry)

        # Find recurring patterns
        for pattern_key, errors in error_groups.items():
            if len(errors) > 1:
                patterns['recurring_errors'].append({
                    'pattern': pattern_key,
                    'count': len(errors),
                    'first_occurrence': min(e['timestamp'] for e in errors),
                    'last_occurrence': max(e['timestamp'] for e in errors),
                    'affected_stages': list(set(e.get('pipeline_stage') for e in errors if e.get('pipeline_stage')))
                })

        return patterns

    def generate_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate a performance report."""
        analysis = self.analyze_logs(hours)

        report = {
            'summary': {
                'analysis_period_hours': hours,
                'total_log_entries': analysis['summary']['total_entries'],
                'performance_entries': len(analysis['performance']['memory_usage_trends'])
            },
            'metrics': {
                'average_memory_delta_mb': analysis['performance'].get('avg_memory_delta_mb'),
                'average_cpu_usage_percent': analysis['performance'].get('avg_cpu_usage_percent'),
                'error_rate': analysis['summary'].get('error_rate', 0)
            },
            'bottlenecks': analysis['pipeline']['bottlenecks'],
            'recommendations': []
        }

        # Generate recommendations
        if report['metrics']['error_rate'] > 0.1:  # 10% error rate
            report['recommendations'].append({
                'priority': 'high',
                'issue': 'High error rate detected',
                'recommendation': 'Review error patterns and implement additional error handling'
            })

        if report['metrics'].get('average_memory_delta_mb', 0) > 100:
            report['recommendations'].append({
                'priority': 'medium',
                'issue': 'High memory usage',
                'recommendation': 'Consider optimizing memory usage or increasing system resources'
            })

        if report['metrics'].get('average_cpu_usage_percent', 0) > 90:
            report['recommendations'].append({
                'priority': 'high',
                'issue': 'High CPU usage',
                'recommendation': 'Monitor CPU-intensive operations and consider optimization'
            })

        return report

    def search_logs(self, query: str, hours: int = 24,
                   case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """Search logs for specific patterns."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        matches = []

        flags = 0 if case_sensitive else re.IGNORECASE

        try:
            pattern = re.compile(query, flags)
        except re.error as e:
            self.logger.error(f"Invalid regex pattern: {e}")
            return matches

        for log_file in self.logs_dir.glob("*.log"):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        try:
                            entry = json.loads(line.strip())
                            entry_time = datetime.fromisoformat(entry['timestamp'])

                            if entry_time < cutoff_time:
                                continue

                            # Search in message and structured data
                            searchable_text = entry.get('message', '')
                            if entry.get('contextual_data'):
                                searchable_text += json.dumps(entry['contextual_data'])

                            if pattern.search(searchable_text):
                                matches.append({
                                    'file': log_file.name,
                                    'line': line_num,
                                    'entry': entry
                                })

                        except json.JSONDecodeError:
                            continue

            except Exception as e:
                self.logger.error(f"Error searching log file {log_file.name}: {e}")

        return matches

    def export_analysis(self, analysis: Dict[str, Any], output_file: Path):
        """Export analysis results to a file."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2, default=str)

            self.logger.info(f"Analysis exported to {output_file}")

        except Exception as e:
            self.logger.error(f"Failed to export analysis: {e}")


class LogDashboard:
    """Generates dashboard data from log analysis."""

    def __init__(self, analyzer: LogAnalyzer):
        """Initialize log dashboard."""
        self.analyzer = analyzer

    def generate_dashboard_data(self, hours: int = 24) -> Dict[str, Any]:
        """Generate dashboard data for visualization."""
        analysis = self.analyzer.analyze_logs(hours)

        dashboard = {
            'timestamp': datetime.now().isoformat(),
            'time_range_hours': hours,
            'summary_cards': {
                'total_logs': analysis['summary']['total_entries'],
                'error_rate': analysis['summary'].get('error_rate', 0),
                'warning_rate': analysis['summary'].get('warning_rate', 0),
                'avg_memory_mb': analysis['performance'].get('avg_memory_delta_mb', 0)
            },
            'charts': {
                'error_trends': self._generate_error_trends(analysis),
                'performance_trends': self._generate_performance_trends(analysis),
                'stage_performance': self._generate_stage_performance(analysis)
            },
            'alerts': self._generate_alerts(analysis),
            'insights': self._generate_insights(analysis)
        }

        return dashboard

    def _generate_error_trends(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate error trend data for charts."""
        # Group errors by time buckets (hourly)
        error_timeline = defaultdict(int)

        # This would require parsing timestamps from entries
        # For now, return placeholder structure
        return {
            'labels': [],  # Time labels
            'datasets': [{
                'label': 'Errors',
                'data': []
            }]
        }

    def _generate_performance_trends(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate performance trend data."""
        return {
            'memory_usage': analysis['performance']['memory_usage_trends'][-50:],  # Last 50 data points
            'cpu_usage': analysis['performance']['cpu_usage_trends'][-50:]
        }

    def _generate_stage_performance(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate stage performance data."""
        return {
            'stages': list(analysis['errors']['by_stage'].keys()),
            'error_counts': [sum(errors.values()) for errors in analysis['errors']['by_stage'].values()]
        }

    def _generate_alerts(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alerts based on analysis."""
        alerts = []

        error_rate = analysis['summary'].get('error_rate', 0)
        if error_rate > 0.05:  # 5% error rate threshold
            alerts.append({
                'level': 'warning',
                'message': f'High error rate detected: {error_rate:.2%}',
                'recommendation': 'Review recent errors and implement fixes'
            })

        bottlenecks = analysis['pipeline']['bottlenecks']
        for bottleneck in bottlenecks:
            if bottleneck['severity'] == 'high':
                alerts.append({
                    'level': 'error',
                    'message': f'Performance bottleneck: {bottleneck["type"]}',
                    'recommendation': 'Address performance issues immediately'
                })

        return alerts

    def _generate_insights(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate insights from analysis."""
        insights = []

        # Error insights
        most_common = analysis['errors']['most_common_errors']
        if most_common:
            top_error = most_common[0]
            insights.append({
                'type': 'error_pattern',
                'title': 'Most Common Error',
                'description': f'{top_error[0]} ({top_error[1]} occurrences)',
                'impact': 'high' if top_error[1] > 10 else 'medium'
            })

        # Performance insights
        avg_memory = analysis['performance'].get('avg_memory_delta_mb', 0)
        if avg_memory > 0:
            insights.append({
                'type': 'performance',
                'title': 'Memory Usage',
                'description': f'Average memory delta: {avg_memory:.2f} MB',
                'impact': 'high' if avg_memory > 100 else 'low'
            })

        return insights