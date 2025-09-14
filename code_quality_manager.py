#!/usr/bin/env python3
"""
Code Quality Manager - コード品質管理システム
型チェック、リント、コードメトリクス、自動修正を提供
"""

import ast
import re
import sys
import inspect
import importlib
from typing import Dict, Any, Optional, List, Set, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import threading
from pathlib import Path
import subprocess
import json

class CodeSeverity(Enum):
    """コード品質問題の重要度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class CodeIssueType(Enum):
    """コード問題のタイプ"""
    STYLE = "style"
    COMPLEXITY = "complexity"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    DOCUMENTATION = "documentation"
    TYPE_SAFETY = "type_safety"

@dataclass
class CodeIssue:
    """コード品質問題"""
    file_path: str
    line_number: int
    column: int
    issue_type: CodeIssueType
    severity: CodeSeverity
    message: str
    rule_id: str
    suggested_fix: Optional[str] = None
    auto_fixable: bool = False

@dataclass
class CodeMetrics:
    """コードメトリクス"""
    lines_of_code: int = 0
    cyclomatic_complexity: int = 0
    cognitive_complexity: int = 0
    maintainability_index: float = 0.0
    test_coverage: float = 0.0
    documentation_coverage: float = 0.0
    duplicate_code_percentage: float = 0.0
    technical_debt_minutes: int = 0

class TypeChecker:
    """型チェッカー"""
    
    def __init__(self):
        self.logger = logging.getLogger("TypeChecker")
        self.type_errors = []
    
    def check_function_types(self, func: Callable) -> List[CodeIssue]:
        """関数の型チェック"""
        issues = []
        
        try:
            signature = inspect.signature(func)
            source = inspect.getsource(func)
            
            # 型アノテーションの確認
            for param_name, param in signature.parameters.items():
                if param.annotation == inspect.Parameter.empty:
                    issues.append(CodeIssue(
                        file_path=inspect.getfile(func),
                        line_number=func.__code__.co_firstlineno,
                        column=0,
                        issue_type=CodeIssueType.TYPE_SAFETY,
                        severity=CodeSeverity.WARNING,
                        message=f"Parameter '{param_name}' lacks type annotation",
                        rule_id="T001",
                        suggested_fix=f"Add type annotation: {param_name}: SomeType",
                        auto_fixable=False
                    ))
            
            # 戻り値の型アノテーションチェック
            if signature.return_annotation == inspect.Signature.empty:
                issues.append(CodeIssue(
                    file_path=inspect.getfile(func),
                    line_number=func.__code__.co_firstlineno,
                    column=0,
                    issue_type=CodeIssueType.TYPE_SAFETY,
                    severity=CodeSeverity.WARNING,
                    message="Function lacks return type annotation",
                    rule_id="T002",
                    suggested_fix="Add return type annotation: -> ReturnType",
                    auto_fixable=False
                ))
            
        except Exception as e:
            self.logger.error(f"Type checking error: {e}")
        
        return issues

class StyleChecker:
    """コードスタイルチェッカー"""
    
    def __init__(self):
        self.logger = logging.getLogger("StyleChecker")
        
        # スタイルルール
        self.style_rules = {
            'line_length': 120,
            'indent_size': 4,
            'max_function_length': 50,
            'max_class_length': 300,
            'max_parameters': 7,
            'naming_convention': {
                'function': r'^[a-z_][a-z0-9_]*$',
                'class': r'^[A-Z][a-zA-Z0-9]*$',
                'constant': r'^[A-Z_][A-Z0-9_]*$',
                'variable': r'^[a-z_][a-z0-9_]*$'
            }
        }
    
    def check_code_style(self, code: str, file_path: str = "unknown") -> List[CodeIssue]:
        """コードスタイルチェック"""
        issues = []
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # 行長チェック
            if len(line) > self.style_rules['line_length']:
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=line_num,
                    column=self.style_rules['line_length'],
                    issue_type=CodeIssueType.STYLE,
                    severity=CodeSeverity.WARNING,
                    message=f"Line too long ({len(line)}/{self.style_rules['line_length']})",
                    rule_id="S001",
                    suggested_fix="Break line or shorten",
                    auto_fixable=False
                ))
            
            # インデントチェック
            stripped_line = line.lstrip()
            if stripped_line and line != stripped_line:
                indent_level = len(line) - len(stripped_line)
                if indent_level % self.style_rules['indent_size'] != 0:
                    issues.append(CodeIssue(
                        file_path=file_path,
                        line_number=line_num,
                        column=0,
                        issue_type=CodeIssueType.STYLE,
                        severity=CodeSeverity.WARNING,
                        message="Inconsistent indentation",
                        rule_id="S002",
                        suggested_fix=f"Use {self.style_rules['indent_size']} spaces for indentation",
                        auto_fixable=True
                    ))
            
            # トレイリング空白チェック
            if line.endswith(' ') or line.endswith('\t'):
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=line_num,
                    column=len(line.rstrip()),
                    issue_type=CodeIssueType.STYLE,
                    severity=CodeSeverity.INFO,
                    message="Trailing whitespace",
                    rule_id="S003",
                    suggested_fix="Remove trailing whitespace",
                    auto_fixable=True
                ))
        
        return issues

class ComplexityAnalyzer:
    """複雑度解析器"""
    
    def __init__(self):
        self.logger = logging.getLogger("ComplexityAnalyzer")
    
    def calculate_cyclomatic_complexity(self, code: str) -> int:
        """循環的複雑度計算"""
        try:
            tree = ast.parse(code)
            complexity = 1  # ベース複雑度
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor,
                                   ast.ExceptHandler, ast.With, ast.AsyncWith)):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
                elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                    complexity += 1
                    for generator in node.generators:
                        complexity += len(generator.ifs)
            
            return complexity
        except Exception as e:
            self.logger.error(f"Complexity calculation error: {e}")
            return 1
    
    def calculate_cognitive_complexity(self, code: str) -> int:
        """認知的複雑度計算"""
        try:
            tree = ast.parse(code)
            complexity = 0
            nesting_level = 0
            
            def visit_node(node, level=0):
                nonlocal complexity, nesting_level
                
                if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                    complexity += 1 + level
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
                elif isinstance(node, ast.ExceptHandler):
                    complexity += 1 + level
                
                # ネストレベル増加
                if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor, 
                                   ast.With, ast.AsyncWith, ast.FunctionDef, ast.AsyncFunctionDef)):
                    level += 1
                
                for child in ast.iter_child_nodes(node):
                    visit_node(child, level)
            
            visit_node(tree)
            return complexity
        except Exception as e:
            self.logger.error(f"Cognitive complexity calculation error: {e}")
            return 0
    
    def analyze_function_complexity(self, func: Callable) -> Dict[str, Any]:
        """関数の複雑度分析"""
        try:
            source = inspect.getsource(func)
            return {
                'cyclomatic_complexity': self.calculate_cyclomatic_complexity(source),
                'cognitive_complexity': self.calculate_cognitive_complexity(source),
                'lines_of_code': len(source.split('\n')),
                'parameter_count': len(inspect.signature(func).parameters)
            }
        except Exception as e:
            self.logger.error(f"Function complexity analysis error: {e}")
            return {}

class DocumentationChecker:
    """ドキュメントチェッカー"""
    
    def __init__(self):
        self.logger = logging.getLogger("DocumentationChecker")
    
    def check_docstrings(self, code: str, file_path: str = "unknown") -> List[CodeIssue]:
        """docstringチェック"""
        issues = []
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if not ast.get_docstring(node):
                        line_num = node.lineno
                        issues.append(CodeIssue(
                            file_path=file_path,
                            line_number=line_num,
                            column=0,
                            issue_type=CodeIssueType.DOCUMENTATION,
                            severity=CodeSeverity.WARNING,
                            message=f"Missing docstring for {node.__class__.__name__.lower()} '{node.name}'",
                            rule_id="D001",
                            suggested_fix=f'Add docstring: """Description of {node.name}"""',
                            auto_fixable=False
                        ))
                    else:
                        # docstringの品質チェック
                        docstring = ast.get_docstring(node)
                        if len(docstring.split()) < 3:
                            issues.append(CodeIssue(
                                file_path=file_path,
                                line_number=line_num,
                                column=0,
                                issue_type=CodeIssueType.DOCUMENTATION,
                                severity=CodeSeverity.INFO,
                                message=f"Short docstring for {node.__class__.__name__.lower()} '{node.name}'",
                                rule_id="D002",
                                suggested_fix="Provide more detailed description",
                                auto_fixable=False
                            ))
        
        except Exception as e:
            self.logger.error(f"Docstring checking error: {e}")
        
        return issues

class AutoFixer:
    """自動修正機能"""
    
    def __init__(self):
        self.logger = logging.getLogger("AutoFixer")
    
    def fix_trailing_whitespace(self, code: str) -> str:
        """トレイリング空白を修正"""
        lines = code.split('\n')
        fixed_lines = [line.rstrip() for line in lines]
        return '\n'.join(fixed_lines)
    
    def fix_line_endings(self, code: str) -> str:
        """行末を統一"""
        return code.replace('\r\n', '\n').replace('\r', '\n')
    
    def fix_imports(self, code: str) -> str:
        """import文の整理"""
        try:
            tree = ast.parse(code)
            imports = []
            other_nodes = []
            
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports.append(node)
                else:
                    other_nodes.append(node)
            
            # import文をソート（標準ライブラリ、サードパーティ、ローカルの順）
            std_imports = []
            third_party_imports = []
            local_imports = []
            
            for imp in imports:
                if isinstance(imp, ast.Import):
                    module_name = imp.names[0].name
                elif isinstance(imp, ast.ImportFrom):
                    module_name = imp.module or ""
                
                if module_name in {'os', 'sys', 'json', 'time', 'datetime', 'typing', 'pathlib', 're'}:
                    std_imports.append(imp)
                elif '.' not in module_name:
                    third_party_imports.append(imp)
                else:
                    local_imports.append(imp)
            
            # 新しいASTを構築
            new_body = std_imports + third_party_imports + local_imports + other_nodes
            tree.body = new_body
            
            return ast.unparse(tree)
        except Exception as e:
            self.logger.error(f"Import fixing error: {e}")
            return code
    
    def apply_auto_fixes(self, code: str, issues: List[CodeIssue]) -> str:
        """自動修正適用"""
        fixed_code = code
        
        # 修正可能な問題を処理
        for issue in issues:
            if issue.auto_fixable:
                if issue.rule_id == "S003":  # トレイリング空白
                    fixed_code = self.fix_trailing_whitespace(fixed_code)
        
        # その他の一般的な修正
        fixed_code = self.fix_line_endings(fixed_code)
        
        return fixed_code

class CodeQualityManager:
    """統合コード品質管理システム"""
    
    def __init__(self):
        self.logger = logging.getLogger("CodeQualityManager")
        
        # 各種チェッカー初期化
        self.type_checker = TypeChecker()
        self.style_checker = StyleChecker()
        self.complexity_analyzer = ComplexityAnalyzer()
        self.documentation_checker = DocumentationChecker()
        self.auto_fixer = AutoFixer()
        
        # 品質レポート
        self.quality_reports = {}
        self.lock = threading.RLock()
    
    def analyze_code_quality(self, code: str, file_path: str = "unknown") -> Dict[str, Any]:
        """包括的コード品質分析"""
        all_issues = []
        
        # スタイルチェック
        style_issues = self.style_checker.check_code_style(code, file_path)
        all_issues.extend(style_issues)
        
        # ドキュメントチェック
        doc_issues = self.documentation_checker.check_docstrings(code, file_path)
        all_issues.extend(doc_issues)
        
        # 複雑度分析
        cyclomatic_complexity = self.complexity_analyzer.calculate_cyclomatic_complexity(code)
        cognitive_complexity = self.complexity_analyzer.calculate_cognitive_complexity(code)
        
        # メトリクス計算
        lines = code.split('\n')
        metrics = CodeMetrics(
            lines_of_code=len([line for line in lines if line.strip()]),
            cyclomatic_complexity=cyclomatic_complexity,
            cognitive_complexity=cognitive_complexity,
            maintainability_index=self._calculate_maintainability_index(
                cyclomatic_complexity, 
                len(lines), 
                len(all_issues)
            )
        )
        
        # 品質スコア計算
        quality_score = self._calculate_quality_score(all_issues, metrics)
        
        return {
            'file_path': file_path,
            'issues': [issue.__dict__ for issue in all_issues],
            'metrics': metrics.__dict__,
            'quality_score': quality_score,
            'issue_summary': self._summarize_issues(all_issues),
            'recommendations': self._generate_recommendations(all_issues, metrics)
        }
    
    def analyze_function_quality(self, func: Callable) -> Dict[str, Any]:
        """関数の品質分析"""
        try:
            file_path = inspect.getfile(func)
            source = inspect.getsource(func)
            
            # 型チェック
            type_issues = self.type_checker.check_function_types(func)
            
            # 基本分析に型問題を追加
            analysis = self.analyze_code_quality(source, file_path)
            analysis['issues'].extend([issue.__dict__ for issue in type_issues])
            
            # 関数固有のメトリクス
            func_complexity = self.complexity_analyzer.analyze_function_complexity(func)
            analysis['function_metrics'] = func_complexity
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Function quality analysis error: {e}")
            return {
                'error': str(e),
                'function_name': getattr(func, '__name__', 'unknown')
            }
    
    def fix_code_quality_issues(self, code: str, issues: List[CodeIssue]) -> Tuple[str, List[str]]:
        """コード品質問題の自動修正"""
        fixed_code = self.auto_fixer.apply_auto_fixes(code, issues)
        
        applied_fixes = []
        for issue in issues:
            if issue.auto_fixable:
                applied_fixes.append(f"Fixed {issue.rule_id}: {issue.message}")
        
        return fixed_code, applied_fixes
    
    def _calculate_maintainability_index(self, complexity: int, 
                                       lines_of_code: int, 
                                       issue_count: int) -> float:
        """保守性指標計算"""
        if lines_of_code == 0:
            return 0.0
        
        # 簡略化された保守性指標
        base_score = 100
        complexity_penalty = complexity * 2
        size_penalty = lines_of_code * 0.1
        issue_penalty = issue_count * 5
        
        score = base_score - complexity_penalty - size_penalty - issue_penalty
        return max(0.0, min(100.0, score))
    
    def _calculate_quality_score(self, issues: List[CodeIssue], 
                                metrics: CodeMetrics) -> float:
        """総合品質スコア計算"""
        base_score = 100.0
        
        # 問題による減点
        for issue in issues:
            if issue.severity == CodeSeverity.CRITICAL:
                base_score -= 10
            elif issue.severity == CodeSeverity.ERROR:
                base_score -= 5
            elif issue.severity == CodeSeverity.WARNING:
                base_score -= 2
            elif issue.severity == CodeSeverity.INFO:
                base_score -= 1
        
        # 複雑度による減点
        if metrics.cyclomatic_complexity > 15:
            base_score -= (metrics.cyclomatic_complexity - 15) * 2
        
        if metrics.cognitive_complexity > 20:
            base_score -= (metrics.cognitive_complexity - 20) * 1.5
        
        return max(0.0, min(100.0, base_score))
    
    def _summarize_issues(self, issues: List[CodeIssue]) -> Dict[str, int]:
        """問題の要約"""
        summary = {
            'total': len(issues),
            'critical': 0,
            'error': 0,
            'warning': 0,
            'info': 0,
            'by_type': {}
        }
        
        for issue in issues:
            summary[issue.severity.value] += 1
            
            issue_type = issue.issue_type.value
            if issue_type not in summary['by_type']:
                summary['by_type'][issue_type] = 0
            summary['by_type'][issue_type] += 1
        
        return summary
    
    def _generate_recommendations(self, issues: List[CodeIssue], 
                                metrics: CodeMetrics) -> List[str]:
        """改善推奨事項生成"""
        recommendations = []
        
        # 複雑度の推奨事項
        if metrics.cyclomatic_complexity > 15:
            recommendations.append(
                f"Reduce cyclomatic complexity ({metrics.cyclomatic_complexity}) "
                "by breaking down functions into smaller pieces"
            )
        
        if metrics.cognitive_complexity > 20:
            recommendations.append(
                f"Reduce cognitive complexity ({metrics.cognitive_complexity}) "
                "by simplifying control flow"
            )
        
        # 問題タイプ別推奨事項
        issue_types = set(issue.issue_type for issue in issues)
        
        if CodeIssueType.DOCUMENTATION in issue_types:
            recommendations.append("Add comprehensive docstrings to improve code documentation")
        
        if CodeIssueType.TYPE_SAFETY in issue_types:
            recommendations.append("Add type annotations to improve code safety and readability")
        
        if CodeIssueType.STYLE in issue_types:
            recommendations.append("Follow consistent code style guidelines")
        
        return recommendations
    
    def get_quality_report(self, file_patterns: List[str] = None) -> Dict[str, Any]:
        """品質レポート生成"""
        with self.lock:
            return {
                'analyzed_files': len(self.quality_reports),
                'total_reports': list(self.quality_reports.keys()),
                'summary_statistics': self._calculate_summary_statistics()
            }
    
    def _calculate_summary_statistics(self) -> Dict[str, Any]:
        """要約統計計算"""
        if not self.quality_reports:
            return {}
        
        all_scores = [report['quality_score'] for report in self.quality_reports.values()]
        all_issues = []
        for report in self.quality_reports.values():
            all_issues.extend(report['issues'])
        
        return {
            'average_quality_score': sum(all_scores) / len(all_scores),
            'total_issues': len(all_issues),
            'files_with_issues': len([r for r in self.quality_reports.values() if r['issues']])
        }

# Convenience decorators
def quality_check(auto_fix: bool = False):
    """コード品質チェックデコレーター"""
    def decorator(func):
        manager = get_code_quality_manager()
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 関数の品質をチェック
            quality_report = manager.analyze_function_quality(func)
            
            # 問題があれば警告
            if quality_report.get('issues'):
                manager.logger.warning(
                    f"Quality issues found in {func.__name__}: "
                    f"{len(quality_report['issues'])} issues"
                )
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

# Global code quality manager
_global_code_quality_manager = None

def get_code_quality_manager() -> CodeQualityManager:
    """グローバルコード品質マネージャー取得"""
    global _global_code_quality_manager
    if _global_code_quality_manager is None:
        _global_code_quality_manager = CodeQualityManager()
    return _global_code_quality_manager

if __name__ == "__main__":
    # コード品質チェックのテスト
    print("✨ Code Quality Manager Test")
    print("=" * 40)
    
    manager = get_code_quality_manager()
    
    # テストコード
    test_code = '''
def bad_function(x,y,z,a,b,c,d,e):
    if x > 0:
        if y > 0:
            if z > 0:
                if a > 0:
                    if b > 0:
                        return x + y + z + a + b
    return 0

class TestClass:
    def method_without_docstring(self):
        pass
'''
    
    # 品質分析
    analysis = manager.analyze_code_quality(test_code, "test.py")
    
    print(f"Quality Score: {analysis['quality_score']:.1f}/100")
    print(f"Issues Found: {analysis['issue_summary']['total']}")
    print(f"Cyclomatic Complexity: {analysis['metrics']['cyclomatic_complexity']}")
    print(f"Cognitive Complexity: {analysis['metrics']['cognitive_complexity']}")
    
    print("\nRecommendations:")
    for rec in analysis['recommendations']:
        print(f"  • {rec}")
    
    # 自動修正テスト
    issues = [CodeIssue(**issue) for issue in analysis['issues']]
    fixed_code, applied_fixes = manager.fix_code_quality_issues(test_code, issues)
    
    if applied_fixes:
        print(f"\nApplied {len(applied_fixes)} automatic fixes")
        for fix in applied_fixes:
            print(f"  • {fix}")