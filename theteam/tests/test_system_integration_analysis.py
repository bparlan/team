"""
Regression tests for SystemIntegration's integrated system analysis.

Covers defects found during the Phase 5 drift audit:
  * `_run_integrated_system_analysis` never returned its result, so the
    caller's `result['success']` raised TypeError on the success path.
  * It referenced `sys` and `PROJECT_ROOT`, neither of which was defined in
    the module.
"""

from pathlib import Path

import pytest

from theteam.core import system_integration as si
from theteam.core.system_integration import SystemIntegration


def _make(tmp_path, returncode=0, stdout="ok", stderr=""):
    """A real instance whose isolation runner is stubbed out."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "sa_runner.py").write_text("# fake runner\n")

    calls = {}

    class FakeIsolation:
        def available(self):
            return True

        def run(self, cmd, container_name=None, project_root=None, env=None):
            calls["cmd"] = cmd
            calls["env"] = env
            return {"exit_code": returncode, "stdout": stdout, "stderr": stderr}

    integration = SystemIntegration(project_root=str(tmp_path))
    integration.isolation = FakeIsolation()
    integration._update_health_metrics = lambda m: None
    return integration, calls


def _analyze(integration, root):
    return integration._run_integrated_system_analysis(
        {"type": "startup", "project_root": str(root)}
    )


class TestModuleLevelNames:
    def test_sys_is_imported(self):
        # The function body uses sys.path and sys.executable.
        assert hasattr(si, "sys")

    def test_project_root_is_defined(self):
        # The function body builds PYTHONPATH from it, and that path must
        # contain the `theteam` package for the agent to import it.
        assert isinstance(si.PROJECT_ROOT, str)

    def test_project_root_points_at_repo(self):
        assert (Path(si.PROJECT_ROOT) / "theteam" / "__init__.py").is_file()


class TestReturnsResult:
    def test_success_path_returns_a_dict(self, tmp_path):
        """The caller does result['success']; returning None was a TypeError."""
        integration, _ = _make(tmp_path, returncode=0)
        result = _analyze(integration, tmp_path)

        assert result is not None
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["exit_code"] == 0
        assert result["isolated"] is True

    def test_warning_exit_code_counts_as_success(self, tmp_path):
        integration, _ = _make(tmp_path, returncode=2)
        result = _analyze(integration, tmp_path)
        assert result["success"] is True
        assert result["health_metrics"]["status"] == "WARNING"

    def test_failure_exit_code_is_not_success(self, tmp_path):
        integration, _ = _make(tmp_path, returncode=1)
        result = _analyze(integration, tmp_path)
        assert result["success"] is False
        assert result["health_metrics"]["status"] == "CRITICAL"

    def test_exception_returns_error_dict_not_none(self, tmp_path):
        """A raise must not escape as None; the caller indexes the result."""
        integration, _ = _make(tmp_path)

        def boom(*a, **k):
            raise RuntimeError("isolation exploded")

        integration.isolation.run = boom
        result = _analyze(integration, tmp_path)
        assert result is not None
        assert result["success"] is False
        assert "isolation exploded" in result["error"]

    def test_passes_pythonpath_to_isolated_agent(self, tmp_path):
        # The agent imports theteam.*, so it needs the repo root on PYTHONPATH.
        integration, calls = _make(tmp_path)
        _analyze(integration, tmp_path)
        assert calls["env"]["PYTHONPATH"] == si.PROJECT_ROOT

    def test_runner_receives_project_root_flag(self, tmp_path):
        integration, calls = _make(tmp_path)
        _analyze(integration, tmp_path)
        assert "--project-root" in calls["cmd"]
        assert str(tmp_path) in calls["cmd"]
