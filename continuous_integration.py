#!/usr/bin/env python3
"""
Chameleon Audio System - Continuous Integration Framework
=========================================================
Automated testing and validation pipeline for development workflow
"""

import os
import sys
import json
import time
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib


class TestStage(Enum):
    """CI pipeline test stages"""
    SYNTAX_CHECK = "syntax"
    UNIT_TESTS = "unit"
    INTEGRATION_TESTS = "integration"
    PERFORMANCE_TESTS = "performance"
    QUALITY_CHECKS = "quality"
    SECURITY_SCAN = "security"
    DOCUMENTATION = "docs"
    BUILD_VERIFICATION = "build"


class TestResult(Enum):
    """Test execution results"""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class StageResult:
    """Result of a CI stage"""
    stage: TestStage
    result: TestResult
    duration: float
    details: str = ""
    artifacts: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Complete CI pipeline result"""
    timestamp: float
    commit_hash: Optional[str]
    branch: str
    stages: List[StageResult]
    overall_result: TestResult
    total_duration: float
    artifacts_path: str


class CIRunner:
    """Continuous Integration pipeline runner"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.artifacts_dir = self.project_root / "ci_artifacts"
        self.config = self.load_config()
        
        # Ensure artifacts directory exists
        self.artifacts_dir.mkdir(exist_ok=True)
    
    def load_config(self) -> Dict[str, Any]:
        """Load CI configuration"""
        config_file = self.project_root / "ci_config.json"
        
        default_config = {
            "stages": [
                "syntax_check",
                "unit_tests", 
                "integration_tests",
                "performance_tests",
                "quality_checks",
                "documentation"
            ],
            "timeout": 1800,  # 30 minutes
            "parallel_stages": ["unit_tests", "quality_checks"],
            "performance_thresholds": {
                "latency_ms": 10.0,
                "throughput_x": 20.0,
                "memory_mb": 500.0
            },
            "quality_thresholds": {
                "test_coverage": 80.0,
                "code_quality": 7.0
            }
        }
        
        if config_file.exists():
            try:
                with open(config_file) as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                print(f"Warning: Failed to load CI config: {e}")
        
        return default_config
    
    def get_git_info(self) -> Tuple[Optional[str], str]:
        """Get current git commit and branch"""
        try:
            # Get commit hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            commit_hash = result.stdout.strip() if result.returncode == 0 else None
            
            # Get branch name
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            branch = result.stdout.strip() if result.returncode == 0 else "unknown"
            
            return commit_hash, branch
            
        except Exception:
            return None, "unknown"
    
    def run_stage_syntax_check(self) -> StageResult:
        """Run syntax checking stage"""
        start_time = time.time()
        
        try:
            print("Running syntax checks...")
            
            # Find all Python files
            python_files = list(self.project_root.glob("*.py"))
            
            syntax_errors = []
            
            for file_path in python_files:
                try:
                    with open(file_path) as f:
                        compile(f.read(), str(file_path), 'exec')
                except SyntaxError as e:
                    syntax_errors.append(f"{file_path}:{e.lineno}: {e.msg}")
                except Exception as e:
                    syntax_errors.append(f"{file_path}: {str(e)}")
            
            duration = time.time() - start_time
            
            if syntax_errors:
                details = "Syntax errors found:\n" + "\n".join(syntax_errors)
                result = TestResult.FAILED
            else:
                details = f"All {len(python_files)} Python files passed syntax check"
                result = TestResult.PASSED
            
            return StageResult(
                stage=TestStage.SYNTAX_CHECK,
                result=result,
                duration=duration,
                details=details,
                metrics={"files_checked": len(python_files), "errors": len(syntax_errors)}
            )
            
        except Exception as e:
            return StageResult(
                stage=TestStage.SYNTAX_CHECK,
                result=TestResult.ERROR,
                duration=time.time() - start_time,
                details=f"Syntax check failed: {str(e)}"
            )
    
    def run_stage_unit_tests(self) -> StageResult:
        """Run unit tests stage"""
        start_time = time.time()
        
        try:
            print("Running unit tests...")
            
            # Run test framework
            test_script = self.project_root / "test_framework.py"
            
            if not test_script.exists():
                return StageResult(
                    stage=TestStage.UNIT_TESTS,
                    result=TestResult.SKIPPED,
                    duration=time.time() - start_time,
                    details="test_framework.py not found"
                )
            
            # Execute tests
            result = subprocess.run(
                [sys.executable, str(test_script), "unit"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=self.config.get("timeout", 1800)
            )
            
            duration = time.time() - start_time
            
            # Parse test output
            output = result.stdout + result.stderr
            
            # Look for test results patterns
            tests_run = 0
            failures = 0
            errors = 0
            
            for line in output.split('\n'):
                if "Tests Run:" in line:
                    try:
                        tests_run = int(line.split(":")[1].strip())
                    except:
                        pass
                elif "Failures:" in line:
                    try:
                        failures = int(line.split(":")[1].strip())
                    except:
                        pass
                elif "Errors:" in line:
                    try:
                        errors = int(line.split(":")[1].strip())
                    except:
                        pass
            
            # Determine result
            if result.returncode == 0 and failures == 0 and errors == 0:
                test_result = TestResult.PASSED
                details = f"All {tests_run} unit tests passed"
            else:
                test_result = TestResult.FAILED
                details = f"Unit tests failed: {failures} failures, {errors} errors"
            
            # Save test output
            output_file = self.artifacts_dir / "unit_test_output.txt"
            with open(output_file, 'w') as f:
                f.write(output)
            
            return StageResult(
                stage=TestStage.UNIT_TESTS,
                result=test_result,
                duration=duration,
                details=details,
                artifacts=[str(output_file)],
                metrics={
                    "tests_run": tests_run,
                    "failures": failures,
                    "errors": errors,
                    "success_rate": (tests_run - failures - errors) / max(tests_run, 1) * 100
                }
            )
            
        except subprocess.TimeoutExpired:
            return StageResult(
                stage=TestStage.UNIT_TESTS,
                result=TestResult.ERROR,
                duration=self.config.get("timeout", 1800),
                details="Unit tests timed out"
            )
        except Exception as e:
            return StageResult(
                stage=TestStage.UNIT_TESTS,
                result=TestResult.ERROR,
                duration=time.time() - start_time,
                details=f"Unit tests failed: {str(e)}"
            )
    
    def run_stage_integration_tests(self) -> StageResult:
        """Run integration tests stage"""
        start_time = time.time()
        
        try:
            print("Running integration tests...")
            
            # Run integration tests from test framework
            test_script = self.project_root / "test_framework.py"
            
            if not test_script.exists():
                return StageResult(
                    stage=TestStage.INTEGRATION_TESTS,
                    result=TestResult.SKIPPED,
                    duration=time.time() - start_time,
                    details="test_framework.py not found"
                )
            
            result = subprocess.run(
                [sys.executable, str(test_script), "integration"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=self.config.get("timeout", 1800)
            )
            
            duration = time.time() - start_time
            output = result.stdout + result.stderr
            
            # Save output
            output_file = self.artifacts_dir / "integration_test_output.txt"
            with open(output_file, 'w') as f:
                f.write(output)
            
            if result.returncode == 0:
                test_result = TestResult.PASSED
                details = "Integration tests passed"
            else:
                test_result = TestResult.FAILED
                details = "Integration tests failed"
            
            return StageResult(
                stage=TestStage.INTEGRATION_TESTS,
                result=test_result,
                duration=duration,
                details=details,
                artifacts=[str(output_file)]
            )
            
        except Exception as e:
            return StageResult(
                stage=TestStage.INTEGRATION_TESTS,
                result=TestResult.ERROR,
                duration=time.time() - start_time,
                details=f"Integration tests failed: {str(e)}"
            )
    
    def run_stage_performance_tests(self) -> StageResult:
        """Run performance benchmark stage"""
        start_time = time.time()
        
        try:
            print("Running performance benchmarks...")
            
            benchmark_script = self.project_root / "benchmark_suite.py"
            
            if not benchmark_script.exists():
                return StageResult(
                    stage=TestStage.PERFORMANCE_TESTS,
                    result=TestResult.SKIPPED,
                    duration=time.time() - start_time,
                    details="benchmark_suite.py not found"
                )
            
            # Run quick benchmark
            result = subprocess.run(
                [sys.executable, str(benchmark_script), "--quick"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=600  # 10 minutes for performance tests
            )
            
            duration = time.time() - start_time
            output = result.stdout + result.stderr
            
            # Save benchmark output
            output_file = self.artifacts_dir / "performance_benchmark.txt"
            with open(output_file, 'w') as f:
                f.write(output)
            
            # Parse performance metrics
            metrics = self.parse_performance_output(output)
            
            # Check against thresholds
            thresholds = self.config.get("performance_thresholds", {})
            failures = []
            
            for metric, threshold in thresholds.items():
                if metric in metrics:
                    if metrics[metric] > threshold:
                        failures.append(f"{metric}: {metrics[metric]} > {threshold}")
            
            if failures:
                test_result = TestResult.FAILED
                details = "Performance thresholds exceeded:\n" + "\n".join(failures)
            else:
                test_result = TestResult.PASSED
                details = "All performance benchmarks passed"
            
            return StageResult(
                stage=TestStage.PERFORMANCE_TESTS,
                result=test_result,
                duration=duration,
                details=details,
                artifacts=[str(output_file)],
                metrics=metrics
            )
            
        except Exception as e:
            return StageResult(
                stage=TestStage.PERFORMANCE_TESTS,
                result=TestResult.ERROR,
                duration=time.time() - start_time,
                details=f"Performance tests failed: {str(e)}"
            )
    
    def parse_performance_output(self, output: str) -> Dict[str, float]:
        """Parse performance metrics from benchmark output"""
        metrics = {}
        
        for line in output.split('\n'):
            # Look for latency metrics
            if "Average Latency:" in line:
                try:
                    value = float(line.split(":")[1].strip().replace("ms", ""))
                    metrics["latency_ms"] = value
                except:
                    pass
            
            # Look for throughput metrics
            elif "Average Throughput:" in line:
                try:
                    value = float(line.split(":")[1].strip().replace("x real-time", ""))
                    metrics["throughput_x"] = value
                except:
                    pass
            
            # Look for memory metrics
            elif "Average Memory Overhead:" in line:
                try:
                    value = float(line.split(":")[1].strip().replace("MB", ""))
                    metrics["memory_mb"] = value
                except:
                    pass
        
        return metrics
    
    def run_stage_quality_checks(self) -> StageResult:
        """Run code quality checks"""
        start_time = time.time()
        
        try:
            print("Running quality checks...")
            
            quality_metrics = {}
            details_list = []
            
            # Check file structure
            python_files = list(self.project_root.glob("*.py"))
            quality_metrics["total_files"] = len(python_files)
            
            # Basic code metrics
            total_lines = 0
            total_functions = 0
            total_classes = 0
            
            for file_path in python_files:
                try:
                    with open(file_path) as f:
                        lines = f.readlines()
                        total_lines += len(lines)
                        
                        for line in lines:
                            stripped = line.strip()
                            if stripped.startswith("def "):
                                total_functions += 1
                            elif stripped.startswith("class "):
                                total_classes += 1
                                
                except Exception:
                    continue
            
            quality_metrics.update({
                "total_lines": total_lines,
                "total_functions": total_functions,
                "total_classes": total_classes,
                "avg_lines_per_file": total_lines / max(len(python_files), 1)
            })
            
            # Check for common issues
            issues = []
            
            # Check for large files (>1000 lines)
            for file_path in python_files:
                try:
                    with open(file_path) as f:
                        line_count = len(f.readlines())
                        if line_count > 1000:
                            issues.append(f"{file_path.name} has {line_count} lines (consider splitting)")
                except:
                    pass
            
            # Check for missing docstrings
            missing_docs = 0
            for file_path in python_files:
                try:
                    with open(file_path) as f:
                        content = f.read()
                        if 'def ' in content and '"""' not in content:
                            missing_docs += 1
                except:
                    pass
            
            if missing_docs > 0:
                issues.append(f"{missing_docs} files missing docstrings")
            
            quality_metrics["issues_found"] = len(issues)
            
            # Calculate quality score
            base_score = 100.0
            if len(issues) > 0:
                base_score -= len(issues) * 5  # -5 points per issue
            
            quality_score = max(0, min(100, base_score))
            quality_metrics["quality_score"] = quality_score
            
            # Determine result
            threshold = self.config.get("quality_thresholds", {}).get("code_quality", 7.0)
            
            if quality_score >= threshold * 10:  # Convert 0-10 scale to 0-100
                test_result = TestResult.PASSED
                details = f"Code quality score: {quality_score:.1f}/100"
            else:
                test_result = TestResult.FAILED
                details = f"Code quality below threshold: {quality_score:.1f}/100"
            
            if issues:
                details += "\n\nIssues found:\n" + "\n".join(issues)
            
            duration = time.time() - start_time
            
            # Save quality report
            report_file = self.artifacts_dir / "quality_report.json"
            with open(report_file, 'w') as f:
                json.dump(quality_metrics, f, indent=2)
            
            return StageResult(
                stage=TestStage.QUALITY_CHECKS,
                result=test_result,
                duration=duration,
                details=details,
                artifacts=[str(report_file)],
                metrics=quality_metrics
            )
            
        except Exception as e:
            return StageResult(
                stage=TestStage.QUALITY_CHECKS,
                result=TestResult.ERROR,
                duration=time.time() - start_time,
                details=f"Quality checks failed: {str(e)}"
            )
    
    def run_stage_documentation(self) -> StageResult:
        """Check documentation completeness"""
        start_time = time.time()
        
        try:
            print("Checking documentation...")
            
            # Check for required documentation files
            required_docs = ["README.md"]
            missing_docs = []
            found_docs = []
            
            for doc in required_docs:
                doc_path = self.project_root / doc
                if doc_path.exists():
                    found_docs.append(doc)
                else:
                    missing_docs.append(doc)
            
            # Check main.py for help text
            main_py = self.project_root / "main.py"
            has_help = False
            
            if main_py.exists():
                with open(main_py) as f:
                    content = f.read()
                    if "help" in content.lower() and "usage" in content.lower():
                        has_help = True
            
            # Calculate documentation score
            doc_score = 0
            if len(found_docs) == len(required_docs):
                doc_score += 50
            else:
                doc_score += (len(found_docs) / len(required_docs)) * 50
            
            if has_help:
                doc_score += 50
            
            details = f"Documentation score: {doc_score:.0f}/100\n"
            details += f"Found: {', '.join(found_docs)}\n"
            
            if missing_docs:
                details += f"Missing: {', '.join(missing_docs)}\n"
            
            if has_help:
                details += "Help text found in main.py"
            else:
                details += "No help text found in main.py"
            
            # Determine result
            if doc_score >= 80:
                test_result = TestResult.PASSED
            elif doc_score >= 50:
                test_result = TestResult.FAILED  # Partial docs
            else:
                test_result = TestResult.FAILED
            
            duration = time.time() - start_time
            
            return StageResult(
                stage=TestStage.DOCUMENTATION,
                result=test_result,
                duration=duration,
                details=details,
                metrics={
                    "doc_score": doc_score,
                    "found_docs": len(found_docs),
                    "missing_docs": len(missing_docs),
                    "has_help": has_help
                }
            )
            
        except Exception as e:
            return StageResult(
                stage=TestStage.DOCUMENTATION,
                result=TestResult.ERROR,
                duration=time.time() - start_time,
                details=f"Documentation check failed: {str(e)}"
            )
    
    def run_pipeline(self, stages: Optional[List[str]] = None) -> PipelineResult:
        """Run complete CI pipeline"""
        start_time = time.time()
        
        # Get git info
        commit_hash, branch = self.get_git_info()
        
        # Determine stages to run
        if stages is None:
            stages = self.config.get("stages", [])
        
        print(f"\n{'='*60}")
        print(f"CHAMELEON CI PIPELINE - {branch}")
        if commit_hash:
            print(f"Commit: {commit_hash[:8]}")
        print(f"{'='*60}")
        
        stage_results = []
        overall_result = TestResult.PASSED
        
        # Run each stage
        for stage_name in stages:
            print(f"\n[STAGE] {stage_name.upper()}")
            
            if stage_name == "syntax_check":
                result = self.run_stage_syntax_check()
            elif stage_name == "unit_tests":
                result = self.run_stage_unit_tests()
            elif stage_name == "integration_tests":
                result = self.run_stage_integration_tests()
            elif stage_name == "performance_tests":
                result = self.run_stage_performance_tests()
            elif stage_name == "quality_checks":
                result = self.run_stage_quality_checks()
            elif stage_name == "documentation":
                result = self.run_stage_documentation()
            else:
                print(f"Unknown stage: {stage_name}")
                continue
            
            stage_results.append(result)
            
            # Print stage result
            status_icon = {
                TestResult.PASSED: "✅",
                TestResult.FAILED: "❌", 
                TestResult.SKIPPED: "⏭️",
                TestResult.ERROR: "💥"
            }
            
            print(f"{status_icon[result.result]} {result.stage.value}: "
                  f"{result.result.value} ({result.duration:.2f}s)")
            
            if result.details:
                print(f"   {result.details}")
            
            # Update overall result
            if result.result in [TestResult.FAILED, TestResult.ERROR]:
                overall_result = TestResult.FAILED
        
        total_duration = time.time() - start_time
        
        # Create pipeline result
        pipeline_result = PipelineResult(
            timestamp=time.time(),
            commit_hash=commit_hash,
            branch=branch,
            stages=stage_results,
            overall_result=overall_result,
            total_duration=total_duration,
            artifacts_path=str(self.artifacts_dir)
        )
        
        # Print final summary
        self.print_pipeline_summary(pipeline_result)
        
        # Save pipeline report
        self.save_pipeline_report(pipeline_result)
        
        return pipeline_result
    
    def print_pipeline_summary(self, result: PipelineResult):
        """Print pipeline execution summary"""
        print(f"\n{'='*60}")
        print("PIPELINE SUMMARY")
        print(f"{'='*60}")
        
        # Count results by type
        passed = sum(1 for s in result.stages if s.result == TestResult.PASSED)
        failed = sum(1 for s in result.stages if s.result == TestResult.FAILED)
        skipped = sum(1 for s in result.stages if s.result == TestResult.SKIPPED)
        errors = sum(1 for s in result.stages if s.result == TestResult.ERROR)
        
        print(f"Branch: {result.branch}")
        if result.commit_hash:
            print(f"Commit: {result.commit_hash[:8]}")
        print(f"Duration: {result.total_duration:.1f}s")
        print()
        print(f"Stages:  {len(result.stages)} total")
        print(f"Passed:  {passed}")
        print(f"Failed:  {failed}")
        print(f"Skipped: {skipped}")
        print(f"Errors:  {errors}")
        print()
        
        # Overall result
        if result.overall_result == TestResult.PASSED:
            print("🎉 PIPELINE PASSED - All stages completed successfully!")
        else:
            print("💥 PIPELINE FAILED - Some stages failed or had errors")
            
            # List failed stages
            failed_stages = [s for s in result.stages 
                           if s.result in [TestResult.FAILED, TestResult.ERROR]]
            if failed_stages:
                print("\nFailed stages:")
                for stage in failed_stages:
                    print(f"  • {stage.stage.value}: {stage.result.value}")
        
        print(f"\nArtifacts saved to: {result.artifacts_path}")
    
    def save_pipeline_report(self, result: PipelineResult):
        """Save detailed pipeline report"""
        timestamp = int(result.timestamp)
        report_file = self.artifacts_dir / f"pipeline_report_{timestamp}.json"
        
        # Convert to JSON-serializable format
        report_data = {
            "timestamp": result.timestamp,
            "commit_hash": result.commit_hash,
            "branch": result.branch,
            "overall_result": result.overall_result.value,
            "total_duration": result.total_duration,
            "artifacts_path": result.artifacts_path,
            "stages": [
                {
                    "stage": stage.stage.value,
                    "result": stage.result.value,
                    "duration": stage.duration,
                    "details": stage.details,
                    "artifacts": stage.artifacts,
                    "metrics": stage.metrics
                }
                for stage in result.stages
            ]
        }
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"Pipeline report saved: {report_file}")


def create_github_workflow():
    """Create GitHub Actions workflow file"""
    workflow_content = """name: Chameleon CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
    
    - name: Run CI Pipeline
      run: |
        python continuous_integration.py --stages syntax_check unit_tests quality_checks
    
    - name: Upload artifacts
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: ci-artifacts
        path: ci_artifacts/
"""
    
    # Create .github/workflows directory
    workflow_dir = Path(".github/workflows")
    workflow_dir.mkdir(parents=True, exist_ok=True)
    
    # Write workflow file
    workflow_file = workflow_dir / "ci.yml"
    with open(workflow_file, 'w') as f:
        f.write(workflow_content)
    
    print(f"GitHub Actions workflow created: {workflow_file}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Chameleon CI Pipeline')
    parser.add_argument('--stages', nargs='+', 
                       choices=['syntax_check', 'unit_tests', 'integration_tests',
                               'performance_tests', 'quality_checks', 'documentation'],
                       help='Specific stages to run')
    parser.add_argument('--create-workflow', action='store_true',
                       help='Create GitHub Actions workflow file')
    parser.add_argument('--config', help='Path to CI configuration file')
    
    args = parser.parse_args()
    
    if args.create_workflow:
        create_github_workflow()
        return
    
    # Run CI pipeline
    runner = CIRunner()
    
    if args.config:
        # Load custom config
        with open(args.config) as f:
            runner.config.update(json.load(f))
    
    result = runner.run_pipeline(stages=args.stages)
    
    # Exit with appropriate code
    if result.overall_result == TestResult.PASSED:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()