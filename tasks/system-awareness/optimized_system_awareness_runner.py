#!/usr/bin/env python3
"""
Optimized System Architecture Design Awareness Runner

Lightweight runner for system architecture analysis that integrates 
seamlessly with the existing task loop system. Removes HITL and team
discussion complexity while maintaining all core analysis capabilities.

Ponytail principles applied:
- Minimal complexity, maximal effectiveness
- Modular composition, readability first
- Standard library only
"""

import os
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

class OptimizedSystemAwarenessRunner:
    """
    Optimized task runner for system architecture design awareness.
    
    Lightweight alternative to the original runner that focuses on
    core analysis while removing unnecessary complexity for main loop integration.
    """

    def __init__(self, project_root: str, config_path: Optional[str] = None):
        self.project_root = Path(project_root).resolve()
        self.config_path = config_path or str(self.project_root / "system-awareness-config.json")
        
        # Paths based on task requirements
        self.tasks_dir = self.project_root / "tasks"
        self.reports_dir = self.project_root / "theteam" / "reports"
        self.ledger_file = self.tasks_dir / "system-awareness-ledger.json"
        self.config_file = Path(self.config_path)
        
        # Ensure directories exist
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

        # Ledger rotation threshold (deterministic size cap, existing infra)
        self._ledger_max_bytes = 2 * 1024 * 1024  # 2 MB

        # Load configuration
        self.config = self._load_config()

        # Initialize ledger if needed
        self.ledger = self._initialize_ledger()

    def _load_config(self) -> Dict[str, Any]:
        """Load task configuration."""
        default_config = {
            "project_root": str(self.project_root),
            "output_paths": {
                "ledger": str(self.ledger_file),
                "reports": str(self.reports_dir),
                "health_score": str(self.tasks_dir / "system-health-score.json"),
                "architecture_report": str(self.tasks_dir / "architecture-analysis.md"),
                "documentation_report": str(self.tasks_dir / "documentation-audit-report.md"),
                "infrastructure_report": str(self.tasks_dir / "infrastructure-assessment.md"),
                "optimization_recommendations": str(self.tasks_dir / "optimization-recommendations.md")
            },
            "phases": [
                {
                    "id": "structure_analysis",
                    "name": "Project Structure Analysis",
                    "required": True,
                    "description": "Analyze project structure, modules, dependencies, and complexity"
                },
                {
                    "id": "documentation_audit", 
                    "name": "Documentation Audit",
                    "required": True,
                    "description": "Evaluate documentation completeness and quality"
                },
                {
                    "id": "architecture_review",
                    "name": "Architecture Review", 
                    "required": True,
                    "description": "Review design patterns and architectural decisions"
                },
                {
                    "id": "infrastructure_assessment",
                    "name": "Infrastructure Assessment",
                    "required": True,
                    "description": "Assess build systems and infrastructure configuration"
                }
            ],
            "hitl_settings": {
                "phase_review_required": False,  # DISABLED for main loop integration
                "team_discussion_trigger": False,  # DISABLED for main loop integration
                "optimization_recommendations": True,
                "continuity_checkpoint": True
            },
            "team_discussion": {
                "enabled": False,  # DISABLED for main loop integration
                "topic": "System Architecture Analysis Results",
                "required_for_completion": False
            }
        }
        
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults, preserving user customizations
                    return {**default_config, **config}
            else:
                # Create default config if it doesn't exist
                with open(self.config_file, 'w') as f:
                    json.dump(default_config, f, indent=2)
                return default_config
        except Exception as e:
            print(f"Warning: Could not load config, using defaults: {e}")
            return default_config

    def _initialize_ledger(self) -> Dict[str, Any]:
        """Initialize or load the analysis ledger."""
        if self.ledger_file.exists():
            try:
                with open(self.ledger_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # Initialize fresh ledger
        return {
            "project": str(self.project_root),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "analysis_history": [],
            "phase_progress": {},
            "team_discussions": [],
            "user_interactions": []
        }

    def _save_ledger(self) -> None:
        """Save ledger state to disk with size-based rotation."""
        try:
            # Rotate ledger if it exceeds the size threshold (existing infra)
            if self.ledger_file.exists() and self.ledger_file.stat().st_size > self._ledger_max_bytes:
                self._rotate_ledger()

            with open(self.ledger_file, 'w') as f:
                json.dump(self.ledger, f, indent=2)
        except Exception as e:
            print(f"Error saving ledger: {e}")

    def _rotate_ledger(self) -> None:
        """Archive an oversized ledger before rewriting (deterministic)."""
        from datetime import datetime
        archive_dir = self.ledger_file.parent / "archives"
        archive_dir.mkdir(exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_path = archive_dir / f"ledger_{timestamp}.json"
        try:
            import shutil
            shutil.move(str(self.ledger_file), str(archive_path))
        except Exception as e:
            print(f"Warning: Could not archive ledger: {e}")

    def run_optimized_analysis(self) -> Dict[str, Any]:
        """
        Run the complete system awareness analysis without HITL or team discussions.
        
        Designed for main loop integration - fast, focused execution.
        """
        print(f"{'='*60}")
        print(f"🚀 RUNNING OPTIMIZED SYSTEM AWARENESS ANALYSIS")
        print(f"{'='*60}")
        
        try:
            from analyze_system_awareness import SystemArchitectureAnalyzer
            analyzer = SystemArchitectureAnalyzer(str(self.project_root))
            
            # Run all 4 phases in sequence
            results = analyzer.run_complete_analysis()
            
            # Update ledger with results
            self._update_ledger_from_results(results)
            
            # Generate all output files
            generated_files = self._generate_all_outputs(results['analysis_results'])
            
            return {
                "success": True,
                "analysis_results": results['analysis_results'],
                "generated_files": generated_files,
                "ledger_updated": True,
                "team_discussion_available": False
            }
            
        except Exception as e:
            print(f"❌ Error in optimized analysis: {e}")
            return {"error": str(e), "success": False}

    def _update_ledger_from_results(self, results: Dict[str, Any]) -> None:
        """Update ledger with analysis results."""
        if "analysis_results" not in self.ledger:
            self.ledger["analysis_results"] = {}
        
        self.ledger["analysis_results"] = results['analysis_results']
        self.ledger["generated_files"] = []
        
        # Update phase progress
        for phase_name in ["structure_analysis", "documentation_audit", 
                          "architecture_review", "infrastructure_assessment"]:
            self.ledger["phase_progress"][phase_name] = {
                "completed": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "completed"
            }
        
        self._save_ledger()

    def _generate_all_outputs(self, analysis_results: Dict[str, Any]) -> List[str]:
        """Generate all required output files."""
        generated_files = []
        
        # Generate comprehensive report
        report_file = self.reports_dir / f"system-architecture-analysis-{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
        try:
            from analyze_system_awareness import SystemArchitectureAnalyzer
            analyzer = SystemArchitectureAnalyzer(str(self.project_root))
            full_results = analyzer.run_complete_analysis()
            
            with open(report_file, 'w') as f:
                f.write(f"# System Architecture Design Awareness Report\n\n")
                f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
                f.write(f"## Analysis Summary\n\n")
                f.write(f"Project: {self.project_root}\n")
                f.write(f"Health Score: {full_results['analysis_results']['health_score']['overall_score']:.2f}/1.0\n")
                f.write(f"Grade: {full_results['analysis_results']['health_score']['grade']}\n\n")
                
                # Add detailed analysis
                f.write(f"## Phase 1: Project Structure Analysis\n")
                f.write(f"- Files Analyzed: {full_results['analysis_results']['project_structure']['metrics']['total_files']}\n")
                f.write(f"- Directories: {full_results['analysis_results']['project_structure']['metrics']['total_directories']}\n\n")
                
                f.write(f"## Phase 2: Documentation Audit\n")
                doc_quality = full_results['analysis_results']['documentation']['quality_metrics']
                f.write(f"- Coverage Score: {doc_quality.get('coverage_score', 0.0):.2f}\n")
                f.write(f"- Completeness Score: {doc_quality.get('completeness_score', 0.0):.2f}\n\n")
                
                f.write(f"## Phase 3: Architecture Review\n")
                f.write(f"- Design Patterns: {len(full_results['analysis_results']['architecture']['design_patterns'])}\n")
                f.write(f"- Technical Debt Items: {len(full_results['analysis_results']['architecture']['technical_debt'])}\n\n")
                
                f.write(f"## Phase 4: Infrastructure Assessment\n")
                infra = full_results['analysis_results']['infrastructure']
                f.write(f"- Build Systems: {len(infra.get('build_systems', []))}\n")
                f.write(f"- Deployment Configs: {len(infra.get('deployment_configs', []))}\n")
                
                f.write(f"\n## Recommendations\n\n")
                recommendations = full_results['analysis_results']['health_score'].get('recommendations', [])
                for i, rec in enumerate(recommendations[:5], 1):
                    f.write(f"{i}. {rec}\n")
            
            generated_files.append(str(report_file))
            
        except Exception as e:
            print(f"   ❌ Error generating comprehensive report: {e}")
        
        # Generate system health score
        health_score_file = Path(self.config['output_paths']['health_score'])
        try:
            with open(health_score_file, 'w') as f:
                health_data = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "project": str(self.project_root),
                    "health_score": analysis_results.get('health_score', {}),
                    "generated_by": "optimized-system-awareness-runner",
                    "version": "1.0.0"
                }
                json.dump(health_data, f, indent=2)
            generated_files.append(str(health_score_file))
            
        except Exception as e:
            print(f"   ❌ Error generating health score: {e}")
        
        # Generate architecture analysis
        arch_file = Path(self.config['output_paths']['architecture_report'])
        try:
            with open(arch_file, 'w') as f:
                f.write("# Architecture Analysis Report\n\n")
                f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
                f.write(f"## Design Pattern Analysis\n")
                for pattern in analysis_results.get('architecture', {}).get('design_patterns', []):
                    f.write(f"- {pattern}\n")
                f.write(f"\n## Architectural Decisions\n")
                for decision in analysis_results.get('architecture', {}).get('architectural_decisions', []):
                    f.write(f"- {decision}\n")
            generated_files.append(str(arch_file))
            
        except Exception as e:
            print(f"   ❌ Error generating architecture analysis: {e}")
        
        # Generate documentation audit report
        doc_file = Path(self.config['output_paths']['documentation_report'])
        try:
            with open(doc_file, 'w') as f:
                f.write("# Documentation Audit Report\n\n")
                f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
                f.write(f"## Quality Metrics Summary\n")
                doc_quality = analysis_results.get('documentation', {}).get('quality_metrics', {})
                for key, value in doc_quality.items():
                    f.write(f"- {key.replace('_', ' ').title()}: {value:.2f}\n")
            generated_files.append(str(doc_file))
            
        except Exception as e:
            print(f"   ❌ Error generating documentation audit: {e}")
        
        # Generate infrastructure assessment
        infra_file = Path(self.config['output_paths']['infrastructure_report'])
        try:
            with open(infra_file, 'w') as f:
                f.write("# Infrastructure Assessment Report\n\n")
                f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
                f.write(f"## Build Systems\n")
                for system in analysis_results.get('infrastructure', {}).get('build_systems', []):
                    f.write(f"- {system}\n")
                f.write(f"\n## Deployment Configurations\n")
                for config in analysis_results.get('infrastructure', {}).get('deployment_configs', []):
                    f.write(f"- {config}\n")
            generated_files.append(str(infra_file))
            
        except Exception as e:
            print(f"   ❌ Error generating infrastructure assessment: {e}")
        
        # Generate optimization recommendations
        opt_file = Path(self.config['output_paths']['optimization_recommendations'])
        try:
            with open(opt_file, 'w') as f:
                f.write("# Optimization Recommendations\n\n")
                f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
                f.write(f"## Immediate Actions\n")
                f.write(f"1. Improve documentation coverage\n")
                f.write(f"2. Address technical debt items\n")
                f.write(f"3. Enhance build system automation\n")
                f.write(f"4. Implement continuous monitoring\n")
                f.write(f"5. Establish coding standards\n\n")
                f.write(f"## Priority Matrix\n")
                f.write(f"- **High Priority**: Documentation gaps, Critical technical debt\n")
                f.write(f"- **Medium Priority**: Infrastructure automation, Monitoring setup\n")
                f.write(f"- **Low Priority**: Minor improvements, Enhancements\n")
            generated_files.append(str(opt_file))
            
        except Exception as e:
            print(f"   ❌ Error generating optimization recommendations: {e}")
        
        return generated_files

def main():
    """Main entry point for the optimized runner."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Optimized System Architecture Design Awareness Runner"
    )
    parser.add_argument(
        "--project-root", "-p",
        default="./",
        help="Project root directory (default: ./)"
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to configuration file"
    )
    
    args = parser.parse_args()
    
    # Initialize optimized runner
    runner = OptimizedSystemAwarenessRunner(args.project_root, args.config)
    
    # Run the optimized analysis
    result = runner.run_optimized_analysis()
    
    # Final status
    print(f"\n{'='*60}")
    print(f"🏁 OPTIMIZED ANALYSIS COMPLETE")
    print(f"{'='*60}")
    
    if result.get("success"):
        print(f"✅ Analysis completed successfully!")
        print(f"📊 Health Score: {result['analysis_results']['health_score']['overall_score']:.2f}/1.0")
        print(f"📁 Files Generated: {len(result['generated_files'])}")
        print(f"📋 Ledger Updated: {'Yes' if result.get('ledger_updated') else 'No'}")
        return 0
    else:
        print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
        return 1

if __name__ == "__main__":
    sys.exit(main())