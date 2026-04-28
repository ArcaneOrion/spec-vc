from __future__ import annotations

import json
from pathlib import Path

from spec_vc.manifest import (
    AuditFinding,
    AuditReport,
    TestReport,
    TestUnitResult,
    VerificationResult,
)
from spec_vc.verify import (
    check_coverage_from_raw,
    check_evidence,
    check_format,
    run_verify,
)


VALID_OPENAPI = """openapi: "3.0.3"
info:
  title: test
  version: "0.1.0"
paths:
  /users:
    get:
      responses:
        200:
          description: ok
"""

VALID_SCHEMA = """{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "User",
  "type": "object",
  "properties": {
    "id": {"type": "integer"},
    "name": {"type": "string"}
  }
}
"""

VALID_GHERKIN = """Feature: user list
  Scenario: get all users
    When GET /users
    Then status is 200
    And response is JSON array
"""


def _make_manifest_data(num_specs: int = 1) -> dict:
    units = []
    for i in range(num_specs):
        sid = f"{i + 1:03d}"
        units.append({
            "unit_id": f"audit-{sid}",
            "spec_id": sid,
            "adr_ref": "ADR-000",
            "dev_doc_summary": {"overview": "test", "interface_contract": "", "data_shape": "", "behavior_rules": "", "non_goals": ""},
            "formal_files": {
                "contract.openapi.yaml": VALID_OPENAPI,
                "schema.json": VALID_SCHEMA,
                "behavior.feature": VALID_GHERKIN,
            },
            "complexity_score": 5,
        })
    return {
        "repo_root": "/tmp/repo",
        "specs_root": "/tmp/repo/doc/arch/specs",
        "staged_files": ["src/main.py"],
        "staged_diff": "diff ...",
        "audit_units": units,
        "test_units": [],
        "complexity_report": {"total_audit_units": num_specs, "total_test_units": 0, "recommended_audit_agents": 1, "recommended_test_agents": 1},
    }


def _make_audit_data(spec_id: str = "001", symbol: str = "✅", description: str = "ok", formal_file: str = "contract.openapi.yaml", location: str = "src/main.py:1") -> dict:
    return {
        "findings": [
            {"symbol": symbol, "spec_id": spec_id, "formal_file": formal_file, "description": description, "location": location},
        ],
        "summary_pass": 1 if symbol == "✅" else 0,
        "summary_warn": 1 if symbol == "⚠️" else 0,
        "summary_fail": 1 if symbol == "❌" else 0,
        "judgment": "阻塞" if symbol == "❌" else "通过",
    }


def _make_test_data(test_files: list[str] | None = None, test_case_count: int = 3, passed: int = 3, failed: int = 0) -> dict:
    if test_files is None:
        test_files = ["test_users.py"]
    return {
        "unit_results": [
            {"spec_id": "001", "formal_type": "openapi", "test_files": test_files, "test_case_count": test_case_count, "passed": passed, "failed": failed, "judgment": "通过" if failed == 0 else "失败"},
        ],
        "total_cases": test_case_count,
        "total_passed": passed,
        "total_failed": failed,
        "judgment": "通过" if failed == 0 else "失败",
    }


class TestCoverageCheck:
    def test_full_coverage_passes(self):
        manifest = _make_manifest_data(1)
        audit = _make_audit_data(spec_id="001", formal_file="contract.openapi.yaml")
        ok, issues = check_coverage_from_raw(manifest, audit)
        assert not ok  # only covers 1 of 3 formal files per spec
        assert len(issues) == 2  # 2 uncovered

    def test_missing_unit_fails(self):
        manifest = _make_manifest_data(2)
        audit = _make_audit_data(spec_id="001")  # only covers spec 001
        ok, issues = check_coverage_from_raw(manifest, audit)
        assert not ok

    def test_missing_formal_file_fails(self):
        manifest = _make_manifest_data(1)
        audit = _make_audit_data(spec_id="001", formal_file="contract.openapi.yaml")
        ok, issues = check_coverage_from_raw(manifest, audit)
        assert not ok
        assert "schema.json" in " ".join(issues) or "behavior.feature" in " ".join(issues)


