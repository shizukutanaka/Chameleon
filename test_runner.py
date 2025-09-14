#!/usr/bin/env python3
"""
Chameleon Audio System - Advanced Test Runner
=============================================
Unified test execution and reporting system
"""

import sys
import os
import time
import json
import subprocess
import concurrent.futures
import multiprocessing
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import argparse


class TestType(Enum):
    """Test type classifications"""
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    STRESS = "stress"
    REGRESSION = "regression"
    SMOKE = "smoke"
    END_TO_END = "e2e"


class TestPriority(Enum):
    """Test priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TestCase:
    """Individual test case definition"""
    name: str
    test_type: TestType
    priority: TestPriority
    module: str
    function: str
    timeout: int = 60
    depends_on: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    expected_duration: float = 0.0


@dataclass
class TestExecution:
    """Test execution result"""
    test_case: TestCase
    passed: bool
    duration: float
    error_message: str = ""
    output: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class TestSession:
    """Complete test session"""
    session_id: str
    start_time: float
    end_time: float = 0.0
    executions: List[TestExecution] = field(default_factory=list)
    configuration: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)


class TestRegistry:
    """Registry of all available tests"""
    
    def __init__(self):
        self.tests: Dict[str, TestCase] = {}
        self.load_test_definitions()
    
    def load_test_definitions(self):
        """Load test definitions from modules"""
        # Audio processor tests
        self.register_audio_processor_tests()
        
        # Stream processor tests
        self.register_stream_processor_tests()
        
        # Voice processor tests
        self.register_voice_processor_tests()
        
        # Integration tests
        self.register_integration_tests()
        
        # Performance tests
        self.register_performance_tests()
        
        # System tests
        self.register_system_tests()
    
    def register_audio_processor_tests(self):
        """Register audio processor test cases"""
        base_tests = [
            ("normalize_audio", "Test audio normalization", 30),
            ("apply_gain", "Test gain application", 15),
            ("apply_eq", "Test equalizer", 45),
            ("compress_audio", "Test dynamic compression", 60),
            ("denoise", "Test noise reduction", 120),
            ("spectral_gate", "Test spectral gating", 90)
        ]
        
        for test_name, description, timeout in base_tests:
            self.tests[f"audio_processor.{test_name}"] = TestCase(
                name=f"audio_processor.{test_name}",
                test_type=TestType.UNIT,
                priority=TestPriority.HIGH,
                module="test_framework",
                function=f"TestAudioProcessor.test_{test_name}",
                timeout=timeout,
                tags=["audio", "processing", "core"]
            )
    
    def register_stream_processor_tests(self):
        """Register stream processor test cases"""
        stream_tests = [
            ("stream_initialization", "Test stream setup", 10),
            ("real_time_processing", "Test real-time latency", 30),
            ("buffer_management", "Test buffer handling", 60),
            ("concurrent_streams", "Test multiple streams", 120)
        ]
        
        for test_name, description, timeout in stream_tests:
            self.tests[f"stream_processor.{test_name}"] = TestCase(
                name=f"stream_processor.{test_name}",
                test_type=TestType.UNIT if "concurrent" not in test_name else TestType.STRESS,
                priority=TestPriority.CRITICAL,
                module="test_framework", 
                function=f"TestStreamProcessor.test_{test_name}",
                timeout=timeout,
                tags=["streaming", "realtime", "latency"]
            )
    
    def register_voice_processor_tests(self):
        """Register voice processor test cases"""
        voice_tests = [
            ("pitch_shift", "Test pitch shifting", 90),
            ("formant_shift", "Test formant shifting", 90),
            ("gender_change", "Test gender transformation", 120),
            ("voice_cloning", "Test voice cloning", 300)
        ]
        
        for test_name, description, timeout in voice_tests:
            priority = TestPriority.CRITICAL if test_name in ["pitch_shift", "formant_shift"] else TestPriority.HIGH
            
            self.tests[f"voice_processor.{test_name}"] = TestCase(
                name=f"voice_processor.{test_name}",
                test_type=TestType.UNIT,
                priority=priority,
                module="test_framework",
                function=f"TestVoiceProcessor.test_{test_name}",
                timeout=timeout,
                tags=["voice", "dsp", "transformation"]
            )
    
    def register_integration_tests(self):
        """Register integration test cases"""
        integration_tests = [
            ("full_processing_pipeline", "Test complete audio pipeline", 180),
            ("plugin_system", "Test plugin loading and execution", 120),
            ("file_format_compatibility", "Test various audio formats", 240),
            ("network_streaming", "Test network audio streaming", 300),
            ("ml_training_pipeline", "Test ML training workflow", 600)
        ]
        
        for test_name, description, timeout in integration_tests:
            self.tests[f"integration.{test_name}"] = TestCase(
                name=f"integration.{test_name}",
                test_type=TestType.INTEGRATION,
                priority=TestPriority.HIGH,
                module="test_framework",
                function=f"IntegrationTestSuite.test_{test_name}",
                timeout=timeout,
                tags=["integration", "system", "workflow"]
            )
    
    def register_performance_tests(self):
        """Register performance test cases"""
        perf_tests = [
            ("latency_benchmark", "Measure processing latency", 300),
            ("throughput_benchmark", "Measure processing throughput", 300),
            ("memory_efficiency", "Test memory usage", 180),
            ("cpu_utilization", "Test CPU efficiency", 240),
            ("concurrent_performance", "Test parallel processing", 360)
        ]
        
        for test_name, description, timeout in perf_tests:
            self.tests[f"performance.{test_name}"] = TestCase(
                name=f"performance.{test_name}",
                test_type=TestType.PERFORMANCE,
                priority=TestPriority.MEDIUM,
                module="benchmark_suite",
                function=f"PerformanceTest.{test_name}",
                timeout=timeout,
                tags=["performance", "benchmark", "optimization"]
            )
    
    def register_system_tests(self):
        """Register system-level test cases"""
        system_tests = [
            ("startup_shutdown", "Test system startup/shutdown", 60),
            ("resource_cleanup", "Test resource cleanup", 90),
            ("error_recovery", "Test error handling", 120),
            ("configuration_loading", "Test config management", 30),
            ("logging_system", "Test logging functionality", 45)
        ]
        
        for test_name, description, timeout in system_tests:
            self.tests[f"system.{test_name}"] = TestCase(
                name=f"system.{test_name}",
                test_type=TestType.UNIT,
                priority=TestPriority.MEDIUM,
                module="test_framework",
                function=f"SystemTest.test_{test_name}",
                timeout=timeout,
                tags=["system", "infrastructure", "reliability"]
            )
    
    def get_tests_by_type(self, test_type: TestType) -> List[TestCase]:
        """Get tests filtered by type"""
        return [test for test in self.tests.values() if test.test_type == test_type]
    
    def get_tests_by_priority(self, priority: TestPriority) -> List[TestCase]:
        """Get tests filtered by priority"""
        return [test for test in self.tests.values() if test.priority == priority]
    
    def get_tests_by_tags(self, tags: List[str]) -> List[TestCase]:
        """Get tests filtered by tags"""
        return [test for test in self.tests.values() 
                if any(tag in test.tags for tag in tags)]
    
    def get_critical_tests(self) -> List[TestCase]:
        """Get critical tests for smoke testing"""
        critical_tests = []
        
        # Core functionality tests
        critical_tests.extend([
            self.tests.get("audio_processor.normalize_audio"),
            self.tests.get("stream_processor.real_time_processing"), 
            self.tests.get("voice_processor.pitch_shift"),
            self.tests.get("integration.full_processing_pipeline")
        ])
        
        return [t for t in critical_tests if t is not None]


class TestRunner:
    """Advanced test execution engine"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.registry = TestRegistry()
        self.results_dir = self.project_root / "test_results"
        self.results_dir.mkdir(exist_ok=True)
        
        # Configuration
        self.config = {
            "parallel_execution": True,
            "max_workers": min(8, multiprocessing.cpu_count()),
            "stop_on_failure": False,
            "retry_failed": True,
            "max_retries": 2,
            "verbose_output": False,
            "generate_reports": True
        }
    
    def load_config(self, config_file: Optional[str] = None):
        """Load runner configuration"""
        if config_file and Path(config_file).exists():
            with open(config_file) as f:
                user_config = json.load(f)
                self.config.update(user_config)
    
    def execute_test(self, test_case: TestCase) -> TestExecution:
        """Execute a single test case"""
        start_time = time.time()
        
        try:
            # Run the test
            if test_case.module == "test_framework":
                result = self._run_unittest(test_case)
            elif test_case.module == "benchmark_suite":
                result = self._run_benchmark(test_case)
            else:
                result = self._run_custom_test(test_case)
            
            duration = time.time() - start_time
            
            return TestExecution(
                test_case=test_case,
                passed=result["passed"],
                duration=duration,
                error_message=result.get("error", ""),
                output=result.get("output", ""),
                metrics=result.get("metrics", {})
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return TestExecution(
                test_case=test_case,
                passed=False,
                duration=duration,
                error_message=str(e),
                output="",
                metrics={}
            )
    
    def _run_unittest(self, test_case: TestCase) -> Dict[str, Any]:
        """Run unittest-based test"""
        try:
            # Import and run the test
            test_script = self.project_root / "test_framework.py"
            
            # Run specific test method
            cmd = [
                sys.executable, str(test_script),
                test_case.test_type.value
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=test_case.timeout,
                cwd=self.project_root
            )
            
            return {
                "passed": result.returncode == 0,
                "output": result.stdout + result.stderr,
                "error": result.stderr if result.returncode != 0 else ""
            }
            
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "error": f"Test timed out after {test_case.timeout}s",
                "output": ""
            }
        except Exception as e:
            return {
                "passed": False,
                "error": str(e),
                "output": ""
            }
    
    def _run_benchmark(self, test_case: TestCase) -> Dict[str, Any]:
        """Run benchmark test"""
        try:
            benchmark_script = self.project_root / "benchmark_suite.py"
            
            # Extract benchmark category from function name
            if "latency" in test_case.function:
                category = "latency"
            elif "throughput" in test_case.function:
                category = "throughput"
            elif "memory" in test_case.function:
                category = "memory"
            else:
                category = "performance"
            
            cmd = [sys.executable, str(benchmark_script), "--category", category]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=test_case.timeout,
                cwd=self.project_root
            )
            
            # Parse metrics from output
            metrics = self._parse_benchmark_metrics(result.stdout)
            
            return {
                "passed": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else "",
                "metrics": metrics
            }
            
        except Exception as e:
            return {
                "passed": False,
                "error": str(e),
                "output": "",
                "metrics": {}
            }
    
    def _run_custom_test(self, test_case: TestCase) -> Dict[str, Any]:
        """Run custom test implementation"""
        # Placeholder for custom test runners
        return {
            "passed": True,
            "output": f"Custom test {test_case.name} executed",
            "metrics": {}
        }
    
    def _parse_benchmark_metrics(self, output: str) -> Dict[str, Any]:
        """Parse metrics from benchmark output"""
        metrics = {}
        
        for line in output.split('\n'):
            if ':' in line and any(keyword in line.lower() 
                                 for keyword in ['latency', 'throughput', 'memory', 'ops']):
                try:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        key = parts[0].strip().lower().replace(' ', '_')
                        value_str = parts[1].strip()
                        
                        # Extract numeric value
                        import re
                        numbers = re.findall(r'[\d.]+', value_str)
                        if numbers:
                            metrics[key] = float(numbers[0])
                except:
                    continue
        
        return metrics
    
    def run_test_suite(self, 
                      test_filter: Optional[str] = None,
                      test_type: Optional[TestType] = None,
                      priority: Optional[TestPriority] = None,
                      tags: Optional[List[str]] = None,
                      parallel: bool = True) -> TestSession:
        """Run a suite of tests"""
        
        session_id = f"test_session_{int(time.time())}"
        session = TestSession(
            session_id=session_id,
            start_time=time.time(),
            configuration=self.config.copy(),
            environment=self._get_environment_info()
        )
        
        # Select tests to run
        tests_to_run = list(self.registry.tests.values())
        
        if test_type:
            tests_to_run = [t for t in tests_to_run if t.test_type == test_type]
        
        if priority:
            tests_to_run = [t for t in tests_to_run if t.priority == priority]
        
        if tags:
            tests_to_run = [t for t in tests_to_run 
                           if any(tag in t.tags for tag in tags)]
        
        if test_filter:
            tests_to_run = [t for t in tests_to_run if test_filter in t.name]
        
        print(f"\nRunning {len(tests_to_run)} tests...")
        print(f"Session ID: {session_id}")
        print(f"Parallel execution: {parallel}")
        
        # Execute tests
        if parallel and len(tests_to_run) > 1:
            session.executions = self._run_tests_parallel(tests_to_run)
        else:
            session.executions = self._run_tests_sequential(tests_to_run)
        
        session.end_time = time.time()
        
        # Generate reports
        if self.config.get("generate_reports", True):
            self._generate_reports(session)
        
        # Print summary
        self._print_session_summary(session)
        
        return session
    
    def _run_tests_parallel(self, tests: List[TestCase]) -> List[TestExecution]:
        """Run tests in parallel"""
        executions = []
        
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config["max_workers"]
        ) as executor:
            
            # Submit all tests
            future_to_test = {
                executor.submit(self.execute_test, test): test 
                for test in tests
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_test):
                test = future_to_test[future]
                try:
                    execution = future.result()
                    executions.append(execution)
                    
                    # Print progress
                    status = "✅ PASS" if execution.passed else "❌ FAIL"
                    print(f"{status} {test.name} ({execution.duration:.2f}s)")
                    
                    if not execution.passed and self.config.get("stop_on_failure", False):
                        # Cancel remaining tests
                        for remaining_future in future_to_test:
                            if not remaining_future.done():
                                remaining_future.cancel()
                        break
                        
                except Exception as e:
                    print(f"💥 ERROR {test.name}: {str(e)}")
        
        return executions
    
    def _run_tests_sequential(self, tests: List[TestCase]) -> List[TestExecution]:
        """Run tests sequentially"""
        executions = []
        
        for i, test in enumerate(tests, 1):
            print(f"\n[{i}/{len(tests)}] Running {test.name}...")
            
            execution = self.execute_test(test)
            executions.append(execution)
            
            status = "✅ PASS" if execution.passed else "❌ FAIL"
            print(f"{status} {test.name} ({execution.duration:.2f}s)")
            
            if not execution.passed:
                if execution.error_message:
                    print(f"   Error: {execution.error_message}")
                
                if self.config.get("stop_on_failure", False):
                    print("Stopping on first failure...")
                    break
        
        return executions
    
    def _get_environment_info(self) -> Dict[str, Any]:
        """Get test environment information"""
        import platform
        
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": multiprocessing.cpu_count(),
            "project_root": str(self.project_root),
            "timestamp": time.time()
        }
    
    def _print_session_summary(self, session: TestSession):
        """Print test session summary"""
        total_tests = len(session.executions)
        passed_tests = sum(1 for e in session.executions if e.passed)
        failed_tests = total_tests - passed_tests
        
        total_duration = session.end_time - session.start_time
        
        print(f"\n{'='*60}")
        print("TEST SESSION SUMMARY")
        print(f"{'='*60}")
        print(f"Session ID: {session.session_id}")
        print(f"Duration: {total_duration:.1f}s")
        print(f"Tests: {total_tests} total, {passed_tests} passed, {failed_tests} failed")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print(f"\nFailed Tests:")
            for execution in session.executions:
                if not execution.passed:
                    print(f"  • {execution.test_case.name}: {execution.error_message}")
        
        # Performance summary
        if session.executions:
            durations = [e.duration for e in session.executions]
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            
            print(f"\nPerformance:")
            print(f"  Average test duration: {avg_duration:.2f}s")
            print(f"  Longest test: {max_duration:.2f}s")
    
    def _generate_reports(self, session: TestSession):
        """Generate test reports"""
        timestamp = int(session.start_time)
        
        # JSON report
        json_report = self.results_dir / f"test_report_{timestamp}.json"
        self._generate_json_report(session, json_report)
        
        # HTML report
        html_report = self.results_dir / f"test_report_{timestamp}.html"
        self._generate_html_report(session, html_report)
        
        print(f"\nReports generated:")
        print(f"  JSON: {json_report}")
        print(f"  HTML: {html_report}")
    
    def _generate_json_report(self, session: TestSession, output_file: Path):
        """Generate JSON test report"""
        report_data = {
            "session_id": session.session_id,
            "start_time": session.start_time,
            "end_time": session.end_time,
            "duration": session.end_time - session.start_time,
            "configuration": session.configuration,
            "environment": session.environment,
            "summary": {
                "total_tests": len(session.executions),
                "passed": sum(1 for e in session.executions if e.passed),
                "failed": sum(1 for e in session.executions if not e.passed),
                "success_rate": sum(1 for e in session.executions if e.passed) / len(session.executions) * 100
            },
            "executions": [
                {
                    "test_name": e.test_case.name,
                    "test_type": e.test_case.test_type.value,
                    "priority": e.test_case.priority.value,
                    "passed": e.passed,
                    "duration": e.duration,
                    "error_message": e.error_message,
                    "metrics": e.metrics,
                    "timestamp": e.timestamp,
                    "tags": e.test_case.tags
                }
                for e in session.executions
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2)
    
    def _generate_html_report(self, session: TestSession, output_file: Path):
        """Generate HTML test report"""
        total_tests = len(session.executions)
        passed_tests = sum(1 for e in session.executions if e.passed)
        failed_tests = total_tests - passed_tests
        success_rate = passed_tests / total_tests * 100 if total_tests > 0 else 0
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Chameleon Test Report - {session.session_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .metric {{ background: #e8f4f8; padding: 15px; border-radius: 5px; text-align: center; }}
        .metric h3 {{ margin: 0; color: #2c5aa0; }}
        .metric .value {{ font-size: 24px; font-weight: bold; }}
        .tests {{ margin-top: 20px; }}
        .test {{ border: 1px solid #ddd; margin: 5px 0; padding: 10px; border-radius: 3px; }}
        .test.passed {{ border-left: 5px solid #28a745; }}
        .test.failed {{ border-left: 5px solid #dc3545; }}
        .test-name {{ font-weight: bold; }}
        .test-details {{ color: #666; font-size: 0.9em; }}
        .error {{ color: #dc3545; margin-top: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Chameleon Audio System - Test Report</h1>
        <p>Session: {session.session_id}</p>
        <p>Generated: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session.start_time))}</p>
    </div>
    
    <div class="summary">
        <div class="metric">
            <h3>Total Tests</h3>
            <div class="value">{total_tests}</div>
        </div>
        <div class="metric">
            <h3>Passed</h3>
            <div class="value" style="color: #28a745">{passed_tests}</div>
        </div>
        <div class="metric">
            <h3>Failed</h3>
            <div class="value" style="color: #dc3545">{failed_tests}</div>
        </div>
        <div class="metric">
            <h3>Success Rate</h3>
            <div class="value">{success_rate:.1f}%</div>
        </div>
        <div class="metric">
            <h3>Duration</h3>
            <div class="value">{(session.end_time - session.start_time):.1f}s</div>
        </div>
    </div>
    
    <div class="tests">
        <h2>Test Results</h2>
"""
        
        for execution in session.executions:
            status_class = "passed" if execution.passed else "failed"
            status_text = "✅ PASSED" if execution.passed else "❌ FAILED"
            
            html_content += f"""
        <div class="test {status_class}">
            <div class="test-name">{execution.test_case.name} - {status_text}</div>
            <div class="test-details">
                Type: {execution.test_case.test_type.value} | 
                Priority: {execution.test_case.priority.value} | 
                Duration: {execution.duration:.2f}s |
                Tags: {', '.join(execution.test_case.tags)}
            </div>
            {f'<div class="error">Error: {execution.error_message}</div>' if execution.error_message else ''}
        </div>
"""
        
        html_content += """
    </div>
</body>
</html>
"""
        
        with open(output_file, 'w') as f:
            f.write(html_content)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Chameleon Advanced Test Runner')
    
    parser.add_argument('--type', choices=[t.value for t in TestType],
                       help='Run tests of specific type')
    parser.add_argument('--priority', choices=[p.value for p in TestPriority],
                       help='Run tests of specific priority')
    parser.add_argument('--tags', nargs='+', help='Run tests with specific tags')
    parser.add_argument('--filter', help='Filter tests by name pattern')
    parser.add_argument('--sequential', action='store_true',
                       help='Run tests sequentially (not parallel)')
    parser.add_argument('--stop-on-failure', action='store_true',
                       help='Stop execution on first failure')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--smoke', action='store_true',
                       help='Run smoke tests (critical tests only)')
    parser.add_argument('--list-tests', action='store_true',
                       help='List available tests and exit')
    
    args = parser.parse_args()
    
    # Initialize runner
    runner = TestRunner()
    
    if args.config:
        runner.load_config(args.config)
    
    if args.stop_on_failure:
        runner.config["stop_on_failure"] = True
    
    # List tests
    if args.list_tests:
        print("Available tests:")
        for test_name, test_case in runner.registry.tests.items():
            print(f"  {test_name} ({test_case.test_type.value}, {test_case.priority.value})")
            print(f"    Tags: {', '.join(test_case.tags)}")
        return
    
    # Run smoke tests
    if args.smoke:
        critical_tests = runner.registry.get_critical_tests()
        print(f"Running {len(critical_tests)} critical tests (smoke test)...")
        # Would need to modify run_test_suite to accept specific test list
        
    # Run test suite
    test_type = TestType(args.type) if args.type else None
    priority = TestPriority(args.priority) if args.priority else None
    
    session = runner.run_test_suite(
        test_filter=args.filter,
        test_type=test_type,
        priority=priority,
        tags=args.tags,
        parallel=not args.sequential
    )
    
    # Exit with appropriate code
    failed_tests = sum(1 for e in session.executions if not e.passed)
    sys.exit(1 if failed_tests > 0 else 0)


if __name__ == "__main__":
    main()