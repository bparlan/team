#!/usr/bin/env python3
"""
Project File Analysis and Scanning System for theteam Enhancement

This module analyzes project files and characteristics to determine optimal
t behavioral team composition.
"""

import os
import json
import ast
import re
import fnmatch
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

# File type classifications
CODE_FILES = {
    "Python": {".py", ".pyi", ".pyx", ".pxd"},
    "JavaScript/TypeScript": {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"},
    "Java": {".java", ".jar"},
    "C/C++": {".c", ".cpp", ".cc", ".cxx", ".hpp", ".h", ".hxx"},
    "Go": {".go"},
    "Rust": {".rs"},
    "PHP": {".php"},
    "Ruby": {".rb"},
    "Swift": {".swift"},
    "Kotlin": {".kt", ".kts"}
}

DOCUMENTATION_FILES = {
    ".md", ".rst", ".txt", ".md.txt", ".readme", "README.md", "readme.md"
}

CONFIG_FILES = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".xml"
}

TEST_FILES = {
    "test_*", "*_test", "__tests__", "*_spec", "test_*.py", "*_test.py"
}
class ProjectAnalyzer:
    """
    Analyzes project structure and files to determine characteristics
    that inform optimal team behavioral composition.
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.analysis_results = {}
        self.file_analysis = {}
        self.dependencies = {}
        self.complexity_metrics = {}

    def analyze_project(self) -> Dict[str, Any]:
        """
        Perform comprehensive project analysis.

        Returns:
            Dict containing all project characteristics and metrics.
        """
        self.analysis_results = {
            "project_type": self._detect_project_type(),
            "code_complexity": self._analyze_code_complexity(),
            "documentation_needs": self._analyze_documentation_requirements(),
            "testing_requirements": self._analyze_testing_requirements(),
            "team_collaboration_patterns": self._analyze_collaboration_patterns(),
            "behavioral_recommendations": self._generate_behavioral_recommendations(),
            "risk_assessment": self._assess_project_risks(),
            "dependency_analysis": self._analyze_dependencies(),
            "file_organization": self._analyze_file_organization(),
            "technology_stack": self._identify_technology_stack(),
            "project_metrics": self._calculate_project_metrics()
        }

        return self.analysis_results

    def _detect_project_type(self) -> str:
        """
        Detect the primary type of project based on files and structure.
        """
        indicators = {
            "web_application": 0,
            "library": 0,
            "cli_tool": 0,
            "data_science": 0,
            "mobile_app": 0,
            "enterprise": 0,
            "research": 0,
            "devops": 0
        }

        for file_path in self.project_root.rglob("*"):
            if file_path.is_file():
                name = file_path.name.lower()

                # Web application indicators
                if any(indicator in name for indicator in ["app.py", "flask", "django", "fastapi"]):
                    indicators["web_application"] += 1
                elif any(indicator in name for indicator in ["package.json", "requirements.txt"]):
                    indicators["web_application"] += 1

                # Library indicators
                elif name.endswith(".py") and "__init__.py" in str(file_path):
                    indicators["library"] += 1
                elif any(indicator in name for indicator in ["setup.py", "pyproject.toml", "setup.cfg"]):
                    indicators["library"] += 1

                # CLI tool indicators
                elif any(indicator in name for indicator in ["main.py", "cli", "command"]):
                    indicators["cli_tool"] += 1

                # Data science indicators
                elif any(indicator in name for indicator in ["notebook", "jupyter", "ml", "ai", "model"]):
                    indicators["data_science"] += 1

                # Enterprise indicators
                elif any(indicator in name for indicator in ["config", "settings", "production"]):
                    indicators["enterprise"] += 1

                # DevOps indicators
                elif any(indicator in name for indicator in [".dockerfile", "docker-compose", "ansible", "terraform"]):
                    indicators["devops"] += 1

        # Return primary project type
        primary_type = max(indicators, key=indicators.get)
        confidence = indicators[primary_type] / sum(indicators.values())

        return {
            "type": primary_type,
            "confidence": confidence,
            "indicators": indicators
        }

    def _analyze_code_complexity(self) -> Dict[str, Any]:
        """
        Analyze code complexity and structure.
        """
        complexity_metrics = {
            "total_files": 0,
            "code_files": 0,
            "documentation_files": 0,
            "config_files": 0,
            "test_files": 0,
            "max_nesting_depth": 0,
            "average_nesting_depth": 0,
            "total_lines": 0,
            "average_file_size": 0,
            "import_complexity": 0,
            "structural_complexity": 0
        }

        file_sizes = []
        nesting_depths = []
        total_imports = 0
        structural_scores = []

        for file_path in self.project_root.rglob("*"):
            if file_path.is_file() and not self._should_ignore_file(file_path):
                complexity_metrics["total_files"] += 1
                file_size = file_path.stat().st_size
                file_sizes.append(file_size)

                # Classify file type. Each file lands in exactly one bucket so the
                # buckets partition total_files. Tests are matched first because a
                # .py test also matches _is_code_file, which made the test_files
                # branch unreachable when it came last.
                #
                # Complexity metrics still include test files: they are source
                # code, and excluding them would shift structural_complexity —
                # which gates role selection and risk tolerance — purely as a side
                # effect of fixing the counts.
                is_test = self._is_test_file(file_path)
                is_code = self._is_code_file(file_path)

                if is_test:
                    complexity_metrics["test_files"] += 1
                elif is_code:
                    complexity_metrics["code_files"] += 1
                elif self._is_documentation_file(file_path):
                    complexity_metrics["documentation_files"] += 1
                elif self._is_config_file(file_path):
                    complexity_metrics["config_files"] += 1

                if is_code:
                    nesting_depth, file_imports, struct_score = self._calculate_file_complexity(file_path)
                    nesting_depths.append(nesting_depth)
                    total_imports += file_imports
                    structural_scores.append(struct_score)

        # Calculate metrics
        if file_sizes:
            complexity_metrics["average_file_size"] = sum(file_sizes) / len(file_sizes)
            complexity_metrics["max_file_size"] = max(file_sizes)

        if nesting_depths:
            complexity_metrics["max_nesting_depth"] = max(nesting_depths)
            complexity_metrics["average_nesting_depth"] = sum(nesting_depths) / len(nesting_depths)

        if structural_scores:
            complexity_metrics["structural_complexity"] = sum(structural_scores) / len(structural_scores)

        # Denominator must match the population that contributed imports: every
        # file with is_code True, which includes test files. Using code_files
        # alone would inflate this once tests stopped being counted as code.
        code_population = len(structural_scores)
        complexity_metrics["import_complexity"] = (
            total_imports / code_population if code_population > 0 else 0
        )

        return complexity_metrics

    def _calculate_file_complexity(self, file_path: Path) -> Tuple[int, int, float]:
        """
        Calculate complexity metrics for a single file.
        """
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')

            # Calculate nesting depth (simplified)
            max_depth = 0
            current_depth = 0
            for line in content.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue

                # Count indentation
                indent = len(line) - len(line.lstrip())
                current_depth = indent // 4  # Assuming 4-space indentation
                max_depth = max(max_depth, current_depth)

            # Count imports
            import_count = len(re.findall(r'^\s*(import|from)\s+\w+', content, re.MULTILINE))

            # Calculate structural complexity score (simplified)
            # Based on function definitions, classes, conditionals, loops
            function_count = len(re.findall(r'^\s*def\s+\w+', content, re.MULTILINE))
            class_count = len(re.findall(r'^\s*class\s+\w+', content, re.MULTILINE))
            conditional_count = len(re.findall(r'^\s*(if|elif|else)\s+', content, re.MULTILINE))
            loop_count = len(re.findall(r'^\s*(for|while)\s+', content, re.MULTILINE))

            structural_score = (function_count * 2 + class_count * 3 +
                              conditional_count * 1 + loop_count * 1) / max(len(content.splitlines()), 1)

            return max_depth, import_count, structural_score

        except Exception:
            return 0, 0, 0.0

    def _analyze_documentation_requirements(self) -> Dict[str, Any]:
        """
        Analyze documentation needs based on project characteristics.
        """
        doc_patterns = {
            "technical_documentation": 0,
            "api_documentation": 0,
            "user_guide": 0,
            "architecture_diagrams": 0,
            "deployment_guides": 0,
            "development_guides": 0
        }

        for file_path in self.project_root.rglob("*"):
            if file_path.is_file():
                name = file_path.name.lower()

                if any(indicator in name for indicator in ["api", "swagger", "openapi"]):
                    doc_patterns["api_documentation"] += 1
                elif any(indicator in name for indicator in ["guide", "manual", "howto"]):
                    doc_patterns["user_guide"] += 1
                elif any(indicator in name for indicator in ["diagram", "architecture", "design"]):
                    doc_patterns["architecture_diagrams"] += 1
                elif any(indicator in name for indicator in ["deploy", "install", "setup"]):
                    doc_patterns["deployment_guides"] += 1
                elif any(indicator in name for indicator in ["dev", "development", "contributing"]):
                    doc_patterns["development_guides"] += 1
                elif doc_patterns["technical_documentation"] < 3:  # Count markdown files as fallback
                    doc_patterns["technical_documentation"] += 1

        # Determine documentation density
        total_files = max(1, sum(doc_patterns.values()))
        documentation_density = (sum(doc_patterns.values()) - doc_patterns["technical_documentation"]) / total_files

        return {
            "patterns": doc_patterns,
            "density": documentation_density,
            "needs_enhanced_documentation": documentation_density > 0.3,
            "recommended_documentation_focus": self._determine_documentation_focus(doc_patterns)
        }

    def _analyze_testing_requirements(self) -> Dict[str, Any]:
        """
        Analyze testing requirements and patterns.
        """
        test_metrics = {
            "test_coverage": 0.0,
            "test_types": {
                "unit_tests": 0,
                "integration_tests": 0,
                "e2e_tests": 0,
                "performance_tests": 0,
                "security_tests": 0
            },
            "testing_approach": "manual",  # manual, automated, mixed
            "testing_frameworks": [],
            "quality_assurance_level": "basic"  # basic, intermediate, advanced
        }

        # Detect testing frameworks
        for file_path in self.project_root.rglob("*"):
            if file_path.is_file():
                name = file_path.name.lower()

                if any(indicator in name for indicator in ["pytest", "unittest", "test_"]):
                    test_metrics["testing_frameworks"].append("Python testing")
                    test_metrics["test_types"]["unit_tests"] += 1
                elif any(indicator in name for indicator in ["selenium", "playwright", "cypress"]):
                    test_metrics["testing_frameworks"].append("E2E testing")
                    test_metrics["test_types"]["e2e_tests"] += 1
                elif any(indicator in name for indicator in ["coverage", "pytest-cov"]):
                    test_metrics["testing_frameworks"].append("Test coverage")

        # Determine testing approach
        if any("test_" in str(f).lower() for f in self.project_root.rglob("*")):
            test_metrics["testing_approach"] = "automated"
        elif any("test" in str(f).lower() for f in self.project_root.rglob("*")):
            test_metrics["testing_approach"] = "mixed"

        # Calculate quality assurance level
        if len(test_metrics["testing_frameworks"]) > 2:
            test_metrics["quality_assurance_level"] = "advanced"
        elif len(test_metrics["testing_frameworks"]) > 0:
            test_metrics["quality_assurance_level"] = "intermediate"

        return test_metrics

    def _analyze_collaboration_patterns(self) -> Dict[str, Any]:
        """
        Analyze existing collaboration patterns and team dynamics.
        """
        patterns = {
            "code_review_patterns": [],
            "documentation_contribution": [],
            "testing_participation": [],
            "communication_channels": [],
            "decision_making_style": "collaborative",  # collaborative, hierarchical, decentralized
            "conflict_resolution_approach": "avoidant"  # avoidant, diplomatic, direct
        }

        # Analyze code review patterns from git history or existing config
        for file_path in self.project_root.rglob("*"):
            if file_path.is_file():
                name = file_path.name.lower()

                if any(indicator in name for indicator in ["review", "pr", "pull", "merge"]):
                    patterns["code_review_patterns"].append(str(file_path))

        # Analyze documentation patterns
        for file_path in self.project_root.glob("*.md"):
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            if "contributing" in content.lower() or "code of conduct" in content.lower():
                patterns["documentation_contribution"].append(str(file_path))

        # Analyze testing patterns
        for file_path in self.project_root.rglob("*test*"):
            if file_path.is_file():
                patterns["testing_participation"].append(str(file_path))

        return patterns

    def _generate_behavioral_recommendations(self) -> Dict[str, Any]:
        """
        Generate behavioral team composition recommendations based on analysis.
        """
        recommendations = {
            "recommended_team_size": 3,
            "recommended_roles": [],
            "behavioral_priorities": [],
            "skill_gaps": [],
            "collaboration_focus": []
        }

        complexity = self.analysis_results.get("code_complexity", {})
        doc_needs = self.analysis_results.get("documentation_needs", {})
        testing = self.analysis_results.get("testing_requirements", {})

        # Determine recommended roles based on complexity
        if complexity.get("structural_complexity", 0) > 0.5:
            recommendations["recommended_roles"].extend(["technical_architect", "adversarial_reviewer"])
        else:
            recommendations["recommended_roles"].append("delivery_pragmatist")

        # Documentation needs
        if doc_needs.get("needs_enhanced_documentation", False):
            recommendations["behavioral_priorities"].append("methodical_communication")
            recommendations["recommended_roles"].append("technical_architect")

        # Testing requirements
        if testing.get("quality_assurance_level") == "advanced":
            recommendations["behavioral_priorities"].append("analytical_thinking")
            recommendations["recommended_roles"].append("adversarial_reviewer")

        # Ensure we have the right number of roles
        if len(recommendations["recommended_roles"]) > 3:
            recommendations["recommended_roles"] = recommendations["recommended_roles"][:3]

        return recommendations

    def _assess_project_risks(self) -> Dict[str, Any]:
        """
        Assess project risks that inform team composition.
        """
        risks = {
            "technical_risks": [],
            "business_risks": [],
            "compliance_risks": [],
            "operational_risks": []
        }

        complexity = self.analysis_results.get("code_complexity", {})

        if complexity.get("average_nesting_depth", 0) > 10:
            risks["technical_risks"].append("High code complexity - need analytical expertise")

        if complexity.get("structural_complexity", 0) > 0.7:
            risks["technical_risks"].append("Complex architecture - need technical leadership")

        if not self.analysis_results.get("documentation_needs", {}).get("needs_enhanced_documentation", False):
            risks["business_risks"].append("Limited documentation - need methodical communication")

        return risks

    def _analyze_dependencies(self) -> Dict[str, Any]:
        """
        Analyze project dependencies and requirements.
        """
        dependencies = {
            "external_dependencies": [],
            "internal_dependencies": [],
            "integration_requirements": [],
            "performance_requirements": []
        }

        # Analyze package files
        for dep_file in self.project_root.glob("requirements.txt"):
            dependencies["external_dependencies"].extend(
                dep_file.read_text().splitlines()
            )

        for dep_file in self.project_root.glob("package.json"):
            try:
                import json
                deps = json.loads(dep_file.read_text())
                dependencies["external_dependencies"].extend(
                    list(deps.get("dependencies", {}).keys()) +
                    list(deps.get("devDependencies", {}).keys())
                )
            except Exception:
                pass

        return dependencies

    def _analyze_file_organization(self) -> Dict[str, Any]:
        """
        Analyze file organization and structure.
        """
        org_analysis = {
            "directory_depth": 0,
            "main_module_exists": False,
            "src_structure": "",
            "separation_of_concerns": 0.0,
            "organization_score": 0.0
        }

        # Analyze directory structure
        max_depth = 0
        for file_path in self.project_root.rglob("*"):
            if file_path.is_file():
                depth = len(file_path.relative_to(self.project_root).parts)
                max_depth = max(max_depth, depth)

        org_analysis["directory_depth"] = max_depth

        # Check for main entry point
        main_indicators = ["__main__.py", "main.py", "app.py", "cli.py"]
        for indicator in main_indicators:
            if (self.project_root / indicator).exists():
                org_analysis["main_module_exists"] = True
                break

        # Analyze source structure. iterdir() order is arbitrary, so take the
        # first *recognised* source directory by preference order rather than
        # src_dirs[0] — otherwise a project with src/ and tests/ reports tests/.
        skip = {"__pycache__", ".git", "node_modules", ".venv", "venv",
                "tests", "test", "__tests__", "docs", "build", "dist"}
        dirs = [d for d in self.project_root.iterdir()
                if d.is_dir() and not d.name.startswith(".") and d.name not in skip]
        preferred = [d for d in ("src", "lib", "app", "source") if (self.project_root / d).is_dir()]
        if preferred:
            org_analysis["src_structure"] = preferred[0]
        elif dirs:
            org_analysis["src_structure"] = dirs[0].name

        return org_analysis

    def _identify_technology_stack(self) -> Dict[str, Any]:
        """
        Identify technology stack from project files.
        """
        stack = {
            "primary_languages": [],
            "frameworks": [],
            "databases": [],
            "deployment_platforms": [],
            "build_tools": []
        }

        # Analyze common configuration files
        for config_file in self.project_root.glob("pyproject.toml"):
            stack["primary_languages"].append("Python")
            stack["build_tools"].append("Poetry")

        for config_file in self.project_root.glob("package.json"):
            stack["primary_languages"].append("JavaScript/TypeScript")
            stack["build_tools"].append("npm/yarn")

        for config_file in self.project_root.glob("setup.py"):
            stack["primary_languages"].append("Python")
            stack["build_tools"].append("setuptools")

        return stack

    def _calculate_project_metrics(self) -> Dict[str, Any]:
        """
        Calculate overall project metrics.
        """
        metrics = {
            "total_lines_of_code": 0,
            "file_count": 0,
            "documentation_ratio": 0.0,
            "test_coverage_ratio": 0.0,
            "maintainability_score": 0.0,
            "complexity_score": 0.0
        }

        total_loc = 0
        total_files = 0
        doc_files = 0
        test_files = 0

        for file_path in self.project_root.rglob("*"):
            if file_path.is_file() and not self._should_ignore_file(file_path):
                total_files += 1
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    total_loc += len(content.splitlines())

                    if self._is_documentation_file(file_path):
                        doc_files += 1
                    elif self._is_test_file(file_path):
                        test_files += 1
                except Exception:
                    pass

        metrics["total_lines_of_code"] = total_loc
        metrics["file_count"] = total_files
        metrics["documentation_ratio"] = doc_files / max(total_files, 1)
        metrics["test_coverage_ratio"] = test_files / max(total_files, 1)

        # Calculate maintainability (simplified)
        if total_files > 0:
            metrics["maintainability_score"] = (1 - metrics["documentation_ratio"] *
                                             0.3 - metrics["test_coverage_ratio"] * 0.2)

        # Calculate complexity (simplified)
        complexity = self.analysis_results.get("code_complexity", {})
        metrics["complexity_score"] = (complexity.get("max_nesting_depth", 0) * 0.3 +
                                       complexity.get("structural_complexity", 0) * 0.7)

        return metrics

    def _should_ignore_file(self, file_path: Path) -> bool:
        """
        Determine if a file should be ignored in analysis.
        """
        ignore_patterns = {
            "__pycache__", ".git", ".hg", ".svn", ".gitignore",
            "node_modules", ".env", "env.py", "requirements.txt",
            "poetry.lock", "Pipfile.lock", ".DS_Store", "Thumbs.db"
        }

        for part in file_path.parts:
            if part in ignore_patterns:
                return True

        return False

    def _is_code_file(self, file_path: Path) -> bool:
        """
        Check if a file is a code file.
        """
        suffix = file_path.suffix.lower()
        name = file_path.name.lower()

        for language, extensions in CODE_FILES.items():
            if suffix in extensions:
                return True

        # Additional checks for specific files
        if name.startswith("test_") and suffix == ".py":
            return False
        if "test" in name and suffix == ".py":
            return False

        return False

    def _is_documentation_file(self, file_path: Path) -> bool:
        """
        Check if a file is a documentation file.
        """
        suffix = file_path.suffix.lower()
        name = file_path.name.lower()

        if suffix in DOCUMENTATION_FILES:
            return True

        # Additional documentation patterns
        if name.startswith("readme") or "documentation" in name:
            return True

        return False

    def _is_config_file(self, file_path: Path) -> bool:
        """
        Check if a file is a configuration file.
        """
        suffix = file_path.suffix.lower()
        name = file_path.name.lower()

        if suffix in CONFIG_FILES:
            return True

        # Additional config patterns
        if any(indicator in name for indicator in ["config", "settings", "env", "env."]):
            return True

        return False

    def _is_test_file(self, file_path: Path) -> bool:
        """
        Check if a file is a test file.

        TEST_FILES holds glob patterns, so they must be matched with fnmatch —
        a literal substring check never matches "test_*" against a real name.
        ponytail: a test file inside a __tests__/ or tests/ directory counts even
        when the filename itself is unremarkable (e.g. conftest.py).
        """
        name = file_path.name.lower()

        if any(fnmatch.fnmatch(name, pattern) for pattern in TEST_FILES):
            return True

        # JS/TS convention: infix dots — mod.spec.ts, mod.test.js
        if any(fnmatch.fnmatch(name, pattern) for pattern in ("*.spec.*", "*.test.*")):
            return True

        parent = file_path.parent.name.lower()
        return parent in ("tests", "test", "__tests__")

    def _determine_documentation_focus(self, doc_patterns: Dict[str, int]) -> List[str]:
        """
        Determine the focus areas for documentation enhancement.
        """
        focus_areas = []

        if doc_patterns.get("api_documentation", 0) > 0:
            focus_areas.append("API documentation")

        if doc_patterns.get("user_guide", 0) > 0:
            focus_areas.append("User guides")

        if doc_patterns.get("architecture_diagrams", 0) > 0:
            focus_areas.append("Architecture diagrams")

        if doc_patterns.get("deployment_guides", 0) > 0:
            focus_areas.append("Deployment guides")

        return focus_areas

    def get_team_recommendations(self) -> Dict[str, Any]:
        """
        Get behavioral team composition recommendations.
        """
        analysis = self.analysis_results

        # Analyze characteristics to determine optimal team composition
        complexity = analysis.get("code_complexity", {})
        doc_needs = analysis.get("documentation_needs", {})
        testing = analysis.get("testing_requirements", {})
        recommendations = analysis.get("behavioral_recommendations", {})

        # Determine required behavioral traits based on project characteristics
        required_traits = set()

        if complexity.get("structural_complexity", 0) > 0.5:
            required_traits.update(["analytical", "methodical"])

        if doc_needs.get("needs_enhanced_documentation", False):
            required_traits.update(["methodical", "technical"])

        if testing.get("quality_assurance_level") == "advanced":
            required_traits.add("analytical")

        # Generate behavioral compatibility requirements
        compatibility_requirements = {
            "diversity_needed": len(required_traits) > 1,
            "communication_style": "methodical" if complexity.get("structural_complexity", 0) > 0.5 else "quick",
            "decision_making_approach": "analytical" if testing.get("quality_assurance_level") == "advanced" else "autonomous",
            "risk_tolerance": "moderate" if complexity.get("structural_complexity", 0) > 0.5 else "aggressive"
        }

        return {
            "project_analysis": analysis,
            "recommended_traits": list(required_traits),
            "compatibility_requirements": compatibility_requirements,
            "team_size_recommendation": recommendations.get("recommended_team_size", 3),
            "behavioral_priorities": recommendations.get("behavioral_priorities", []),
            "skill_gaps": recommendations.get("skill_gaps", []),
            "collaboration_focus": recommendations.get("collaboration_focus", [])
        }

    def save_analysis(self, output_path: str = "project_analysis.json"):
        """
        Save analysis results to a file.
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.analysis_results, f, indent=2, default=str)

    def __str__(self):
        return f"ProjectAnalyzer(project_root='{self.project_root}')"