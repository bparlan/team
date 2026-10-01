#!/usr/bin/env python3
"""
Core Analysis Engine for System Architecture Design Awareness

This is Phase 1: Project Structure Analysis implementation.

Part of a 4-phase comprehensive system architecture analysis:
- Phase 1: Project Structure Analysis (implemented)
- Phase 2: Documentation Audit (implemented)
- Phase 3: Architecture Review (implemented)
- Phase 4: System Health & Continuous Monitoring (implemented)

Ponytail principles applied:
- Delete weightless code, prefer standard library
- Minimal complexity, maximal effectiveness
- Modular composition, readability first
"""

import os
import json
import ast
import hashlib
import yaml
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, List, Any, Optional

class SystemArchitectureAnalyzer:
    """
    Comprehensive system architecture analyzer with 4 analysis phases.
    
    Implements the System Architecture Design Awareness task as a scalable,
    recursive analysis framework following Ponytail principles.
    """
    
    # 2MB cap. Without it this ledger grows without bound — it reached 25MB
    # and was committed, because nothing that could write it also trimmed it.
    # The cap is not new policy: it was already implemented in the
    # `optimized_system_awareness_runner` variant, which nothing imported, so
    # the protection existed in the repo while the live analyzer had none.
    LEDGER_MAX_BYTES = 2 * 1024 * 1024

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.ledger_file = self.project_root / "system-awareness-ledger.json"
        self.report_dir = self.project_root / "theteam" / "reports"
        self.load_ledger()

    def _rotate_ledger(self) -> None:
        """Archive an oversized ledger before rewriting it.

        Rotation rather than truncation: the previous analysis stays readable
        on disk instead of being deleted, which is the only reason to keep a
        ledger at all.
        """
        archive_dir = self.ledger_file.parent / "archives"
        archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        try:
            self.ledger_file.replace(archive_dir / f"ledger_{stamp}.json")
        except OSError as exc:
            # A failed archive must not lose the ledger. The write below
            # truncates, so an unrotated oversized file still gets replaced
            # rather than left in place.
            print(f"Warning: could not archive ledger ({exc}); continuing")
        
    def load_ledger(self):
        """Load analysis ledger or create new one."""
        if self.ledger_file.exists():
            with open(self.ledger_file, 'r') as f:
                self.ledger_data = json.load(f)
        else:
            self.ledger_data = {
                "version": "1.0.0",
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "project_root": str(self.project_root),
                "scan_depth": "recursive",
                "scope": {
                    "include_patterns": ["*.py", "*.md", "*.json", "*.yaml", "*.yml"],
                    "exclude_patterns": ["__pycache__", ".git", ".loop-log", "node_modules", "build/", "dist/", "*.egg-info/"]
                },
                "analysis_components": [
                    "project_structure",
                    "documentation_audit", 
                    "architecture_review",
                    "infrastructure_assessment"
                ],
                "health_metrics": {
                    "documentation_completeness": 0.0,
                    "architecture_cohesion": 0.0,
                    "technical_debt_ratio": 0.0,
                    "system_health_score": 0.0,
                    "infrastructure_automation": 0.0,
                    "maintainability_score": 0.0
                },
                "analysis_history": [],
                "continuous_monitoring": {
                    "enabled": True,
                    "check_interval_minutes": 30,
                    "auto_analysis": True,
                    "alert_threshold": 75
                }
            }
    
    def save_ledger(self):
        """Save analysis ledger to disk, rotating it if it has grown too large."""
        if self.ledger_file.exists() and self.ledger_file.stat().st_size > self.LEDGER_MAX_BYTES:
            self._rotate_ledger()
        with open(self.ledger_file, 'w') as f:
            json.dump(self.ledger_data, f, indent=2)
    
    def run_complete_analysis(self) -> Dict[str, Any]:
        """
        Execute complete 4-phase system architecture analysis.
        
        Returns comprehensive analysis results including all phases and health metrics.
        """
        print("=" * 60)
        print("🔍 STARTING SYSTEM ARCHITECTURE ANALYSIS")
        print("=" * 60)
        
        # Phase 1: Project Structure Analysis
        print("Phase 1: Project Structure Analysis")
        print("-" * 40)
        project_structure = self.analyze_project_structure()
        print("✅ Project structure analysis completed")
        
        # Phase 2: Documentation Audit
        print("Phase 2: Documentation Audit")
        print("-" * 40)
        documentation = self.analyze_documentation()
        print("✅ Documentation analysis completed")
        
        # Phase 3: Architecture Review
        print("Phase 3: Architecture Review")
        print("-" * 40)
        architecture = self.analyze_architecture()
        print("✅ Architecture analysis completed")
        
        # Phase 4: Infrastructure Assessment
        print("Phase 4: Infrastructure Assessment")
        print("-" * 40)
        infrastructure = self.analyze_infrastructure()
        print("✅ Infrastructure analysis completed")
        
        # Generate comprehensive health score
        analysis_results = {
            "project_structure": project_structure,
            "documentation": documentation,
            "architecture": architecture,
            "infrastructure": infrastructure
        }
        
        health_score = self.generate_system_health_score(analysis_results)
        analysis_results["health_score"] = health_score
        
        # Update ledger with complete analysis
        self.update_ledger(analysis_results)
        
        # Generate comprehensive reports
        full_report = self.generate_complete_report(analysis_results)
        
        # Save report
        report_file = self.report_dir / f"system-architecture-analysis-{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
        # `self.report_dir` is `<root>/theteam/reports`, which exists in *this*
        # repo and no other project. Creating it keeps the analyzer runnable
        # against any project root; without this it died with FileNotFoundError
        # on its first write, which is a crash, not a score.
        self.report_dir.mkdir(parents=True, exist_ok=True)
        with open(report_file, 'w') as f:
            f.write(full_report)
            
        print(f"✅ Analysis report saved: {report_file}")
        
        # Generate ledger summary
        self.generate_ledger_summary()
        
        return {
            "analysis_results": analysis_results,
            "report_file": str(report_file),
            "ledger_file": str(self.ledger_file)
        }
    
    def analyze_project_structure(self) -> Dict[str, Any]:
        """
        Phase 1: Analyze project structure, modules, and dependencies.
        
        Returns comprehensive project structure analysis including
        module organization, complexity metrics, and relationship mapping.
        """
        structure = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_root": str(self.project_root),
            "modules": {},
            "relationships": [],
            "metrics": {
                "total_files": 0,
                "total_directories": 0,
                "file_types": defaultdict(int),
                "cyclomatic_complexity": 0,
                "maintainability_index": 0.0,
                "module_count": 0
            },
            "redundancies": [],
            "optimizations": []
        }
        
        EXCLUDED_DIRS = {'__pycache__', '.git', '.loop-log', 'node_modules', 'build', 'dist', 'examples'}
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            self._analyze_directory_structure(root, dirs, files, structure)

        self._identify_and_remove_redundancies(structure)
        self._optimize_relationships(structure)

        return structure
    
    def _analyze_directory_structure(self, root: str, dirs: List[str], files: List[str], structure: Dict[str, Any]) -> None:
        """Analyze directory structure and extract file information."""
        root_path = Path(root)
        
        structure["metrics"]["total_directories"] += len(dirs)
        structure["metrics"]["total_files"] += len(files)
        
        for file in files:
            if file.endswith(('.py', '.json', '.md', '.yaml', '.yml', '.txt')):
                file_path = root_path / file
                self._analyze_code_file(file_path, structure)
                
                ext = file_path.suffix.lower() or "no_extension"
                structure["metrics"]["file_types"][ext] += 1
    
    def _analyze_code_file(self, file_path: Path, structure: Dict[str, Any]) -> None:
        """Analyze code file using AST parsing."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            file_info = {
                "path": str(file_path),
                "size": len(content),
                "complexity": self._calculate_cyclomatic_complexity(content),
                "maintainability": self._calculate_maintainability_index(content),
                "imports": self._extract_imports(content),
                "functions": self._extract_functions(content),
                "classes": self._extract_classes(content),
                "filename": file_path.name,
                "extension": file_path.suffix.lower()
            }
            
            module_name = file_path.stem
            structure["modules"][module_name] = file_info
            
            relationships = self._extract_simple_relationships(file_info)
            if relationships:
                structure["relationships"].extend(relationships)
                
        except Exception as e:
            file_info = {
                "path": str(file_path),
                "error": str(e),
                "error_only": True
            }
            structure["modules"][file_path.stem] = file_info
    
    def _calculate_cyclomatic_complexity(self, content: str) -> int:
        """Calculate cyclomatic complexity using AST."""
        try:
            tree = ast.parse(content)
            complexity = 1
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.For, ast.While, ast.And, ast.Or, ast.Try)):
                    complexity += 1
                elif isinstance(node, ast.ExceptHandler):
                    complexity += 1
                    
            return complexity
        except:
            return 0
    
    def _calculate_maintainability_index(self, content: str) -> float:
        """Calculate maintainability index using simple heuristics."""
        lines = content.split('\n')
        non_empty_lines = len([line for line in lines if line.strip()])
        
        if non_empty_lines == 0:
            return 0.0
            
        comment_ratio = len([line for line in lines if line.strip().startswith('#')]) / non_empty_lines
        loc_per_function = self._estimate_loc_per_function(content)
        
        score = 100.0
        score -= (len(lines) / 10)
        score -= (loc_per_function / 5)
        score += (comment_ratio * 40)
        
        return max(0.0, min(100.0, score))
    
    def _estimate_loc_per_function(self, content: str) -> float:
        """Estimate average lines per function."""
        try:
            tree = ast.parse(content)
            function_count = len([node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)])
            
            if function_count == 0:
                return len(content.split('\n'))
                
            return len(content.split('\n')) / function_count
        except:
            return len(content.split('\n'))
    
    def _extract_imports(self, content: str) -> List[str]:
        """Extract import statements using AST."""
        imports = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        imports.append(f"{module}.{alias.name}")
        except:
            pass
        return imports
    
    def _extract_functions(self, content: str) -> List[Dict[str, Any]]:
        """Extract function definitions with metadata."""
        functions = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        "name": node.name,
                        "line": node.lineno,
                        "complexity": self._calculate_function_complexity(node),
                        "length": self._calculate_function_length(node)
                    })
        except:
            pass
        return functions
    
    def _extract_classes(self, content: str) -> List[Dict[str, Any]]:
        """Extract class definitions with metadata."""
        classes = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = len([n for n in node.body if isinstance(n, ast.FunctionDef)])
                    classes.append({
                        "name": node.name,
                        "line": node.lineno,
                        "methods": methods,
                        "complexity": self._calculate_class_complexity(node)
                    })
        except:
            pass
        return classes
    
    def _calculate_function_complexity(self, func_node: ast.FunctionDef) -> int:
        """Calculate function cyclomatic complexity."""
        complexity = 1
        for node in ast.walk(func_node):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.And, ast.Or, ast.Try)):
                complexity += 1
            elif isinstance(node, ast.ExceptHandler):
                complexity += 1
        return complexity
    
    def _calculate_function_length(self, func_node: ast.FunctionDef) -> int:
        """Calculate function length in lines."""
        if hasattr(func_node, 'end_lineno'):
            return func_node.end_lineno - func_node.lineno + 1
        return 0
    
    def _calculate_class_complexity(self, class_node: ast.ClassDef) -> int:
        """Calculate class complexity based on methods."""
        return len([n for n in class_node.body if isinstance(n, ast.FunctionDef)])
    
    def _extract_simple_relationships(self, module_info: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract module relationships using simplified logic."""
        relationships = []
        
        for import_stmt in module_info.get("imports", []):
            if import_stmt.startswith("theteam."):
                target_module = import_stmt.split(".", 1)[1]
                if target_module:
                    relationships.append({
                        "type": "import",
                        "source": module_info["path"],
                        "target": target_module,
                        "direction": "depends_on"
                    })
                    
        return relationships
    
    def _identify_and_remove_redundancies(self, structure: Dict[str, Any]) -> None:
        """Identify and suggest removal of redundant code."""
        redundancies = []
        
        # Detect duplicate modules (same file paths)
        self._detect_duplicate_modules(structure, redundancies)
        
        # Detect unnecessary abstractions
        self._detect_unnecessary_abstractions(structure, redundancies)
        
        structure["redundancies"] = redundancies
        
        if redundancies:
            structure["optimizations"].extend([
                "Consolidate duplicate modules into single files",
                "Remove unnecessary helper functions that wrap standard library",
                "Simplify imports and remove unused dependencies",
                "Consolidate similar configuration files",
                "Optimize directory structure based on actual dependencies"
            ])
    
    def _detect_duplicate_modules(self, structure: Dict[str, Any], redundancies: List[Dict[str, str]]) -> None:
        """Detect modules that could be consolidated."""
        modules_by_import = defaultdict(list)
        
        for module_name, module_info in structure["modules"].items():
            if not module_info.get("error"):
                imports = module_info.get("imports", [])
                for imp in imports:
                    modules_by_import[imp].append(module_name)
        
        for import_source, modules in modules_by_import.items():
            if len(modules) > 1:
                redundancies.append({
                    "type": "duplicate_imports",
                    "location": f"Modules: {', '.join(modules[:3])}",
                    "severity": "low",
                    "suggestion": f"Consider consolidating common imports in {import_source}"
                })
    
    def _detect_unnecessary_abstractions(self, structure: Dict[str, Any], redundancies: List[Dict[str, str]]) -> None:
        """Detect overly complex modules and unnecessary abstractions."""
        for module_name, module_info in structure["modules"].items():
            if module_info.get("error"):
                continue
                
            functions = module_info.get("functions", [])
            if len(functions) <= 1 and module_info.get("lines", 0) > 50:
                redundancies.append({
                    "type": "overly_complex_module",
                    "location": module_info["path"],
                    "severity": "medium",
                    "suggestion": "Consider splitting or simplifying this module"
                })
    
    def _optimize_relationships(self, structure: Dict[str, Any]) -> None:
        """Optimize module relationships for better modularity."""
        dependencies = defaultdict(int)
        
        for rel in structure["relationships"]:
            dependencies[rel["target"]] += 1
        
        for target, dep_count in dependencies.items():
            if dep_count > 5:
                structure["optimizations"].append(
                    f"Consider consolidating modules that depend heavily on {target}"
                )
                break
    
    def analyze_documentation(self) -> Dict[str, Any]:
        """
        Phase 2: Comprehensive documentation audit.
        
        Analyzes documentation structure, completeness, and quality.
        """
        docs_structure = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "documentation_files": [],
            "quality_metrics": {
                "total_files": 0,
                "coverage_score": 0.0,
                "format_consistency": 0.0,
                "completeness_score": 0.0,
                "content_quality": 0.0,
                "structure_score": 0.0
            },
            "gaps": [],
            "recommendations": [],
            "format_analysis": {},
            "content_analysis": {}
        }
        
        # Discover documentation files
        self._discover_documentation_files(docs_structure)
        
        # Assess documentation quality
        self._assess_documentation_quality(docs_structure)
        
        # Identify gaps and generate recommendations
        self._identify_documentation_gaps(docs_structure)
        
        return docs_structure
    
    def _discover_documentation_files(self, docs_structure: Dict[str, Any]) -> None:
        """Discover and catalog documentation files."""
        doc_patterns = [
            "*.md", "*.rst", "*.txt", "README*", "CONTRIBUTING*",
            "CHANGELOG*", "LICENSE*", "SECURITY_POLICY*",
            "INSTALL*", "USAGE*", "API*", "DEVELOPMENT*", "TESTING*"
        ]
        
        for pattern in doc_patterns:
            for doc_path in self.project_root.glob("**/" + pattern):
                if doc_path.is_file():
                    doc_info = self._analyze_documentation_file(doc_path)
                    docs_structure["documentation_files"].append(doc_info)
                    docs_structure["quality_metrics"]["total_files"] += 1
        
        if docs_structure["quality_metrics"]["total_files"] > 0:
            docs_structure["quality_metrics"]["coverage_score"] = self._calculate_coverage_score(docs_structure)
    
    def _analyze_documentation_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze individual documentation file."""
        file_info = {
            "path": str(file_path),
            "filename": file_path.name,
            "extension": file_path.suffix.lower(),
            "size": file_path.stat().st_size,
            "last_modified": file_path.stat().st_mtime,
            "metrics": {
                "word_count": 0,
                "character_count": 0,
                "line_count": 0,
                "non_empty_lines": 0,
                "heading_count": 0,
                "code_block_count": 0,
                "list_count": 0,
                "image_count": 0,
                "link_count": 0,
                "table_count": 0,
                "completeness_score": 0.0,
                "structure_score": 0.0,
                "content_score": 0.0
            },
            "format_analysis": self._analyze_format_structure(file_path),
            "content_issues": [],
            "format_issues": [],
            "recommendations": []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
            file_info["metrics"]["character_count"] = len(content)
            file_info["metrics"]["line_count"] = len(lines)
            file_info["metrics"]["word_count"] = len(content.split())
            
            non_empty = [line for line in lines if line.strip()]
            file_info["metrics"]["non_empty_lines"] = len(non_empty)
            
            # Structure analysis
            file_info["metrics"]["heading_count"] = len([line for line in lines if line.startswith('#')])
            file_info["metrics"]["code_block_count"] = len([line for line in lines if line.strip().startswith('```')])
            file_info["metrics"]["list_count"] = len([line for line in lines if line.strip().startswith('- ') or line.strip().startswith('* ') or line.strip().startswith('1. ')])
            file_info["metrics"]["image_count"] = len([line for line in lines if '![alt text](' in line or '![](images/' in line])
            file_info["metrics"]["link_count"] = len([line for line in lines if '](' in line and '(' in line[lines.index(line):lines.index(line)+50]])
            file_info["metrics"]["table_count"] = len([line for line in lines if '|' in line or line.strip().startswith('|')])
            
            # Calculate scores
            file_info["metrics"]["completeness_score"] = self._calculate_file_completeness_score(file_info["metrics"])
            file_info["metrics"]["structure_score"] = self._calculate_structure_score(file_info["metrics"])
            file_info["metrics"]["content_score"] = self._calculate_content_score(file_info["metrics"])
            
            self._identify_documentation_issues(file_info)
            
        except Exception as e:
            file_info["error"] = str(e)
            
        return file_info
    
    def _analyze_format_structure(self, file_path: Path) -> Dict[str, Any]:
        """Analyze documentation format structure."""
        format_info = {
            "has_toc": False,
            "consistent_headings": True,
            "proper_markdown": file_path.suffix.lower() == ".md",
            "code_block_language": False,
            "image_alt_text": False,
            "link_validation": False
        }
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                lines = content.split('\n')
                
            # TOC detection
            toc_markers = ['[TOC]', '## Table of Contents', '[Contents]']
            format_info["has_toc"] = any(marker in content for marker in toc_markers)
            
            # Heading consistency
            heading_levels = [len(line) - len(line.lstrip('#')) for line in lines if line.startswith('#')]
            if heading_levels:
                format_info["consistent_headings"] = max(heading_levels) - min(heading_levels) <= 2
                
        except:
            pass
            
        return format_info
    
    def _calculate_coverage_score(self, docs_structure: Dict[str, Any]) -> float:
        """Calculate documentation coverage score."""
        total_files = docs_structure["quality_metrics"]["total_files"]
        
        expected_docs = [
            "README.md", "CONTRIBUTING.md", "INSTALL.md", "USAGE.md",
            "API.md", "DEVELOPMENT.md", "TESTING.md", "CHANGELOG.md",
            "LICENSE.md", "SECURITY_POLICY.md"
        ]
        
        present_expected = sum(1 for expected in expected_docs 
                             if any(expected.lower() in f["filename"].lower() 
                                   for f in docs_structure["documentation_files"]))
        
        return present_expected / len(expected_docs) if expected_docs else 0.0
    
    def _calculate_file_completeness_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate individual file completeness score."""
        score = 0.0
        
        if metrics["word_count"] >= 200:
            score += 0.25
        if metrics["heading_count"] >= 2:
            score += 0.15
        if metrics["code_block_count"] >= 1:
            score += 0.15
        if metrics["link_count"] >= 3:
            score += 0.15
        if metrics["image_count"] >= 1:
            score += 0.10
        if metrics["table_count"] >= 1:
            score += 0.10
        if metrics["list_count"] >= 2:
            score += 0.10
            
        return min(score, 1.0)
    
    def _calculate_structure_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate structure quality score."""
        score = 0.0
        
        if metrics["heading_count"] >= 3:
            score += 0.3
        if metrics["code_block_count"] >= 2:
            score += 0.2
        if metrics["table_count"] >= 1:
            score += 0.2
        if metrics["image_count"] >= 2:
            score += 0.2
        if metrics["link_count"] >= 5:
            score += 0.1
            
        return min(score, 1.0)
    
    def _calculate_content_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate content quality score."""
        score = 0.0
        
        if metrics["word_count"] >= 500:
            score += 0.3
        if metrics["image_count"] >= 2:
            score += 0.2
        if metrics["code_block_count"] >= 3:
            score += 0.2
        if metrics["table_count"] >= 2:
            score += 0.2
            
        return min(score, 1.0)
    
    def _identify_documentation_issues(self, file_info: Dict[str, Any]) -> None:
        """Identify documentation issues and generate recommendations."""
        issues = []
        
        if file_info["metrics"]["word_count"] < 50:
            issues.append("Content may be too brief")
        if file_info["metrics"]["heading_count"] == 0:
            issues.append("Missing structure/headings")
        if file_info["metrics"]["code_block_count"] == 0:
            issues.append("Missing code examples")
        if file_info["metrics"]["link_count"] == 0:
            issues.append("Missing references to other documentation")
            
        file_info["content_issues"] = issues
        
        if issues:
            file_info["recommendations"].append("Expand content and improve structure")
    
    def _assess_documentation_quality(self, docs_structure: Dict[str, Any]) -> None:
        """Assess overall documentation quality."""
        if docs_structure["documentation_files"]:
            avg_completeness = sum(
                f["metrics"]["completeness_score"]
                for f in docs_structure["documentation_files"]
                if not f.get("error")
            ) / len([f for f in docs_structure["documentation_files"] if not f.get("error")])
            
            docs_structure["quality_metrics"]["completeness_score"] = avg_completeness
            
            avg_structure = sum(
                f["metrics"]["structure_score"]
                for f in docs_structure["documentation_files"]
                if not f.get("error")
            ) / len([f for f in docs_structure["documentation_files"] if not f.get("error")])
            
            docs_structure["quality_metrics"]["structure_score"] = avg_structure
            
            avg_content = sum(
                f["metrics"]["content_score"]
                for f in docs_structure["documentation_files"]
                if not f.get("error")
            ) / len([f for f in docs_structure["documentation_files"] if not f.get("error")])
            
            docs_structure["quality_metrics"]["content_score"] = avg_content
            
            # This was the literal `0.8` — a number that looked like a
            # measurement and was not one. It carries 0.3 weight in the
            # documentation total below, so every project got a free 0.24 on
            # that component. Now derived from the per-file `format_analysis`
            # this class already collects: the share of markdown files with
            # both a table of contents and consistent heading levels.
            markdown_files = [f for f in docs_structure["documentation_files"]
                              if not f.get("error") and f["extension"] == ".md"]
            if markdown_files:
                consistent = sum(
                    1 for f in markdown_files
                    if f["format_analysis"].get("has_toc", False)
                    and f["format_analysis"].get("consistent_headings", False)
                )
                docs_structure["quality_metrics"]["format_consistency"] = (
                    consistent / len(markdown_files))
            else:
                docs_structure["quality_metrics"]["format_consistency"] = 0.0
    
    def _identify_documentation_gaps(self, docs_structure: Dict[str, Any]) -> None:
        """Identify documentation gaps and generate recommendations."""
        gaps = []
        recommendations = []
        
        # Critical gap analysis
        if docs_structure["quality_metrics"]["total_files"] < 3:
            gaps.append({
                "type": "insufficient_documentation",
                "severity": "high",
                "description": f"Only {docs_structure['quality_metrics']['total_files']} documentation files found",
                "recommendation": "Add comprehensive documentation files: README, CONTRIBUTING, INSTALL, API documentation"
            })
        
        # Format consistency analysis
        format_issues = []
        for file_info in docs_structure["documentation_files"]:
            if file_info.get("error"):
                continue
                
            if file_info["extension"] == ".md":
                if not file_info["format_analysis"].get("has_toc", False):
                    format_issues.append(f"Missing table of contents in {file_info['filename']}")
                if not file_info["format_analysis"].get("consistent_headings", False):
                    format_issues.append(f"Inconsistent heading levels in {file_info['filename']}")
        
        if format_issues:
            gaps.append({
                "type": "format_inconsistency",
                "severity": "medium",
                "description": f"{len(format_issues)} format consistency issues found",
                "recommendation": "Standardize markdown formatting across all documentation files"
            })
        
        # Quality score analysis
        total_score = (
            docs_structure["quality_metrics"]["coverage_score"] * 0.3 +
            docs_structure["quality_metrics"]["format_consistency"] * 0.3 +
            docs_structure["quality_metrics"]["completeness_score"] * 0.4
        )
        
        if total_score < 0.6:
            gaps.append({
                "type": "quality_issues",
                "severity": "medium",
                "description": f"Overall documentation quality score: {total_score:.2f}/1.0",
                "recommendation": "Focus on improving content completeness and structure quality"
            })
        
        # Generate recommendations
        if gaps:
            recommendations.extend([
                "Establish comprehensive documentation standards",
                "Create documentation templates for consistency",
                "Implement automated documentation quality checks",
                "Schedule regular documentation reviews and updates"
            ])
        
        docs_structure["gaps"] = gaps
        docs_structure["recommendations"] = recommendations
    
    def analyze_architecture(self) -> Dict[str, Any]:
        """
        Phase 3: Comprehensive architecture review.
        
        Analyzes architectural patterns, design decisions, and technical debt.
        """
        architecture = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "design_patterns": [],
            "architectural_decisions": [],
            "technical_debt": [],
            "maintainability_indicators": {
                "code_organization": 0.0,
                "separation_of_concerns": 0.0,
                "dependency_management": 0.0,
                "test_coverage": 0.0
            },
            "recommendations": []
        }
        
        # Architecture is detected from *any* conventional source root, not this
        # repository's own directory names. These two branches used to test for
        # `theteam/core` and `theteam/security` specifically, so every other
        # project scored zero on architecture for not being this repo — a
        # measurement of the wrong thing that read as a real measurement.
        for source_root in ("src", "lib", "app", "pkg", "theteam"):
            if (self.project_root / source_root).is_dir():
                architecture["design_patterns"].append({
                    "name": "Separated source root",
                    "description": "Source is separated from the project root",
                    "location": source_root,
                    "quality_score": 0.9
                })
                break

        # A dedicated security module, whatever this project happens to call it.
        for candidate in sorted(self.project_root.glob("*")):
            if not candidate.is_dir():
                continue
            if {"security", "auth"} & {p.name.lower() for p in candidate.iterdir()}:
                architecture["architectural_decisions"].append({
                    "pattern": "Security-First Design",
                    "implementation": f"Dedicated module in {candidate.name}/",
                    "rationale": "Centralized security controls and validation",
                    "impact": "High - provides consistent security enforcement"
                })
                break
        
        # Check for technical debt
        if self._detect_technical_debt():
            architecture["technical_debt"].extend(self._identify_technical_debt())
            
        return architecture
    
    def analyze_infrastructure(self) -> Dict[str, Any]:
        """
        Phase 4: Infrastructure and build systems analysis.
        
        Analyzes build systems, deployment configurations, and environment management.
        """
        infrastructure = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "build_systems": [],
            "deployment_configs": [],
            "environment_configs": [],
            "quality_metrics": {
                "build_automation": 0.0,
                "configuration_management": 0.0,
                "environment_consistency": 0.0
            }
        }
        
        # Check for build configuration files
        build_files = [
            "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
            "Dockerfile", "docker-compose.yml", "Makefile", "tox.ini",
            ".github/workflows", ".gitlab-ci.yml", "azure-pipelines.yml"
        ]
        
        for build_file in build_files:
            file_path = self.project_root / build_file
            if file_path.exists():
                infrastructure["build_systems"].append({
                    "type": build_file,
                    "path": str(file_path),
                    "status": "configured"
                })
                
        # Check for environment configuration
        env_patterns = [".env.example", ".env.template", "config.json", "settings.py"]
        for env_file in env_patterns:
            env_path = self.project_root / env_file
            if env_path.exists():
                infrastructure["environment_configs"].append({
                    "type": env_file,
                    "path": str(env_path),
                    "status": "configured"
                })
                
        return infrastructure
    
    def generate_system_health_score(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive system health score with weighted components.
        
        Follows Ponytail principle: minimal complexity, maximum effectiveness.
        """
        health_metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_score": 0.0,
            "component_scores": {},
            "grade": "F",
            "recommendations": []
        }
        
        # Calculate component scores
        project_score = self._calculate_project_score(analysis_results["project_structure"])
        docs_score = analysis_results["documentation"]["quality_metrics"]["completeness_score"]
        arch_score = self._calculate_architecture_score(analysis_results["architecture"])
        infra_score = self._calculate_infrastructure_score(analysis_results["infrastructure"])
        
        component_scores = {
            "project_structure": project_score,
            "documentation": docs_score,
            "architecture": arch_score,
            "infrastructure": infra_score
        }
        
        # Weighted scoring (Phase 2: Documentation emphasis)
        weights = {
            "project_structure": 0.25,
            "documentation": 0.30,
            "architecture": 0.25,
            "infrastructure": 0.20
        }
        
        overall_score = sum(
            component_scores[component] * weights[component]
            for component in component_scores
        )
        
        health_metrics["overall_score"] = overall_score
        health_metrics["component_scores"] = component_scores
        
        # Assign grade
        if overall_score >= 0.9:
            health_metrics["grade"] = "A+"
        elif overall_score >= 0.8:
            health_metrics["grade"] = "A"
        elif overall_score >= 0.7:
            health_metrics["grade"] = "B"
        elif overall_score >= 0.6:
            health_metrics["grade"] = "C"
        elif overall_score >= 0.5:
            health_metrics["grade"] = "D"
        else:
            health_metrics["grade"] = "F"
            
        # Generate recommendations based on scores
        if overall_score < 0.7:
            health_metrics["recommendations"].extend([
                "Improve documentation completeness",
                "Review and refactor complex functions",
                "Enhance test coverage",
                "Standardize configuration management"
            ])
        
        return health_metrics
    
    def _calculate_project_score(self, structure: Dict[str, Any]) -> float:
        """Calculate project structure quality score."""
        if not structure:
            return 0.0
            
        score = 0.0
        
        # Module organization
        if "modules" in structure and len(structure["modules"]) > 3:
            score += 0.4
            
        # Relationship complexity
        if "relationships" in structure:
            relationship_count = len(structure["relationships"])
            if relationship_count < 20:
                score += 0.3
                
        # Nesting depth
        max_depth = structure.get("metrics", {}).get("nesting_depth", 0)
        if max_depth < 3:
            score += 0.3
            
        return min(score, 1.0)
    
    def _calculate_architecture_score(self, architecture: Dict[str, Any]) -> float:
        """Calculate architecture quality score."""
        if not architecture:
            return 0.0
            
        score = 0.0
        
        # Design patterns
        design_patterns = architecture.get("design_patterns", [])
        if len(design_patterns) >= 2:
            score += 0.4
            
        # Architectural decisions
        arch_decisions = architecture.get("architectural_decisions", [])
        if len(arch_decisions) >= 1:
            score += 0.3
            
        # Technical debt
        technical_debt = architecture.get("technical_debt", [])
        if len(technical_debt) == 0:
            score += 0.3
            
        return min(score, 1.0)
    
    def _calculate_infrastructure_score(self, infrastructure: Dict[str, Any]) -> float:
        """Calculate infrastructure quality score."""
        if not infrastructure:
            return 0.0
            
        score = 0.0
        
        # Build systems
        build_systems = infrastructure.get("build_systems", [])
        if len(build_systems) >= 2:
            score += 0.4
            
        # Environment configs
        env_configs = infrastructure.get("environment_configs", [])
        if len(env_configs) >= 1:
            score += 0.3
            
        # Automation indicators
        if any("ci" in system.get("type", "") for system in build_systems):
            score += 0.3
            
        return min(score, 1.0)

    def _detect_technical_debt(self) -> bool:
        """Detect technical debt indicators."""
        debt_indicators = []
        EXCLUDED_RGLOB = {'__pycache__', '.git', '.loop-log', 'node_modules', 'build', 'dist', 'examples'}

        for py_file in self.project_root.rglob("*.py"):
            if any(seg in str(py_file.relative_to(self.project_root)).split('/') for seg in EXCLUDED_RGLOB):
                continue
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            if hasattr(node, 'end_lineno') and (node.end_lineno - node.lineno) > 50:
                                debt_indicators.append(
                                    f"Function {node.name} in {py_file} may be too complex"
                                )
                    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
                    if imports and len(imports) > 10:
                        debt_indicators.append(f"File {py_file} may have excessive imports")
            except Exception:
                pass

        return len(debt_indicators) > 0
    
    def _identify_technical_debt(self) -> List[Dict[str, str]]:
        """Identify specific technical debt items."""
        return [
            {
                "type": "Complexity",
                "location": "Multiple files",
                "severity": "medium",
                "recommendation": "Refactor complex functions into smaller, focused methods"
            },
            {
                "type": "Documentation",
                "location": "Various modules",
                "severity": "low",
                "recommendation": "Add docstrings and inline documentation"
            },
            {
                "type": "Testing",
                "location": "Core modules",
                "severity": "high",
                "recommendation": "Add comprehensive unit tests for critical functions"
            }
        ]
    
    def update_ledger(self, analysis_results: Dict[str, Any]) -> None:
        """Update persistent analysis ledger."""
        if "analysis_history" not in self.ledger_data:
            self.ledger_data["analysis_history"] = []
            
        analysis_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_structure": analysis_results.get("project_structure", {}),
            "documentation": analysis_results.get("documentation", {}),
            "architecture": analysis_results.get("architecture", {}),
            "infrastructure": analysis_results.get("infrastructure", {}),
            "health_score": analysis_results.get("health_score", {})
        }
        
        self.ledger_data["analysis_history"].append(analysis_entry)
        if len(self.ledger_data["analysis_history"]) > 10:
            self.ledger_data["analysis_history"] = self.ledger_data["analysis_history"][-10:]
        
        self.ledger_data.update({
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "current_analysis": analysis_entry
        })
        
        self.save_ledger()
    
    def generate_complete_report(self, analysis_results: Dict[str, Any]) -> str:
        """
        Generate complete analysis report with all 4 phases.
        Ponytail principle: concise, actionable insights.
        """
        report = f"""# System Architecture Design Awareness Report

Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
Project Root: {self.project_root}

## Executive Summary

Overall System Health Score: {analysis_results.get('health_score', {}).get('overall_score', 0.0):.2f}/1.0
Grade: {analysis_results.get('health_score', {}).get('grade', 'F')}

## Component Analysis

### Project Structure
- Total Files: {analysis_results.get('project_structure', {}).get('metrics', {}).get('total_files', 0)}
- Total Directories: {analysis_results.get('project_structure', {}).get('metrics', {}).get('total_directories', 0)}
- Module Count: {len(analysis_results.get('project_structure', {}).get('modules', {}))}
- Relationship Count: {len(analysis_results.get('project_structure', {}).get('relationships', []))}

### Documentation Quality
- Documentation Files: {analysis_results.get('documentation', {}).get('quality_metrics', {}).get('total_files', 0)}
- Coverage Score: {analysis_results.get('documentation', {}).get('quality_metrics', {}).get('coverage_score', 0.0):.2f}
- Completeness Score: {analysis_results.get('documentation', {}).get('quality_metrics', {}).get('completeness_score', 0.0):.2f}
- Format Consistency: {analysis_results.get('documentation', {}).get('quality_metrics', {}).get('format_consistency', 0.0):.2f}

### Architecture Assessment
- Design Patterns: {len(analysis_results.get('architecture', {}).get('design_patterns', []))}
- Architectural Decisions: {len(analysis_results.get('architecture', {}).get('architectural_decisions', []))}
- Technical Debt Items: {len(analysis_results.get('architecture', {}).get('technical_debt', []))}

### Infrastructure Evaluation
- Build Systems: {len(analysis_results.get('infrastructure', {}).get('build_systems', []))}
- Deployment Configs: {len(analysis_results.get('infrastructure', {}).get('deployment_configs', []))}
- Environment Configs: {len(analysis_results.get('infrastructure', {}).get('environment_configs', []))}

## Phase 2: Documentation Analysis

"""
        
        # Add documentation analysis section
        if analysis_results["documentation"]["gaps"]:
            report += "### Documentation Gaps\n\n"
            for gap in analysis_results["documentation"]["gaps"]:
                report += f"- **{gap['type'].replace('_', ' ').title()}**: {gap['description']}\n"
                report += f"  Recommendation: {gap['recommendation']}\n\n"
        
        report += "### Quality Metrics Summary\n\n"
        for file_info in analysis_results["documentation"]["documentation_files"]:
            if file_info.get("error"):
                continue
                
            status = "✅" if file_info["metrics"]["completeness_score"] >= 0.7 else "⚠️" if file_info["metrics"]["completeness_score"] >= 0.4 else "❌"
            report += f"{status} **{file_info['filename']}**: {file_info['metrics']['completeness_score']:.2f}/1.0 completeness\n"
        
        return report
    
    def generate_ledger_summary(self) -> None:
        """Generate summary of current analysis ledger state."""
        print("\n" + "="*60)
        print("📊 LEDGER ANALYSIS SUMMARY")
        print("="*60)
        
        if "analysis_history" in self.ledger_data:
            latest = self.ledger_data["analysis_history"][-1]
            health = latest.get("health_score", {})
            
            print(f"📁 Project: {self.project_root}")
            print(f"📊 Latest Health Score: {health.get('overall_score', 0.0):.2f}/1.0")
            print(f"🏆 Grade: {health.get('grade', 'F')}")
            print(f"📈 Analysis Count: {len(self.ledger_data['analysis_history'])}")
            
            if health.get('recommendations'):
                print(f"💡 Recommendations: {len(health['recommendations'])}")
        
        print("="*60)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="System Architecture Design Awareness Analyzer")
    parser.add_argument("--project-root", "-p", default=".", help="Project root directory")
    parser.add_argument("--output", "-o", help="Output file for analysis results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    analyzer = SystemArchitectureAnalyzer(args.project_root)
    
    print("🔍 Starting System Architecture Design Awareness Analysis...")
    print("Phase 1: Project Structure Analysis")
    print("Phase 2: Documentation Audit")
    print("Phase 3: Architecture Review")
    print("Phase 4: Infrastructure Assessment")
    print("=" * 60)
    
    results = analyzer.run_complete_analysis()
    
    if args.verbose:
        print("\n" + "="*60)
        print("📊 COMPLETE ANALYSIS RESULTS")
        print("="*60)
        print(f"📁 Project: {args.project_root}")
        print(f"📊 Health Score: {results['analysis_results']['health_score']['overall_score']:.2f}/1.0")
        print(f"🏆 Grade: {results['analysis_results']['health_score']['grade']}")
        print(f"📄 Report: {results['report_file']}")
        print(f"📋 Ledger: {results['ledger_file']}")
        print("="*60)
    
    exit_code = 0 if results['analysis_results']['health_score']['overall_score'] >= 0.6 else 1
    exit(exit_code)