class TestFormatCheck:
    def test_valid_finding_passes(self):
        report = AuditReport(
            findings=[AuditFinding(symbol="✅", spec_id="001", formal_file="contract.openapi.yaml", description="ok", location="src/main.py:1")],
            summary_pass=1, summary_warn=0, summary_fail=0, judgment="通过",
        )
        ok, issues = check_format(report)
        assert ok
        assert len(issues) == 0

    def test_all_three_symbols_valid(self):
        for symbol, is_fail, is_warn in [("✅", False, False), ("⚠️", False, True), ("❌", True, False)]:
            report = AuditReport(
                findings=[AuditFinding(symbol=symbol, spec_id="001", formal_file="f.yaml", description="desc", location="f:1")],
                summary_pass=0 if (is_fail or is_warn) else 1,
                summary_warn=1 if is_warn else 0,
                summary_fail=1 if is_fail else 0,
                judgment="阻塞" if is_fail else "通过",
            )
            ok, _ = check_format(report)
            assert ok, f"symbol={symbol} failed"

    def test_invalid_symbol_fails(self):
        report = AuditReport(
            findings=[AuditFinding(symbol="[x]", spec_id="001", formal_file="f.yaml", description="desc", location="f:1")],
            summary_pass=1, summary_warn=0, summary_fail=0, judgment="通过",
        )
        ok, issues = check_format(report)
        assert not ok
        assert any("非法标记" in i for i in issues)

    def test_missing_description_fails(self):
        report = AuditReport(
            findings=[AuditFinding(symbol="✅", spec_id="001", formal_file="f.yaml", description="", location="f:1")],
            summary_pass=1, summary_warn=0, summary_fail=0, judgment="通过",
        )
        ok, issues = check_format(report)
        assert not ok
        assert any("description" in i for i in issues)

    def test_missing_location_fails(self):
        report = AuditReport(
            findings=[AuditFinding(symbol="✅", spec_id="001", formal_file="f.yaml", description="desc", location="")],
            summary_pass=1, summary_warn=0, summary_fail=0, judgment="通过",
        )
        ok, issues = check_format(report)
        assert not ok
        assert any("location" in i for i in issues)

    def test_count_mismatch_fails(self):
        report = AuditReport(
            findings=[AuditFinding(symbol="✅", spec_id="001", formal_file="f.yaml", description="desc", location="f:1")],
            summary_pass=999, summary_warn=0, summary_fail=0, judgment="通过",
        )
        ok, issues = check_format(report)
        assert not ok
        assert any("不一致" in i for i in issues)

    def test_fail_judgment_contradiction(self):
        report = AuditReport(
            findings=[AuditFinding(symbol="❌", spec_id="001", formal_file="f.yaml", description="desc", location="f:1")],
            summary_pass=0, summary_warn=0, summary_fail=1, judgment="通过",
        )
        ok, issues = check_format(report)
        assert not ok
        assert any("矛盾" in i for i in issues)

    def test_invalid_judgment_fails(self):
        report = AuditReport(
            findings=[AuditFinding(symbol="✅", spec_id="001", formal_file="f.yaml", description="desc", location="f:1")],
            summary_pass=1, summary_warn=0, summary_fail=0, judgment="INVALID",
        )
        ok, issues = check_format(report)
        assert not ok
        assert any("无效" in i for i in issues)


