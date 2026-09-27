#!/usr/bin/env python3
"""
Project Structure Analyzer
Automated scanning and complexity assessment for team initialization.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

class ProjectStructureAnalyzer:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.scan_results = {}

    def scan_project(self) -> Dict:
        """Perform comprehensive project structure scan"""
        scan_result = {
            "scan_timestamp": datetime.now().isoformat(),
            "project_path": str(self.project_root),
            "directories": [],
            "files": [],
            "file_types": {},
            "total_files": 0,
            "total_directories": 0,
            "complexity_score": 0,
            "patterns_detected": [],
            "recommendations": []
        }

        # Scan directory structure
        for root, dirs, files in os.walk(self.project_root):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            # Record directory
            rel_dir = os.path.relpath(root, self.project_root)
            if rel_dir != '.':
                scan_result["directories"].append(rel_dir)
                scan_result["total_directories"] += 1

            # Record files
            for file in files:
                if file.startswith('.'):
                    continue

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.project_root)

                # Get file extension
                if '.' in file:
                    ext = file.split('.')[-1]
                    scan_result["file_types"][ext] = scan_result["file_types"].get(ext, 0) + 1

                scan_result["files"].append(rel_path)
                scan_result["total_files"] += 1

        # Calculate complexity score
        scan_result["complexity_score"] = self._calculate_complexity(scan_result)

        # Detect patterns
        scan_result["patterns_detected"] = self._detect_patterns(scan_result)

        # Generate recommendations
        scan_result["recommendations"] = self._generate_recommendations(scan_result)

        self.scan_results = scan_result
        return scan_result

    def _calculate_complexity(self, scan_result: Dict) -> float:
        """Calculate project complexity score"""
        score = 0.0

        # Base score from file count
        score += min(scan_result["total_files"] / 100, 5.0)

        # Directory complexity
        score += min(scan_result["total_directories"] / 20, 3.0)

        # File type diversity
        score += len(scan_result["file_types"]) * 0.5

        return round(score, 2)

    def _detect_patterns(self, scan_result: Dict) -> List[str]:
        """Detect architectural patterns"""
        patterns = []

        # Check for common patterns
        file_paths = [f.lower() for f in scan_result["files"]]

        if any('ai' in f or 'llm' in f or 'model' in f for f in file_paths):
            patterns.append('ai_system')

        if any('browser' in f or 'playwright' in f for f in file_paths):
            patterns.append('browser_automation')

        if any('database' in f or 'sql' in f or 'postgres' in f for f in file_paths):
            patterns.append('database_system')

        if any('security' in f or 'auth' in f for f in file_paths):
            patterns.append('security_focused')

        if any('pipeline' in f or 'spec' in f for f in file_paths):
            patterns.append('pipeline_system')

        return patterns

    def _generate_recommendations(self, scan_result: Dict) -> List[str]:
        """Generate team recommendations based on scan"""
        recommendations = []

        complexity = scan_result.get("complexity_score", 0)
        if complexity > 5.0:
            recommendations.append("Consider architectural review - high complexity")
            recommendations.append("Add middleware layer for better organization")

        source_files = [f for f in scan_result["files"] if f.endswith('.py')]
        if len(source_files) > 10:
            recommendations.append("Add junior developer - code coverage needed")

        file_types = list(scan_result["file_types"].keys())
        if 'md' not in file_types:
            recommendations.append("Establish documentation standards")

        patterns = scan_result.get("patterns_detected", [])
        if "pipeline_system" in patterns:
            recommendations.append("Implement CI/CD pipeline for automated testing")

        return recommendations

    def get_scan_summary(self) -> Dict:
        """Get a summary of the scan results"""
        if not self.scan_results:
            return {"error": "No scan results available"}

        return {
            "file_count": self.scan_results.get("total_files", 0),
            "directory_count": self.scan_results.get("total_directories", 0),
            "complexity_score": self.scan_results.get("complexity_score", 0),
            "pattern_count": len(self.scan_results.get("patterns_detected", [])),
            "recommendation_count": len(self.scan_results.get("recommendations", []))
        }

if __name__ == "__main__":
    analyzer = ProjectStructureAnalyzer()
    result = analyzer.scan_project()
    print(json.dumps(result, indent=2))