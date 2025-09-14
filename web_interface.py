#!/usr/bin/env python3
"""
Mobile and Web Interface System
Progressive web application with mobile-responsive design
"""

import logging
import threading
import time
import json
import asyncio
from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import http.server
import socketserver
import urllib.parse
import base64
import gzip
import mimetypes
import os
import hashlib

# Import system components
from cloud_processor import CloudProcessor, ProcessingPriority
from visualization_dashboard import VisualizationDashboard
from system_monitor import SystemMonitor
from plugin_fault_tolerance import PluginFaultToleranceManager

class InterfaceType(Enum):
    """Interface types"""
    WEB = "web"
    MOBILE_WEB = "mobile_web"
    API = "api"
    WEBSOCKET = "websocket"

class ResponseFormat(Enum):
    """Response format types"""
    HTML = "html"
    JSON = "json"
    XML = "xml"
    CSV = "csv"

@dataclass
class WebRequest:
    """Web request data"""
    method: str
    path: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    body: Optional[str] = None
    user_agent: str = ""
    remote_addr: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class WebResponse:
    """Web response data"""
    status_code: int
    headers: Dict[str, str]
    content: str
    content_type: str = "text/html"
    is_binary: bool = False

class WebInterfaceManager:
    """Manages web interface routing and responses"""
    
    def __init__(self, cloud_processor: Optional[CloudProcessor] = None,
                 dashboard: Optional[VisualizationDashboard] = None,
                 system_monitor: Optional[SystemMonitor] = None,
                 plugin_ft: Optional[PluginFaultToleranceManager] = None):
        
        self.cloud_processor = cloud_processor
        self.dashboard = dashboard  
        self.system_monitor = system_monitor
        self.plugin_ft = plugin_ft
        
        # Routing table
        self.routes = {}
        self.api_routes = {}
        
        # Request tracking
        self.request_history = []
        self.active_sessions = {}
        
        # Configuration
        self.config = {
            "enable_compression": True,
            "cache_static_files": True,
            "max_upload_size": 50 * 1024 * 1024,  # 50MB
            "session_timeout": 3600,  # 1 hour
            "rate_limit_per_minute": 100
        }
        
        # Initialize logging
        self.logger = logging.getLogger("WebInterface")
        
        # Setup routes
        self._setup_routes()
        
        # Static file cache
        self.static_cache = {}
    
    def _setup_routes(self):
        """Setup web interface routes"""
        
        # Main application routes
        self.routes["/"] = self._serve_home
        self.routes["/home"] = self._serve_home
        self.routes["/dashboard"] = self._serve_dashboard
        self.routes["/processor"] = self._serve_processor
        self.routes["/monitor"] = self._serve_monitor
        self.routes["/plugins"] = self._serve_plugins
        self.routes["/settings"] = self._serve_settings
        self.routes["/about"] = self._serve_about
        
        # API routes
        self.api_routes["/api/status"] = self._api_system_status
        self.api_routes["/api/tasks"] = self._api_tasks
        self.api_routes["/api/tasks/submit"] = self._api_submit_task
        self.api_routes["/api/tasks/{task_id}"] = self._api_task_status
        self.api_routes["/api/workers"] = self._api_workers
        self.api_routes["/api/plugins"] = self._api_plugins
        self.api_routes["/api/monitoring"] = self._api_monitoring
        self.api_routes["/api/upload"] = self._api_upload_file
    
    def handle_request(self, request: WebRequest) -> WebResponse:
        """Handle incoming web request"""
        try:
            # Log request
            self.request_history.append(request)
            if len(self.request_history) > 1000:
                self.request_history = self.request_history[-500:]
            
            # Check rate limiting
            if not self._check_rate_limit(request.remote_addr):
                return WebResponse(
                    status_code=429,
                    headers={"Content-Type": "application/json"},
                    content='{"error": "Rate limit exceeded"}'
                )
            
            # Handle API requests
            if request.path.startswith("/api/"):
                return self._handle_api_request(request)
            
            # Handle static files
            if request.path.startswith("/static/"):
                return self._serve_static_file(request)
            
            # Handle application routes
            if request.path in self.routes:
                return self.routes[request.path](request)
            
            # 404 Not Found
            return self._serve_404(request)
            
        except Exception as e:
            self.logger.error(f"Request handling error: {e}")
            return self._serve_error(request, str(e))
    
    def _check_rate_limit(self, remote_addr: str) -> bool:
        """Check if request is within rate limits"""
        # Simple rate limiting - count requests in last minute
        cutoff = datetime.now() - timedelta(minutes=1)
        recent_requests = [r for r in self.request_history 
                          if r.remote_addr == remote_addr and r.timestamp > cutoff]
        
        return len(recent_requests) < self.config["rate_limit_per_minute"]
    
    def _handle_api_request(self, request: WebRequest) -> WebResponse:
        """Handle API request"""
        # Find matching API route
        for route_pattern, handler in self.api_routes.items():
            if self._match_route_pattern(request.path, route_pattern):
                try:
                    result = handler(request)
                    if isinstance(result, dict):
                        content = json.dumps(result, default=str)
                        return WebResponse(
                            status_code=200,
                            headers={"Content-Type": "application/json"},
                            content=content
                        )
                    return result
                except Exception as e:
                    self.logger.error(f"API handler error: {e}")
                    return WebResponse(
                        status_code=500,
                        headers={"Content-Type": "application/json"},
                        content=json.dumps({"error": str(e)})
                    )
        
        return WebResponse(
            status_code=404,
            headers={"Content-Type": "application/json"},
            content='{"error": "API endpoint not found"}'
        )
    
    def _match_route_pattern(self, path: str, pattern: str) -> bool:
        """Match URL path against route pattern"""
        if "{" not in pattern:
            return path == pattern
        
        # Simple pattern matching for {variable} patterns
        path_parts = path.split("/")
        pattern_parts = pattern.split("/")
        
        if len(path_parts) != len(pattern_parts):
            return False
        
        for path_part, pattern_part in zip(path_parts, pattern_parts):
            if pattern_part.startswith("{") and pattern_part.endswith("}"):
                continue  # Variable part matches anything
            if path_part != pattern_part:
                return False
        
        return True
    
    def _serve_home(self, request: WebRequest) -> WebResponse:
        """Serve home page"""
        is_mobile = self._is_mobile_request(request)
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Chameleon Audio System</title>
            <link rel="stylesheet" href="/static/styles.css">
            <link rel="manifest" href="/static/manifest.json">
            <meta name="theme-color" content="#2196F3">
        </head>
        <body class="{'mobile' if is_mobile else 'desktop'}">
            <header class="main-header">
                <nav class="navbar">
                    <div class="nav-brand">
                        <h1>🎵 Chameleon Audio</h1>
                    </div>
                    <div class="nav-menu">
                        <a href="/dashboard" class="nav-link">Dashboard</a>
                        <a href="/processor" class="nav-link">Processor</a>
                        <a href="/monitor" class="nav-link">Monitor</a>
                        <a href="/plugins" class="nav-link">Plugins</a>
                    </div>
                    <div class="nav-toggle">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </nav>
            </header>
            
            <main class="main-content">
                <section class="hero">
                    <div class="hero-content">
                        <h1>Professional Audio Processing System</h1>
                        <p>Advanced cloud-based audio processing with real-time monitoring, plugin ecosystem, and distributed computing capabilities.</p>
                        <div class="hero-actions">
                            <a href="/processor" class="btn btn-primary">Start Processing</a>
                            <a href="/dashboard" class="btn btn-secondary">View Dashboard</a>
                        </div>
                    </div>
                </section>
                
                <section class="features">
                    <div class="feature-grid">
                        <div class="feature-card">
                            <div class="feature-icon">🎯</div>
                            <h3>Real-time Processing</h3>
                            <p>Process audio streams in real-time with low latency and high quality.</p>
                        </div>
                        <div class="feature-card">
                            <div class="feature-icon">☁️</div>
                            <h3>Cloud Integration</h3>
                            <p>Scalable cloud processing with automatic load balancing and cost optimization.</p>
                        </div>
                        <div class="feature-card">
                            <div class="feature-icon">🔌</div>
                            <h3>Plugin Ecosystem</h3>
                            <p>Extensible plugin system with advanced effects and processors.</p>
                        </div>
                        <div class="feature-card">
                            <div class="feature-icon">📊</div>
                            <h3>Advanced Analytics</h3>
                            <p>Comprehensive monitoring and performance analytics dashboard.</p>
                        </div>
                    </div>
                </section>
                
                <section class="system-status">
                    <h2>System Status</h2>
                    <div class="status-grid">
                        <div class="status-card">
                            <h4>Processing Queue</h4>
                            <div class="status-value" id="queue-status">Loading...</div>
                        </div>
                        <div class="status-card">
                            <h4>Active Workers</h4>
                            <div class="status-value" id="worker-status">Loading...</div>
                        </div>
                        <div class="status-card">
                            <h4>System Health</h4>
                            <div class="status-value" id="health-status">Loading...</div>
                        </div>
                    </div>
                </section>
            </main>
            
            <footer class="main-footer">
                <p>&copy; 2024 Chameleon Audio System. Advanced audio processing platform.</p>
            </footer>
            
            <script src="/static/app.js"></script>
        </body>
        </html>
        """
        
        return WebResponse(
            status_code=200,
            headers={"Content-Type": "text/html"},
            content=html
        )
    
    def _serve_processor(self, request: WebRequest) -> WebResponse:
        """Serve audio processor interface"""
        is_mobile = self._is_mobile_request(request)
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Audio Processor - Chameleon</title>
            <link rel="stylesheet" href="/static/styles.css">
        </head>
        <body class="{'mobile' if is_mobile else 'desktop'}">
            <header class="main-header">
                <nav class="navbar">
                    <div class="nav-brand">
                        <a href="/">🎵 Chameleon Audio</a>
                    </div>
                    <div class="nav-menu">
                        <a href="/dashboard" class="nav-link">Dashboard</a>
                        <a href="/processor" class="nav-link active">Processor</a>
                        <a href="/monitor" class="nav-link">Monitor</a>
                        <a href="/plugins" class="nav-link">Plugins</a>
                    </div>
                </nav>
            </header>
            
            <main class="main-content">
                <section class="processor-interface">
                    <h1>Audio Processor</h1>
                    
                    <div class="processor-grid">
                        <div class="upload-section">
                            <h3>Upload Audio</h3>
                            <div class="upload-area" id="upload-area">
                                <div class="upload-icon">📁</div>
                                <p>Drag & drop audio files here or click to browse</p>
                                <input type="file" id="file-input" accept=".wav,.mp3,.flac,.aac" multiple hidden>
                                <button class="btn btn-primary" onclick="document.getElementById('file-input').click()">
                                    Choose Files
                                </button>
                            </div>
                            <div class="file-list" id="file-list"></div>
                        </div>
                        
                        <div class="processing-options">
                            <h3>Processing Options</h3>
                            <form id="processing-form">
                                <div class="option-group">
                                    <label for="task-type">Task Type:</label>
                                    <select id="task-type" name="task_type">
                                        <option value="audio_analysis">Audio Analysis</option>
                                        <option value="format_conversion">Format Conversion</option>
                                        <option value="noise_reduction">Noise Reduction</option>
                                        <option value="audio_enhancement">Audio Enhancement</option>
                                        <option value="transcription">Transcription</option>
                                        <option value="music_separation">Music Separation</option>
                                    </select>
                                </div>
                                
                                <div class="option-group">
                                    <label for="priority">Priority:</label>
                                    <select id="priority" name="priority">
                                        <option value="low">Low</option>
                                        <option value="normal" selected>Normal</option>
                                        <option value="high">High</option>
                                        <option value="urgent">Urgent</option>
                                    </select>
                                </div>
                                
                                <div class="option-group" id="format-options" style="display: none;">
                                    <label for="target-format">Target Format:</label>
                                    <select id="target-format" name="target_format">
                                        <option value="mp3">MP3</option>
                                        <option value="wav">WAV</option>
                                        <option value="flac">FLAC</option>
                                        <option value="aac">AAC</option>
                                    </select>
                                </div>
                                
                                <div class="option-group" id="quality-options" style="display: none;">
                                    <label for="quality">Quality:</label>
                                    <input type="range" id="quality" name="quality" min="0" max="1" step="0.1" value="0.8">
                                    <span id="quality-value">0.8</span>
                                </div>
                                
                                <button type="submit" class="btn btn-success">Start Processing</button>
                            </form>
                        </div>
                    </div>
                    
                    <div class="processing-status">
                        <h3>Processing Status</h3>
                        <div class="task-list" id="task-list">
                            <p class="no-tasks">No active processing tasks</p>
                        </div>
                    </div>
                </section>
            </main>
            
            <script src="/static/processor.js"></script>
        </body>
        </html>
        """
        
        return WebResponse(
            status_code=200,
            headers={"Content-Type": "text/html"},
            content=html
        )
    
    def _serve_dashboard(self, request: WebRequest) -> WebResponse:
        """Serve dashboard interface"""
        if self.dashboard:
            # Redirect to dashboard server
            return WebResponse(
                status_code=302,
                headers={"Location": self.dashboard.get_dashboard_url()},
                content=""
            )
        else:
            # Simple embedded dashboard
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>System Dashboard</title>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <link rel="stylesheet" href="/static/styles.css">
            </head>
            <body>
                <h1>System Dashboard</h1>
                <p>Dashboard functionality requires visualization dashboard component.</p>
                <a href="/" class="btn btn-primary">Back to Home</a>
            </body>
            </html>
            """
            
            return WebResponse(
                status_code=200,
                headers={"Content-Type": "text/html"},
                content=html
            )
    
    def _serve_static_file(self, request: WebRequest) -> WebResponse:
        """Serve static files (CSS, JS, images)"""
        file_path = request.path[8:]  # Remove "/static/" prefix
        
        # Security check - prevent directory traversal
        if ".." in file_path or file_path.startswith("/"):
            return WebResponse(status_code=403, headers={}, content="Forbidden")
        
        # Check cache first
        if self.config["cache_static_files"] and file_path in self.static_cache:
            return self.static_cache[file_path]
        
        # Generate static files
        if file_path == "styles.css":
            content = self._generate_css()
            content_type = "text/css"
        elif file_path == "app.js":
            content = self._generate_js()
            content_type = "application/javascript"
        elif file_path == "processor.js":
            content = self._generate_processor_js()
            content_type = "application/javascript"
        elif file_path == "manifest.json":
            content = self._generate_manifest()
            content_type = "application/json"
        else:
            return WebResponse(status_code=404, headers={}, content="File not found")
        
        response = WebResponse(
            status_code=200,
            headers={
                "Content-Type": content_type,
                "Cache-Control": "public, max-age=3600"
            },
            content=content
        )
        
        # Cache the response
        if self.config["cache_static_files"]:
            self.static_cache[file_path] = response
        
        return response
    
    def _generate_css(self) -> str:
        """Generate CSS styles"""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .main-header {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(0, 0, 0, 0.1);
            position: fixed;
            width: 100%;
            top: 0;
            z-index: 1000;
        }
        
        .navbar {
            max-width: 1200px;
            margin: 0 auto;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .nav-brand h1 {
            color: #2196F3;
            font-size: 1.5rem;
        }
        
        .nav-menu {
            display: flex;
            gap: 2rem;
        }
        
        .nav-link {
            text-decoration: none;
            color: #666;
            font-weight: 500;
            transition: color 0.3s;
        }
        
        .nav-link:hover, .nav-link.active {
            color: #2196F3;
        }
        
        .main-content {
            margin-top: 80px;
            padding: 2rem;
        }
        
        .hero {
            text-align: center;
            padding: 4rem 0;
            color: white;
        }
        
        .hero h1 {
            font-size: 3rem;
            margin-bottom: 1rem;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        }
        
        .hero p {
            font-size: 1.2rem;
            margin-bottom: 2rem;
            max-width: 600px;
            margin-left: auto;
            margin-right: auto;
        }
        
        .hero-actions {
            display: flex;
            gap: 1rem;
            justify-content: center;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            font-size: 1rem;
            font-weight: 500;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s;
            cursor: pointer;
        }
        
        .btn-primary {
            background: #2196F3;
            color: white;
        }
        
        .btn-primary:hover {
            background: #1976D2;
            transform: translateY(-2px);
        }
        
        .btn-secondary {
            background: transparent;
            color: white;
            border: 2px solid white;
        }
        
        .btn-secondary:hover {
            background: white;
            color: #2196F3;
        }
        
        .btn-success {
            background: #4CAF50;
            color: white;
        }
        
        .btn-success:hover {
            background: #45a049;
        }
        
        .features {
            padding: 4rem 0;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            margin: 2rem 0;
        }
        
        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 2rem;
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .feature-card {
            background: rgba(255, 255, 255, 0.9);
            padding: 2rem;
            border-radius: 12px;
            text-align: center;
            transition: transform 0.3s;
        }
        
        .feature-card:hover {
            transform: translateY(-5px);
        }
        
        .feature-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        
        .system-status {
            background: rgba(255, 255, 255, 0.9);
            padding: 2rem;
            border-radius: 12px;
            margin: 2rem 0;
        }
        
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }
        
        .status-card {
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
        }
        
        .status-value {
            font-size: 1.5rem;
            font-weight: bold;
            color: #2196F3;
            margin-top: 0.5rem;
        }
        
        .processor-interface {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 12px;
            padding: 2rem;
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .processor-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin: 2rem 0;
        }
        
        .upload-area {
            border: 2px dashed #ddd;
            border-radius: 8px;
            padding: 2rem;
            text-align: center;
            transition: border-color 0.3s;
        }
        
        .upload-area.dragover {
            border-color: #2196F3;
            background: rgba(33, 150, 243, 0.1);
        }
        
        .upload-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        
        .option-group {
            margin-bottom: 1rem;
        }
        
        .option-group label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 500;
        }
        
        .option-group select,
        .option-group input {
            width: 100%;
            padding: 0.5rem;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        
        .task-list {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 1rem;
            margin-top: 1rem;
        }
        
        .task-item {
            background: white;
            padding: 1rem;
            border-radius: 6px;
            margin-bottom: 1rem;
            border-left: 4px solid #2196F3;
        }
        
        .main-footer {
            text-align: center;
            padding: 2rem;
            color: rgba(255, 255, 255, 0.8);
            background: rgba(0, 0, 0, 0.1);
        }
        
        /* Mobile styles */
        @media (max-width: 768px) {
            .processor-grid {
                grid-template-columns: 1fr;
            }
            
            .hero h1 {
                font-size: 2rem;
            }
            
            .hero-actions {
                flex-direction: column;
                align-items: center;
            }
            
            .nav-menu {
                display: none;
            }
            
            .feature-grid {
                grid-template-columns: 1fr;
            }
        }
        
        /* Dark mode support */
        @media (prefers-color-scheme: dark) {
            body {
                background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            }
            
            .main-header {
                background: rgba(44, 62, 80, 0.95);
            }
            
            .nav-link {
                color: #ecf0f1;
            }
            
            .feature-card, .processor-interface, .system-status {
                background: rgba(52, 73, 94, 0.9);
                color: #ecf0f1;
            }
        }
        """
    
    def _generate_js(self) -> str:
        """Generate main JavaScript"""
        return """
        // Main application JavaScript
        class ChameleonApp {
            constructor() {
                this.init();
            }
            
            init() {
                this.loadSystemStatus();
                this.setupEventListeners();
                
                // Refresh status every 30 seconds
                setInterval(() => this.loadSystemStatus(), 30000);
            }
            
            setupEventListeners() {
                // Mobile menu toggle
                const navToggle = document.querySelector('.nav-toggle');
                const navMenu = document.querySelector('.nav-menu');
                
                if (navToggle) {
                    navToggle.addEventListener('click', () => {
                        navMenu.classList.toggle('active');
                    });
                }
            }
            
            async loadSystemStatus() {
                try {
                    const response = await fetch('/api/status');
                    const data = await response.json();
                    
                    this.updateStatusDisplay(data);
                } catch (error) {
                    console.error('Failed to load system status:', error);
                }
            }
            
            updateStatusDisplay(data) {
                const queueStatus = document.getElementById('queue-status');
                const workerStatus = document.getElementById('worker-status');
                const healthStatus = document.getElementById('health-status');
                
                if (queueStatus) {
                    const totalQueued = data.queue_status?.total_queued || 0;
                    queueStatus.textContent = `${totalQueued} tasks`;
                }
                
                if (workerStatus) {
                    const availableWorkers = data.worker_status?.available_workers || 0;
                    const totalWorkers = data.worker_status?.total_workers || 0;
                    workerStatus.textContent = `${availableWorkers}/${totalWorkers}`;
                }
                
                if (healthStatus) {
                    const health = data.system_health || 'unknown';
                    healthStatus.textContent = health.charAt(0).toUpperCase() + health.slice(1);
                    healthStatus.className = `status-value health-${health}`;
                }
            }
        }
        
        // Initialize app when DOM is loaded
        document.addEventListener('DOMContentLoaded', () => {
            new ChameleonApp();
        });
        
        // Service Worker registration for PWA
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/static/sw.js')
                    .then((registration) => {
                        console.log('SW registered: ', registration);
                    })
                    .catch((registrationError) => {
                        console.log('SW registration failed: ', registrationError);
                    });
            });
        }
        """
    
    def _generate_processor_js(self) -> str:
        """Generate processor page JavaScript"""
        return """
        // Audio processor JavaScript
        class AudioProcessor {
            constructor() {
                this.activeTasks = new Map();
                this.init();
            }
            
            init() {
                this.setupFileUpload();
                this.setupForm();
                this.setupTaskTypeChange();
                this.loadActiveTasks();
                
                // Refresh tasks every 5 seconds
                setInterval(() => this.refreshTaskStatus(), 5000);
            }
            
            setupFileUpload() {
                const uploadArea = document.getElementById('upload-area');
                const fileInput = document.getElementById('file-input');
                
                uploadArea.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    uploadArea.classList.add('dragover');
                });
                
                uploadArea.addEventListener('dragleave', () => {
                    uploadArea.classList.remove('dragover');
                });
                
                uploadArea.addEventListener('drop', (e) => {
                    e.preventDefault();
                    uploadArea.classList.remove('dragover');
                    this.handleFiles(e.dataTransfer.files);
                });
                
                fileInput.addEventListener('change', (e) => {
                    this.handleFiles(e.target.files);
                });
            }
            
            setupForm() {
                const form = document.getElementById('processing-form');
                form.addEventListener('submit', (e) => {
                    e.preventDefault();
                    this.submitProcessingTask();
                });
                
                const qualitySlider = document.getElementById('quality');
                const qualityValue = document.getElementById('quality-value');
                
                if (qualitySlider) {
                    qualitySlider.addEventListener('input', (e) => {
                        qualityValue.textContent = e.target.value;
                    });
                }
            }
            
            setupTaskTypeChange() {
                const taskType = document.getElementById('task-type');
                const formatOptions = document.getElementById('format-options');
                const qualityOptions = document.getElementById('quality-options');
                
                taskType.addEventListener('change', (e) => {
                    const value = e.target.value;
                    
                    formatOptions.style.display = 
                        value === 'format_conversion' ? 'block' : 'none';
                    qualityOptions.style.display = 
                        ['noise_reduction', 'audio_enhancement'].includes(value) ? 'block' : 'none';
                });
            }
            
            handleFiles(files) {
                const fileList = document.getElementById('file-list');
                fileList.innerHTML = '';
                
                Array.from(files).forEach(file => {
                    const fileItem = document.createElement('div');
                    fileItem.className = 'file-item';
                    fileItem.innerHTML = `
                        <span class="file-name">${file.name}</span>
                        <span class="file-size">(${this.formatFileSize(file.size)})</span>
                        <button class="btn-remove" onclick="this.parentElement.remove()">×</button>
                    `;
                    fileList.appendChild(fileItem);
                });
            }
            
            formatFileSize(bytes) {
                if (bytes === 0) return '0 Bytes';
                const k = 1024;
                const sizes = ['Bytes', 'KB', 'MB', 'GB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
            }
            
            async submitProcessingTask() {
                const form = document.getElementById('processing-form');
                const formData = new FormData(form);
                const fileInput = document.getElementById('file-input');
                
                if (fileInput.files.length === 0) {
                    alert('Please select at least one audio file');
                    return;
                }
                
                // Add files to form data
                Array.from(fileInput.files).forEach(file => {
                    formData.append('files', file);
                });
                
                try {
                    const response = await fetch('/api/tasks/submit', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        this.addTaskToList(result);
                        form.reset();
                        document.getElementById('file-list').innerHTML = '';
                        alert('Task submitted successfully!');
                    } else {
                        alert('Error submitting task: ' + result.error);
                    }
                } catch (error) {
                    alert('Error submitting task: ' + error.message);
                }
            }
            
            addTaskToList(task) {
                const taskList = document.getElementById('task-list');
                const noTasks = taskList.querySelector('.no-tasks');
                
                if (noTasks) {
                    noTasks.remove();
                }
                
                const taskItem = document.createElement('div');
                taskItem.className = 'task-item';
                taskItem.id = `task-${task.task_id}`;
                taskItem.innerHTML = `
                    <div class="task-header">
                        <strong>${task.task_type}</strong>
                        <span class="task-status status-${task.status}">${task.status}</span>
                    </div>
                    <div class="task-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${task.progress || 0}%"></div>
                        </div>
                        <span class="progress-text">${task.progress || 0}%</span>
                    </div>
                    <div class="task-meta">
                        <small>ID: ${task.task_id} | Priority: ${task.priority}</small>
                    </div>
                `;
                
                taskList.appendChild(taskItem);
                this.activeTasks.set(task.task_id, task);
            }
            
            async loadActiveTasks() {
                try {
                    const response = await fetch('/api/tasks');
                    const tasks = await response.json();
                    
                    tasks.forEach(task => this.addTaskToList(task));
                } catch (error) {
                    console.error('Failed to load active tasks:', error);
                }
            }
            
            async refreshTaskStatus() {
                for (const [taskId, task] of this.activeTasks) {
                    if (['completed', 'failed', 'cancelled'].includes(task.status)) {
                        continue;
                    }
                    
                    try {
                        const response = await fetch(`/api/tasks/${taskId}`);
                        const updatedTask = await response.json();
                        
                        this.updateTaskDisplay(updatedTask);
                        this.activeTasks.set(taskId, updatedTask);
                    } catch (error) {
                        console.error(`Failed to refresh task ${taskId}:`, error);
                    }
                }
            }
            
            updateTaskDisplay(task) {
                const taskElement = document.getElementById(`task-${task.task_id}`);
                if (!taskElement) return;
                
                const statusElement = taskElement.querySelector('.task-status');
                const progressFill = taskElement.querySelector('.progress-fill');
                const progressText = taskElement.querySelector('.progress-text');
                
                statusElement.textContent = task.status;
                statusElement.className = `task-status status-${task.status}`;
                
                if (progressFill) {
                    progressFill.style.width = `${task.progress || 0}%`;
                }
                
                if (progressText) {
                    progressText.textContent = `${task.progress || 0}%`;
                }
            }
        }
        
        // Initialize processor when DOM is loaded
        document.addEventListener('DOMContentLoaded', () => {
            new AudioProcessor();
        });
        """
    
    def _generate_manifest(self) -> str:
        """Generate PWA manifest"""
        return json.dumps({
            "name": "Chameleon Audio System",
            "short_name": "Chameleon",
            "description": "Professional audio processing system",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#667eea",
            "theme_color": "#2196F3",
            "icons": [
                {
                    "src": "/static/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png"
                },
                {
                    "src": "/static/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png"
                }
            ]
        })
    
    def _is_mobile_request(self, request: WebRequest) -> bool:
        """Check if request is from mobile device"""
        user_agent = request.user_agent.lower()
        mobile_patterns = ['mobile', 'android', 'iphone', 'ipad', 'tablet']
        return any(pattern in user_agent for pattern in mobile_patterns)
    
    def _serve_404(self, request: WebRequest) -> WebResponse:
        """Serve 404 Not Found page"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Page Not Found - Chameleon</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="/static/styles.css">
        </head>
        <body>
            <main class="main-content" style="text-align: center; padding: 4rem;">
                <h1>404 - Page Not Found</h1>
                <p>The requested page could not be found.</p>
                <a href="/" class="btn btn-primary">Go Home</a>
            </main>
        </body>
        </html>
        """
        
        return WebResponse(
            status_code=404,
            headers={"Content-Type": "text/html"},
            content=html
        )
    
    def _serve_error(self, request: WebRequest, error_message: str) -> WebResponse:
        """Serve error page"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error - Chameleon</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="/static/styles.css">
        </head>
        <body>
            <main class="main-content" style="text-align: center; padding: 4rem;">
                <h1>Server Error</h1>
                <p>An error occurred: {error_message}</p>
                <a href="/" class="btn btn-primary">Go Home</a>
            </main>
        </body>
        </html>
        """
        
        return WebResponse(
            status_code=500,
            headers={"Content-Type": "text/html"},
            content=html
        )
    
    # API endpoints
    def _api_system_status(self, request: WebRequest) -> Dict[str, Any]:
        """API endpoint for system status"""
        if self.cloud_processor:
            return self.cloud_processor.get_system_status()
        else:
            return {
                "timestamp": datetime.now().isoformat(),
                "provider": "local",
                "queue_status": {"total_queued": 0},
                "worker_status": {"total_workers": 0, "available_workers": 0},
                "active_tasks": 0,
                "system_health": "unknown"
            }
    
    def _api_tasks(self, request: WebRequest) -> List[Dict[str, Any]]:
        """API endpoint for active tasks"""
        if not self.cloud_processor:
            return []
        
        # Return list of active tasks
        with self.cloud_processor.lock:
            return [
                {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "status": task.status.value,
                    "priority": task.priority.value,
                    "progress": task.progress,
                    "created_at": task.created_at.isoformat(),
                    "worker_id": task.worker_id
                }
                for task in self.cloud_processor.active_tasks.values()
            ]
    
    def _api_submit_task(self, request: WebRequest) -> Dict[str, Any]:
        """API endpoint for submitting tasks"""
        if not self.cloud_processor:
            return {"error": "Cloud processor not available"}
        
        if request.method != "POST":
            return {"error": "Method not allowed"}
        
        # Parse form data (simplified)
        # In a real implementation, would properly parse multipart form data
        try:
            # Simulate task submission
            task_id = self.cloud_processor.submit_task(
                task_type="audio_analysis",  # Would parse from form
                input_data={"uploaded_files": []},  # Would handle file uploads
                priority=ProcessingPriority.NORMAL,
                metadata={"source": "web_interface"}
            )
            
            return {
                "task_id": task_id,
                "status": "queued",
                "message": "Task submitted successfully"
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _api_task_status(self, request: WebRequest) -> Dict[str, Any]:
        """API endpoint for task status"""
        if not self.cloud_processor:
            return {"error": "Cloud processor not available"}
        
        # Extract task_id from path
        task_id = request.path.split("/")[-1]
        
        status = self.cloud_processor.get_task_status(task_id)
        if status:
            return status
        else:
            return {"error": "Task not found"}

class WebServer:
    """HTTP server for web interface"""
    
    def __init__(self, interface_manager: WebInterfaceManager, port: int = 8000):
        self.interface_manager = interface_manager
        self.port = port
        self.server = None
        self.server_thread = None
        self.logger = logging.getLogger("WebServer")
    
    def start(self):
        """Start the web server"""
        try:
            handler = self._create_handler()
            self.server = socketserver.TCPServer(("", self.port), handler)
            
            def serve():
                self.logger.info(f"Web server starting on port {self.port}")
                self.server.serve_forever()
            
            self.server_thread = threading.Thread(target=serve, daemon=True)
            self.server_thread.start()
            
            self.logger.info(f"Web interface available at http://localhost:{self.port}")
            
        except Exception as e:
            self.logger.error(f"Failed to start web server: {e}")
    
    def stop(self):
        """Stop the web server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.logger.info("Web server stopped")
    
    def _create_handler(self):
        """Create HTTP request handler"""
        interface_manager = self.interface_manager
        
        class WebRequestHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                self._handle_request("GET")
            
            def do_POST(self):
                self._handle_request("POST")
            
            def _handle_request(self, method):
                # Parse request
                query_params = {}
                if "?" in self.path:
                    path, query_string = self.path.split("?", 1)
                    query_params = dict(urllib.parse.parse_qsl(query_string))
                else:
                    path = self.path
                
                body = None
                if method == "POST":
                    content_length = int(self.headers.get('Content-Length', 0))
                    if content_length > 0:
                        body = self.rfile.read(content_length).decode('utf-8')
                
                request = WebRequest(
                    method=method,
                    path=path,
                    headers=dict(self.headers),
                    query_params=query_params,
                    body=body,
                    user_agent=self.headers.get('User-Agent', ''),
                    remote_addr=self.client_address[0]
                )
                
                # Handle request
                response = interface_manager.handle_request(request)
                
                # Send response
                self.send_response(response.status_code)
                for key, value in response.headers.items():
                    self.send_header(key, value)
                self.end_headers()
                
                if response.is_binary:
                    self.wfile.write(response.content)
                else:
                    self.wfile.write(response.content.encode('utf-8'))
            
            def log_message(self, format, *args):
                # Suppress HTTP server logs
                pass
        
        return WebRequestHandler

class MobileWebInterface:
    """Main mobile and web interface system"""
    
    def __init__(self, cloud_processor: Optional[CloudProcessor] = None,
                 dashboard: Optional[VisualizationDashboard] = None,
                 system_monitor: Optional[SystemMonitor] = None,
                 plugin_ft: Optional[PluginFaultToleranceManager] = None,
                 port: int = 8000):
        
        # Initialize components
        self.interface_manager = WebInterfaceManager(
            cloud_processor=cloud_processor,
            dashboard=dashboard,
            system_monitor=system_monitor,
            plugin_ft=plugin_ft
        )
        
        self.server = WebServer(self.interface_manager, port)
        self.logger = logging.getLogger("MobileWebInterface")
    
    def start(self):
        """Start the web interface"""
        self.server.start()
        self.logger.info("Mobile and web interface started")
    
    def stop(self):
        """Stop the web interface"""
        self.server.stop()
        self.logger.info("Mobile and web interface stopped")
    
    def get_interface_url(self) -> str:
        """Get interface URL"""
        return f"http://localhost:{self.server.port}"

# Global web interface instance
_global_web_interface = None

def get_global_web_interface() -> MobileWebInterface:
    """Get or create global web interface"""
    global _global_web_interface
    if _global_web_interface is None:
        _global_web_interface = MobileWebInterface()
    return _global_web_interface

if __name__ == "__main__":
    # Example usage
    from cloud_processor import get_global_cloud_processor
    from visualization_dashboard import get_global_visualization_dashboard
    
    # Create web interface with all components
    web_interface = MobileWebInterface(
        cloud_processor=get_global_cloud_processor(),
        dashboard=get_global_visualization_dashboard(),
        port=8000
    )
    
    # Start web interface
    web_interface.start()
    
    print(f"Web interface available at: {web_interface.get_interface_url()}")
    print("Features:")
    print("- Responsive design for desktop and mobile")
    print("- Progressive Web App (PWA) support")
    print("- Real-time task monitoring")
    print("- File upload and processing")
    print("- System dashboard integration")
    print("- RESTful API endpoints")
    print("\nPress Ctrl+C to stop...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        web_interface.stop()
        print("Web interface stopped")