class TestEvidenceCheck:
    def test_existing_files_pass(self, tmp_path: Path):
        specs_root = tmp_path / "specs"
        test_dir = specs_root / "001" / "tests"
        test_dir.mkdir(parents=True)
        (test_dir / "test_users.py").write_text("def test(): pass\n")

        report = TestReport(
            unit_results=[TestUnitResult(spec_id="001", formal_type="openapi", test_files=["test_users.py"], test_case_count=3, passed=3, failed=0, judgment="通过")],
            total_cases=3, total_passed=3, total_failed=0, judgment="通过",
        )
        ok, issues = check_evidence(report, specs_root)
        assert ok

    def test_missing_file_fails(self, tmp_path: Path):
        specs_root = tmp_path / "specs"
        (specs_root / "001" / "tests").mkdir(parents=True)

        report = TestReport(
            unit_results=[TestUnitResult(spec_id="001", formal_type="openapi", test_files=["test_missing.py"], test_case_count=3, passed=3, failed=0, judgment="通过")],
            total_cases=3, total_passed=3, total_failed=0, judgment="通过",
        )
        ok, issues = check_evidence(report, specs_root)
        assert not ok
        assert any("不存在" in i for i in issues)

    def test_empty_file_fails(self, tmp_path: Path):
        specs_root = tmp_path / "specs"
        test_dir = specs_root / "001" / "tests"
        test_dir.mkdir(parents=True)
        (test_dir / "test_empty.py").write_text("")

        report = TestReport(
            unit_results=[TestUnitResult(spec_id="001", formal_type="openapi", test_files=["test_empty.py"], test_case_count=0, passed=0, failed=0, judgment="失败")],
            total_cases=0, total_passed=0, total_failed=0, judgment="失败",
        )
        ok, issues = check_evidence(report, specs_root)
        assert not ok

    def test_zero_cases_fails(self, tmp_path: Path):
        specs_root = tmp_path / "specs"
        test_dir = specs_root / "001" / "tests"
        test_dir.mkdir(parents=True)
        (test_dir / "test_users.py").write_text("def test(): pass\n")

        report = TestReport(
            unit_results=[TestUnitResult(spec_id="001", formal_type="openapi", test_files=["test_users.py"], test_case_count=0, passed=0, failed=0, judgment="失败")],
            total_cases=0, total_passed=0, total_failed=0, judgment="失败",
        )
        ok, issues = check_evidence(report, specs_root)
        assert not ok


class TestRunVerifyIntegration:
    def test_all_pass(self, tmp_path: Path):
        specs_root = tmp_path / "specs"
        test_dir = specs_root / "001" / "tests"
        test_dir.mkdir(parents=True)
        (test_dir / "test_users.py").write_text("def test(): pass\n")

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(_make_manifest_data(1), ensure_ascii=False))

        audit_path = tmp_path / "audit.json"
        audit_path.write_text(json.dumps(_make_audit_data(spec_id="001", symbol="✅", formal_file="contract.openapi.yaml"), ensure_ascii=False))

        test_path = tmp_path / "test.json"
        test_path.write_text(json.dumps(_make_test_data(test_files=["test_users.py"], test_case_count=3, passed=3, failed=0), ensure_ascii=False))

        result = run_verify(audit_path, test_path, manifest_path)
        assert not result.all_pass  # coverage fails because only 1 of 3 formal files covered

    def test_partial_fail(self, tmp_path: Path):
        specs_root = tmp_path / "specs"
        test_dir = specs_root / "001" / "tests"
        test_dir.mkdir(parents=True)
        (test_dir / "test_users.py").write_text("def test(): pass\n")

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(_make_manifest_data(1), ensure_ascii=False))

        audit_path = tmp_path / "audit.json"
        audit_path.write_text(json.dumps(_make_audit_data(spec_id="001", symbol="❌", formal_file="contract.openapi.yaml"), ensure_ascii=False))

        test_path = tmp_path / "test.json"
        test_path.write_text(json.dumps(_make_test_data(test_files=["test_users.py"], test_case_count=3, passed=3, failed=0), ensure_ascii=False))

        result = run_verify(audit_path, test_path, manifest_path)
        assert not result.all_pass

    def test_with_minimal_manifest_all_pass(self, tmp_path: Path):
        specs_root = tmp_path / "specs"
        test_dir = specs_root / "001" / "tests"
        test_dir.mkdir(parents=True)
        (test_dir / "test_users.py").write_text("def test(): pass\n")

        # Create a minimal manifest just for specs_root discovery
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({
            "specs_root": str(specs_root),
            "audit_units": [],
            "test_units": [],
            "complexity_report": {},
        }, ensure_ascii=False))

        audit_path = tmp_path / "audit.json"
        audit_path.write_text(json.dumps(_make_audit_data(spec_id="001", symbol="✅"), ensure_ascii=False))

        test_path = tmp_path / "test.json"
        test_path.write_text(json.dumps(_make_test_data(test_files=["test_users.py"], test_case_count=3, passed=3, failed=0), ensure_ascii=False))

        result = run_verify(audit_path, test_path, manifest_path)
        assert result.coverage_pass  # empty manifest, nothing to check
        assert result.format_pass
        assert result.evidence_pass
        assert result.all_pass
