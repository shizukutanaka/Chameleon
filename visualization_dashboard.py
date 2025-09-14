#!/usr/bin/env python3
"""
Advanced Visualization and Monitoring Dashboard
Real-time system monitoring with interactive visualizations
"""

import logging
import threading
import time
import json
import asyncio
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, deque
import http.server
import socketserver
import urllib.parse
import uuid
import base64
import gzip

# Optional visualization dependencies
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from system_monitor import SystemMonitor
from performance_optimizer import PerformanceOptimizer
from automated_diagnostics import AutomatedDiagnosticsManager
from error_recovery import ErrorRecoveryManager

class ChartType(Enum):
    """Chart visualization types"""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"

class DashboardTheme(Enum):
    """Dashboard visual themes"""
    LIGHT = "light"
    DARK = "dark"
    HIGH_CONTRAST = "high_contrast"

@dataclass
class ChartConfig:
    """Configuration for a chart"""
    chart_id: str
    title: str
    chart_type: ChartType
    data_source: str
    refresh_interval: int = 30  # seconds
    width: int = 400
    height: int = 300
    color_scheme: List[str] = field(default_factory=lambda: ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"])
    show_legend: bool = True
    grid: bool = True

@dataclass
class DashboardWidget:
    """Individual dashboard widget"""
    widget_id: str
    title: str
    widget_type: str  # "chart", "metric", "alert", "log"
    config: Dict[str, Any]
    position: Tuple[int, int]  # x, y grid position
    size: Tuple[int, int]  # width, height in grid units
    data: Any = None
    last_updated: Optional[datetime] = None

class DataCollector:
    """Collects data from various system components"""
    
    def __init__(self, system_monitor: Optional[SystemMonitor] = None,
                 performance_optimizer: Optional[PerformanceOptimizer] = None,
                 diagnostics_manager: Optional[AutomatedDiagnosticsManager] = None,
                 error_recovery: Optional[ErrorRecoveryManager] = None):
        
        self.system_monitor = system_monitor
        self.performance_optimizer = performance_optimizer
        self.diagnostics_manager = diagnostics_manager
        self.error_recovery = error_recovery
        
        # Data storage
        self.metrics_history = defaultdict(lambda: deque(maxlen=1000))
        self.real_time_data = {}
        self.lock = threading.RLock()
        
        # Start data collection
        self._start_collection()
    
    def _start_collection(self):
        """Start background data collection"""
        def collect_data():
            while True:
                try:
                    self._collect_system_metrics()
                    self._collect_performance_metrics()
                    self._collect_diagnostic_data()
                    self._collect_error_metrics()
                    time.sleep(5)  # Collect every 5 seconds
                except Exception as e:
                    logging.error(f"Data collection error: {e}")
                    time.sleep(10)
        
        collection_thread = threading.Thread(target=collect_data, daemon=True)
        collection_thread.start()
    
    def _collect_system_metrics(self):
        """Collect system monitoring metrics"""
        if not self.system_monitor:
            return
        
        try:
            status = self.system_monitor.get_system_status()
            timestamp = datetime.now()
            
            with self.lock:
                # Store time-series data
                self.metrics_history["cpu_usage"].append((timestamp, status.get("cpu_percent", 0)))
                self.metrics_history["memory_usage"].append((timestamp, status.get("memory_percent", 0)))
                self.metrics_history["disk_usage"].append((timestamp, status.get("disk_percent", 0)))
                self.metrics_history["network_sent"].append((timestamp, status.get("network_sent", 0)))
                self.metrics_history["network_recv"].append((timestamp, status.get("network_recv", 0)))
                
                # Store current values
                self.real_time_data["system"] = status
                
        except Exception as e:
            logging.error(f"System metrics collection error: {e}")
    
    def _collect_performance_metrics(self):
        """Collect performance optimization metrics"""
        if not self.performance_optimizer:
            return
        
        try:
            report = self.performance_optimizer.get_system_performance_report()
            timestamp = datetime.now()
            
            with self.lock:
                # Extract component performance data
                for component, data in report.get("component_performance", {}).items():
                    key = f"component_{component}_avg_time"
                    self.metrics_history[key].append((timestamp, data.get("avg_execution_time", 0)))
                
                # Store current performance data
                self.real_time_data["performance"] = report
                
        except Exception as e:
            logging.error(f"Performance metrics collection error: {e}")
    
    def _collect_diagnostic_data(self):
        """Collect diagnostic information"""
        if not self.diagnostics_manager:
            return
        
        try:
            health_summary = self.diagnostics_manager.get_system_health_summary()
            timestamp = datetime.now()
            
            with self.lock:
                # Store health score over time
                self.metrics_history["health_score"].append((timestamp, health_summary.get("health_score", 100)))
                
                # Store severity distribution
                severity_dist = health_summary.get("summary", {}).get("severity_distribution", {})
                for severity, count in severity_dist.items():
                    key = f"diagnostic_{severity}"
                    self.metrics_history[key].append((timestamp, count))
                
                # Store current diagnostic data
                self.real_time_data["diagnostics"] = health_summary
                
        except Exception as e:
            logging.error(f"Diagnostic data collection error: {e}")
    
    def _collect_error_metrics(self):
        """Collect error recovery metrics"""
        if not self.error_recovery:
            return
        
        try:
            stats = self.error_recovery.get_error_statistics()
            timestamp = datetime.now()
            
            with self.lock:
                # Store error counts over time
                self.metrics_history["total_errors"].append((timestamp, stats.get("total_errors", 0)))
                self.metrics_history["recent_errors"].append((timestamp, stats.get("recent_errors_1h", 0)))
                
                # Store error recovery stats
                recovery_stats = stats.get("recovery_stats", {})
                successful = recovery_stats.get("successful_recoveries", 0)
                failed = recovery_stats.get("failed_recoveries", 0)
                total = successful + failed
                success_rate = (successful / total * 100) if total > 0 else 100
                
                self.metrics_history["recovery_success_rate"].append((timestamp, success_rate))
                
                # Store current error data
                self.real_time_data["errors"] = stats
                
        except Exception as e:
            logging.error(f"Error metrics collection error: {e}")
    
    def get_time_series_data(self, metric_name: str, time_range: timedelta = timedelta(hours=1)) -> List[Tuple[datetime, float]]:
        """Get time series data for a metric"""
        with self.lock:
            if metric_name not in self.metrics_history:
                return []
            
            cutoff = datetime.now() - time_range
            return [(ts, value) for ts, value in self.metrics_history[metric_name] if ts >= cutoff]
    
    def get_current_data(self, data_source: str) -> Dict[str, Any]:
        """Get current real-time data"""
        with self.lock:
            return self.real_time_data.get(data_source, {})

class ChartRenderer:
    """Renders charts and visualizations"""
    
    def __init__(self, theme: DashboardTheme = DashboardTheme.LIGHT):
        self.theme = theme
        self.logger = logging.getLogger("ChartRenderer")
        
        # Set theme colors
        if theme == DashboardTheme.DARK:
            self.bg_color = '#2b2b2b'
            self.text_color = '#ffffff'
            self.grid_color = '#404040'
        elif theme == DashboardTheme.HIGH_CONTRAST:
            self.bg_color = '#000000'
            self.text_color = '#ffffff'
            self.grid_color = '#808080'
        else:  # LIGHT
            self.bg_color = '#ffffff'
            self.text_color = '#000000'
            self.grid_color = '#e0e0e0'
    
    def render_chart(self, config: ChartConfig, data: List[Tuple[datetime, float]]) -> Optional[str]:
        """Render chart and return base64 encoded image"""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_text_chart(config, data)
        
        try:
            fig = plt.figure(figsize=(config.width/100, config.height/100), facecolor=self.bg_color)
            ax = fig.add_subplot(111, facecolor=self.bg_color)
            
            if not data:
                ax.text(0.5, 0.5, 'No Data Available', ha='center', va='center', 
                       color=self.text_color, fontsize=12)
            else:
                timestamps, values = zip(*data)
                
                if config.chart_type == ChartType.LINE:
                    ax.plot(timestamps, values, color=config.color_scheme[0], linewidth=2)
                elif config.chart_type == ChartType.BAR:
                    ax.bar(range(len(values)), values, color=config.color_scheme[0])
                    ax.set_xticks(range(0, len(timestamps), max(1, len(timestamps)//10)))
                elif config.chart_type == ChartType.SCATTER:
                    ax.scatter(timestamps, values, color=config.color_scheme[0], alpha=0.6)
                
                ax.set_xlabel('Time', color=self.text_color)
                ax.set_ylabel('Value', color=self.text_color)
                
                if config.chart_type == ChartType.LINE and len(timestamps) > 1:
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=10))
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            ax.set_title(config.title, color=self.text_color, fontsize=14, fontweight='bold')
            ax.tick_params(colors=self.text_color)
            
            if config.grid:
                ax.grid(True, color=self.grid_color, alpha=0.3)
            
            # Set background colors
            ax.spines['bottom'].set_color(self.text_color)
            ax.spines['top'].set_color(self.text_color)
            ax.spines['right'].set_color(self.text_color)
            ax.spines['left'].set_color(self.text_color)
            
            plt.tight_layout()
            
            # Convert to base64
            canvas = FigureCanvasAgg(fig)
            canvas.draw()
            
            import io
            buf = io.BytesIO()
            canvas.print_png(buf)
            buf.seek(0)
            
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            plt.close(fig)
            
            return f"data:image/png;base64,{img_base64}"
            
        except Exception as e:
            self.logger.error(f"Chart rendering error: {e}")
            return None
    
    def render_gauge_chart(self, config: ChartConfig, value: float, min_val: float = 0, max_val: float = 100) -> Optional[str]:
        """Render a gauge chart"""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_text_gauge(config, value, min_val, max_val)
        
        try:
            fig = plt.figure(figsize=(config.width/100, config.height/100), facecolor=self.bg_color)
            ax = fig.add_subplot(111, facecolor=self.bg_color)
            
            # Create gauge
            theta = np.linspace(0, np.pi, 100)
            r = np.ones_like(theta)
            
            # Color based on value
            if value < 50:
                color = '#2ca02c'  # Green
            elif value < 80:
                color = '#ff7f0e'  # Orange
            else:
                color = '#d62728'  # Red
            
            ax.plot(theta, r, color=self.grid_color, linewidth=10, alpha=0.3)
            
            # Value indicator
            value_theta = np.pi * (1 - (value - min_val) / (max_val - min_val))
            ax.plot([value_theta, value_theta], [0, 1], color=color, linewidth=5)
            
            # Add value text
            ax.text(0, -0.3, f"{value:.1f}", ha='center', va='center', 
                   color=self.text_color, fontsize=16, fontweight='bold')
            
            ax.set_xlim(-0.1, np.pi + 0.1)
            ax.set_ylim(-0.5, 1.1)
            ax.set_aspect('equal')
            ax.axis('off')
            ax.set_title(config.title, color=self.text_color, fontsize=14, fontweight='bold')
            
            plt.tight_layout()
            
            # Convert to base64
            canvas = FigureCanvasAgg(fig)
            canvas.draw()
            
            import io
            buf = io.BytesIO()
            canvas.print_png(buf)
            buf.seek(0)
            
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            plt.close(fig)
            
            return f"data:image/png;base64,{img_base64}"
            
        except Exception as e:
            self.logger.error(f"Gauge rendering error: {e}")
            return None
    
    def _create_text_chart(self, config: ChartConfig, data: List[Tuple[datetime, float]]) -> str:
        """Create simple text-based chart when matplotlib is not available"""
        if not data:
            return f"data:text/plain;base64,{base64.b64encode(f'{config.title}: No Data'.encode()).decode()}"
        
        values = [v for _, v in data[-20:]]  # Last 20 points
        max_val = max(values) if values else 0
        min_val = min(values) if values else 0
        
        chart_text = f"{config.title}\n"
        chart_text += "-" * 40 + "\n"
        
        for i, (ts, val) in enumerate(data[-10:]):  # Last 10 points
            bar_length = int((val - min_val) / (max_val - min_val) * 30) if max_val > min_val else 0
            bar = "█" * bar_length + "░" * (30 - bar_length)
            chart_text += f"{ts.strftime('%H:%M')} {bar} {val:.1f}\n"
        
        return f"data:text/plain;base64,{base64.b64encode(chart_text.encode()).decode()}"
    
    def _create_text_gauge(self, config: ChartConfig, value: float, min_val: float, max_val: float) -> str:
        """Create text-based gauge"""
        percentage = (value - min_val) / (max_val - min_val) * 100 if max_val > min_val else 0
        
        gauge_text = f"{config.title}\n"
        gauge_text += f"Value: {value:.1f}\n"
        gauge_text += f"Range: {min_val:.1f} - {max_val:.1f}\n"
        
        # ASCII gauge
        filled = int(percentage / 10)
        gauge_text += "["
        gauge_text += "█" * filled
        gauge_text += "░" * (10 - filled)
        gauge_text += f"] {percentage:.1f}%"
        
        return f"data:text/plain;base64,{base64.b64encode(gauge_text.encode()).decode()}"

class DashboardManager:
    """Manages dashboard configuration and widgets"""
    
    def __init__(self, data_collector: DataCollector, 
                 theme: DashboardTheme = DashboardTheme.LIGHT):
        self.data_collector = data_collector
        self.chart_renderer = ChartRenderer(theme)
        self.widgets = {}
        self.dashboard_config = {
            "title": "Chameleon Audio System Dashboard",
            "theme": theme.value,
            "refresh_interval": 30,
            "grid_size": (12, 8)  # 12 columns, 8 rows
        }
        
        # Initialize default widgets
        self._create_default_widgets()
        
        # Update tracking
        self.last_update = datetime.now()
        self.lock = threading.RLock()
    
    def _create_default_widgets(self):
        """Create default dashboard widgets"""
        
        # System CPU Usage Chart
        self.add_widget(DashboardWidget(
            widget_id="cpu_usage_chart",
            title="CPU Usage",
            widget_type="chart",
            config=ChartConfig(
                chart_id="cpu_usage",
                title="CPU Usage (%)",
                chart_type=ChartType.LINE,
                data_source="cpu_usage",
                color_scheme=["#1f77b4"]
            ).__dict__,
            position=(0, 0),
            size=(6, 2)
        ))
        
        # Memory Usage Chart
        self.add_widget(DashboardWidget(
            widget_id="memory_usage_chart",
            title="Memory Usage",
            widget_type="chart",
            config=ChartConfig(
                chart_id="memory_usage",
                title="Memory Usage (%)",
                chart_type=ChartType.LINE,
                data_source="memory_usage",
                color_scheme=["#ff7f0e"]
            ).__dict__,
            position=(6, 0),
            size=(6, 2)
        ))
        
        # System Health Gauge
        self.add_widget(DashboardWidget(
            widget_id="health_gauge",
            title="System Health",
            widget_type="gauge",
            config=ChartConfig(
                chart_id="health_score",
                title="Health Score",
                chart_type=ChartType.GAUGE,
                data_source="health_score"
            ).__dict__,
            position=(0, 2),
            size=(3, 2)
        ))
        
        # Error Recovery Rate
        self.add_widget(DashboardWidget(
            widget_id="recovery_rate_gauge",
            title="Recovery Success Rate",
            widget_type="gauge",
            config=ChartConfig(
                chart_id="recovery_success_rate",
                title="Recovery Rate (%)",
                chart_type=ChartType.GAUGE,
                data_source="recovery_success_rate"
            ).__dict__,
            position=(3, 2),
            size=(3, 2)
        ))
        
        # Network Activity
        self.add_widget(DashboardWidget(
            widget_id="network_chart",
            title="Network Activity",
            widget_type="chart",
            config=ChartConfig(
                chart_id="network_activity",
                title="Network I/O",
                chart_type=ChartType.LINE,
                data_source="network_sent",
                color_scheme=["#2ca02c", "#d62728"]
            ).__dict__,
            position=(6, 2),
            size=(6, 2)
        ))
        
        # System Metrics Table
        self.add_widget(DashboardWidget(
            widget_id="system_metrics",
            title="Current Metrics",
            widget_type="metric",
            config={"data_source": "system"},
            position=(0, 4),
            size=(12, 2)
        ))
        
        # Recent Alerts
        self.add_widget(DashboardWidget(
            widget_id="recent_alerts",
            title="Recent Alerts",
            widget_type="alert",
            config={"data_source": "diagnostics", "max_items": 10},
            position=(0, 6),
            size=(12, 2)
        ))
    
    def add_widget(self, widget: DashboardWidget):
        """Add widget to dashboard"""
        with self.lock:
            self.widgets[widget.widget_id] = widget
    
    def remove_widget(self, widget_id: str):
        """Remove widget from dashboard"""
        with self.lock:
            if widget_id in self.widgets:
                del self.widgets[widget_id]
    
    def update_widget_data(self, widget_id: str):
        """Update data for a specific widget"""
        if widget_id not in self.widgets:
            return
        
        widget = self.widgets[widget_id]
        
        try:
            if widget.widget_type == "chart":
                config = ChartConfig(**widget.config)
                data = self.data_collector.get_time_series_data(config.data_source)
                
                if config.chart_type == ChartType.GAUGE:
                    # For gauge, get latest value
                    latest_value = data[-1][1] if data else 0
                    widget.data = self.chart_renderer.render_gauge_chart(config, latest_value)
                else:
                    widget.data = self.chart_renderer.render_chart(config, data)
                    
            elif widget.widget_type == "gauge":
                config = ChartConfig(**widget.config)
                data = self.data_collector.get_time_series_data(config.data_source)
                latest_value = data[-1][1] if data else 0
                widget.data = self.chart_renderer.render_gauge_chart(config, latest_value)
                
            elif widget.widget_type == "metric":
                data_source = widget.config.get("data_source", "system")
                widget.data = self.data_collector.get_current_data(data_source)
                
            elif widget.widget_type == "alert":
                data_source = widget.config.get("data_source", "diagnostics")
                max_items = widget.config.get("max_items", 10)
                current_data = self.data_collector.get_current_data(data_source)
                
                # Extract recent critical issues
                alerts = current_data.get("recent_critical_issues", [])[:max_items]
                widget.data = alerts
            
            widget.last_updated = datetime.now()
            
        except Exception as e:
            logging.error(f"Error updating widget {widget_id}: {e}")
            widget.data = None
    
    def update_all_widgets(self):
        """Update data for all widgets"""
        with self.lock:
            for widget_id in self.widgets:
                self.update_widget_data(widget_id)
            self.last_update = datetime.now()
    
    def get_dashboard_html(self) -> str:
        """Generate HTML dashboard"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{self.dashboard_config['title']}</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: {"#2b2b2b" if self.dashboard_config['theme'] == 'dark' else "#f5f5f5"};
                    color: {"#ffffff" if self.dashboard_config['theme'] == 'dark' else "#000000"};
                }}
                .dashboard-header {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .dashboard-grid {{
                    display: grid;
                    grid-template-columns: repeat(12, 1fr);
                    grid-template-rows: repeat(8, 150px);
                    gap: 15px;
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                .widget {{
                    background: {"#404040" if self.dashboard_config['theme'] == 'dark' else "#ffffff"};
                    border-radius: 8px;
                    padding: 15px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .widget-title {{
                    font-weight: bold;
                    margin-bottom: 10px;
                    color: {"#ffffff" if self.dashboard_config['theme'] == 'dark' else "#333333"};
                }}
                .chart-container {{
                    width: 100%;
                    height: calc(100% - 30px);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .chart-image {{
                    max-width: 100%;
                    max-height: 100%;
                }}
                .metric-table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                .metric-table th, .metric-table td {{
                    text-align: left;
                    padding: 8px;
                    border-bottom: 1px solid {"#555555" if self.dashboard_config['theme'] == 'dark' else "#ddd"};
                }}
                .alert-item {{
                    margin-bottom: 8px;
                    padding: 8px;
                    border-radius: 4px;
                    background: {"#6b2737" if self.dashboard_config['theme'] == 'dark' else "#ffebee"};
                    border-left: 4px solid #d32f2f;
                }}
                .status-indicator {{
                    display: inline-block;
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    margin-right: 8px;
                }}
                .status-healthy {{ background-color: #4caf50; }}
                .status-warning {{ background-color: #ff9800; }}
                .status-critical {{ background-color: #f44336; }}
                .last-updated {{
                    font-size: 12px;
                    color: {"#cccccc" if self.dashboard_config['theme'] == 'dark' else "#666666"};
                    text-align: center;
                    margin-top: 20px;
                }}
            </style>
            <script>
                function refreshDashboard() {{
                    location.reload();
                }}
                setInterval(refreshDashboard, {self.dashboard_config['refresh_interval'] * 1000});
            </script>
        </head>
        <body>
            <div class="dashboard-header">
                <h1>{self.dashboard_config['title']}</h1>
                <div class="status-indicator status-healthy"></div>
                System Online - Last Updated: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}
            </div>
            
            <div class="dashboard-grid">
        """
        
        # Add widgets
        for widget_id, widget in self.widgets.items():
            col_span = widget.size[0]
            row_span = widget.size[1]
            col_start = widget.position[0] + 1
            row_start = widget.position[1] + 1
            
            html += f"""
                <div class="widget" style="grid-column: {col_start} / span {col_span}; grid-row: {row_start} / span {row_span};">
                    <div class="widget-title">{widget.title}</div>
            """
            
            if widget.widget_type in ["chart", "gauge"]:
                if widget.data:
                    if widget.data.startswith("data:image/"):
                        html += f'<div class="chart-container"><img src="{widget.data}" class="chart-image" alt="{widget.title}"></div>'
                    else:
                        # Text chart
                        chart_text = base64.b64decode(widget.data.split(',')[1]).decode('utf-8')
                        html += f'<div class="chart-container"><pre style="font-size: 10px; margin: 0;">{chart_text}</pre></div>'
                else:
                    html += '<div class="chart-container">No data available</div>'
                    
            elif widget.widget_type == "metric":
                if widget.data:
                    html += '<table class="metric-table">'
                    for key, value in widget.data.items():
                        if isinstance(value, (int, float)):
                            html += f'<tr><td>{key.replace("_", " ").title()}</td><td>{value:.2f}</td></tr>'
                        else:
                            html += f'<tr><td>{key.replace("_", " ").title()}</td><td>{value}</td></tr>'
                    html += '</table>'
                else:
                    html += '<div>No metrics available</div>'
                    
            elif widget.widget_type == "alert":
                if widget.data:
                    for alert in widget.data:
                        timestamp = alert.get('timestamp', 'Unknown')
                        message = alert.get('message', 'No message')
                        html += f'<div class="alert-item"><strong>{timestamp}</strong><br>{message}</div>'
                else:
                    html += '<div>No recent alerts</div>'
            
            html += "</div>"
        
        html += """
            </div>
            <div class="last-updated">
                Dashboard automatically refreshes every {} seconds
            </div>
        </body>
        </html>
        """.format(self.dashboard_config['refresh_interval'])
        
        return html

class DashboardServer:
    """HTTP server for dashboard"""
    
    def __init__(self, dashboard_manager: DashboardManager, port: int = 8080):
        self.dashboard_manager = dashboard_manager
        self.port = port
        self.server = None
        self.server_thread = None
        self.logger = logging.getLogger("DashboardServer")
    
    def start(self):
        """Start the dashboard server"""
        try:
            handler = self._create_handler()
            self.server = socketserver.TCPServer(("", self.port), handler)
            
            def serve():
                self.logger.info(f"Dashboard server starting on port {self.port}")
                self.server.serve_forever()
            
            self.server_thread = threading.Thread(target=serve, daemon=True)
            self.server_thread.start()
            
            self.logger.info(f"Dashboard available at http://localhost:{self.port}")
            
        except Exception as e:
            self.logger.error(f"Failed to start dashboard server: {e}")
    
    def stop(self):
        """Stop the dashboard server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.logger.info("Dashboard server stopped")
    
    def _create_handler(self):
        """Create HTTP request handler"""
        dashboard_manager = self.dashboard_manager
        
        class DashboardHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/' or self.path == '/dashboard':
                    # Update dashboard data
                    dashboard_manager.update_all_widgets()
                    
                    # Generate HTML
                    html = dashboard_manager.get_dashboard_html()
                    
                    # Send response
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.send_header('Content-length', len(html.encode('utf-8')))
                    self.end_headers()
                    self.wfile.write(html.encode('utf-8'))
                    
                elif self.path.startswith('/api/'):
                    # API endpoints
                    self._handle_api_request()
                else:
                    self.send_error(404)
            
            def _handle_api_request(self):
                """Handle API requests"""
                if self.path == '/api/metrics':
                    # Return current metrics as JSON
                    metrics = dashboard_manager.data_collector.real_time_data
                    response = json.dumps(metrics, default=str)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Content-length', len(response.encode('utf-8')))
                    self.end_headers()
                    self.wfile.write(response.encode('utf-8'))
                else:
                    self.send_error(404)
            
            def log_message(self, format, *args):
                # Suppress HTTP server logs
                pass
        
        return DashboardHandler

class VisualizationDashboard:
    """Main visualization dashboard class"""
    
    def __init__(self, system_monitor: Optional[SystemMonitor] = None,
                 performance_optimizer: Optional[PerformanceOptimizer] = None,
                 diagnostics_manager: Optional[AutomatedDiagnosticsManager] = None,
                 error_recovery: Optional[ErrorRecoveryManager] = None,
                 port: int = 8080,
                 theme: DashboardTheme = DashboardTheme.LIGHT):
        
        # Initialize components
        self.data_collector = DataCollector(
            system_monitor=system_monitor,
            performance_optimizer=performance_optimizer,
            diagnostics_manager=diagnostics_manager,
            error_recovery=error_recovery
        )
        
        self.dashboard_manager = DashboardManager(self.data_collector, theme)
        self.server = DashboardServer(self.dashboard_manager, port)
        
        self.logger = logging.getLogger("VisualizationDashboard")
    
    def start(self):
        """Start the visualization dashboard"""
        self.server.start()
        self.logger.info("Visualization dashboard started")
    
    def stop(self):
        """Stop the visualization dashboard"""
        self.server.stop()
        self.logger.info("Visualization dashboard stopped")
    
    def add_custom_widget(self, widget: DashboardWidget):
        """Add custom widget to dashboard"""
        self.dashboard_manager.add_widget(widget)
    
    def get_dashboard_url(self) -> str:
        """Get dashboard URL"""
        return f"http://localhost:{self.server.port}"

# Global visualization dashboard instance
_global_visualization_dashboard = None

def get_global_visualization_dashboard() -> VisualizationDashboard:
    """Get or create global visualization dashboard"""
    global _global_visualization_dashboard
    if _global_visualization_dashboard is None:
        _global_visualization_dashboard = VisualizationDashboard()
    return _global_visualization_dashboard

if __name__ == "__main__":
    # Example usage
    from system_monitor import get_global_system_monitor
    from performance_optimizer import get_global_performance_optimizer
    from automated_diagnostics import get_global_diagnostics_manager
    from error_recovery import get_global_recovery_manager
    
    # Create dashboard with all components
    dashboard = VisualizationDashboard(
        system_monitor=get_global_system_monitor(),
        performance_optimizer=get_global_performance_optimizer(),
        diagnostics_manager=get_global_diagnostics_manager(),
        error_recovery=get_global_recovery_manager(),
        port=8080,
        theme=DashboardTheme.DARK
    )
    
    # Start dashboard
    dashboard.start()
    
    print(f"Dashboard available at: {dashboard.get_dashboard_url()}")
    print("Press Ctrl+C to stop...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        dashboard.stop()
        print("Dashboard stopped")