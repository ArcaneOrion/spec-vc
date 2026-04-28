from __future__ import annotations

import json
from pathlib import Path

from .manifest import (
    AuditFinding,
    AuditReport,
    TestReport,
    TestUnitResult,
    VerificationResult,
)
from .errors import UsageError


VALID_SYMBOLS = {"✅", "⚠️", "❌"}
VALID_JUDGMENTS = {"通过", "阻塞"}


def check_coverage_from_raw(
    manifest_data: dict, audit_data: dict
) -> tuple[bool, list[str]]:
    expected: set[tuple[str, str]] = set()
    for unit in manifest_data.get("audit_units", []):
        spec_id = unit["spec_id"]
        for fname in unit.get("formal_files", {}):
            expected.add((spec_id, fname))

    covered: set[tuple[str, str]] = set()
    for finding in audit_data.get("findings", []):
        covered.add((finding.get("spec_id", ""), finding.get("formal_file", "")))

    issues: list[str] = []
    for spec_id, fname in sorted(expected):
        if (spec_id, fname) not in covered:
            issues.append(f"未覆盖: Spec-{spec_id} / {fname}")

    return len(issues) == 0, issues


def check_format(audit_report: AuditReport) -> tuple[bool, list[str]]:
    issues: list[str] = []

    for i, finding in enumerate(audit_report.findings):
        prefix = f"Finding[{i}]"
        if finding.symbol not in VALID_SYMBOLS:
            issues.append(
                f"{prefix}: 非法标记 '{finding.symbol}'，允许: {VALID_SYMBOLS}"
            )
        if not finding.description.strip():
            issues.append(f"{prefix}: description 不能为空")
        if not finding.location.strip():
            issues.append(f"{prefix}: location 不能为空")
        if not finding.spec_id.strip():
            issues.append(f"{prefix}: spec_id 不能为空")
        if not finding.formal_file.strip():
            issues.append(f"{prefix}: formal_file 不能为空")

    actual_pass = sum(1 for f in audit_report.findings if f.symbol == "✅")
    actual_warn = sum(1 for f in audit_report.findings if f.symbol == "⚠️")
    actual_fail = sum(1 for f in audit_report.findings if f.symbol == "❌")

    if actual_pass != audit_report.summary_pass:
        issues.append(
            f"summary_pass ({audit_report.summary_pass}) 与实际 ✅ 数量 ({actual_pass}) 不一致"
        )
    if actual_warn != audit_report.summary_warn:
        issues.append(
            f"summary_warn ({audit_report.summary_warn}) 与实际 ⚠️ 数量 ({actual_warn}) 不一致"
        )
    if actual_fail != audit_report.summary_fail:
        issues.append(
            f"summary_fail ({audit_report.summary_fail}) 与实际 ❌ 数量 ({actual_fail}) 不一致"
        )

    if audit_report.judgment not in VALID_JUDGMENTS:
        issues.append(f"judgment '{audit_report.judgment}' 无效，允许: {VALID_JUDGMENTS}")

    if audit_report.summary_fail > 0 and audit_report.judgment == "通过":
        issues.append("summary_fail > 0 但 judgment 为 '通过'，判定矛盾")

    return len(issues) == 0, issues


def check_evidence(
    test_report: TestReport, specs_root: Path
) -> tuple[bool, list[str]]:
    issues: list[str] = []

    if test_report.total_cases == 0:
        issues.append("total_cases 为 0，测试未实际执行")

    for unit_result in test_report.unit_results:
        prefix = f"Spec-{unit_result.spec_id} / {unit_result.formal_type}"
        if unit_result.test_case_count == 0:
            issues.append(f"{prefix}: test_case_count 为 0")

        for tf in unit_result.test_files:
            test_path = specs_root / str(unit_result.spec_id) / "tests" / tf
            if not test_path.exists():
                issues.append(f"{prefix}: 测试文件不存在: {test_path}")
            elif test_path.stat().st_size == 0:
                issues.append(f"{prefix}: 测试文件为空: {test_path}")

    return len(issues) == 0, issues


def run_verify(
    audit_report_path: Path,
    test_report_path: Path,
    manifest_path: Path,
) -> VerificationResult:
    if not manifest_path.exists():
        raise UsageError(f"manifest 文件不存在: {manifest_path}")

    audit_data = json.loads(audit_report_path.read_text())
    audit_report = AuditReport(
        findings=[
            AuditFinding(
                symbol=f.get("symbol", ""),
                spec_id=f.get("spec_id", ""),
                formal_file=f.get("formal_file", ""),
                description=f.get("description", ""),
                location=f.get("location", ""),
            )
            for f in audit_data.get("findings", [])
        ],
        summary_pass=audit_data.get("summary_pass", 0),
        summary_warn=audit_data.get("summary_warn", 0),
        summary_fail=audit_data.get("summary_fail", 0),
        judgment=audit_data.get("judgment", ""),
    )

    test_data = json.loads(test_report_path.read_text())
    test_report = TestReport(
        unit_results=[
            TestUnitResult(
                spec_id=u.get("spec_id", ""),
                formal_type=u.get("formal_type", ""),
                test_files=u.get("test_files", []),
                test_case_count=u.get("test_case_count", 0),
                passed=u.get("passed", 0),
                failed=u.get("failed", 0),
                judgment=u.get("judgment", ""),
            )
            for u in test_data.get("unit_results", [])
        ],
        total_cases=test_data.get("total_cases", 0),
        total_passed=test_data.get("total_passed", 0),
        total_failed=test_data.get("total_failed", 0),
        judgment=test_data.get("judgment", ""),
    )

    manifest_data = json.loads(manifest_path.read_text())
    coverage_pass, coverage_issues = check_coverage_from_raw(manifest_data, audit_data)

    specs_root_str = manifest_data.get("specs_root", "")
    if not specs_root_str:
        raise UsageError("manifest 缺少 specs_root 字段")
    evidence_specs_root = Path(specs_root_str)

    format_pass, format_issues = check_format(audit_report)
    evidence_pass, evidence_issues = check_evidence(test_report, evidence_specs_root)

    all_pass = coverage_pass and format_pass and evidence_pass

    return VerificationResult(
        coverage_pass=coverage_pass,
        coverage_issues=coverage_issues,
        format_pass=format_pass,
        format_issues=format_issues,
        evidence_pass=evidence_pass,
        evidence_issues=evidence_issues,
        all_pass=all_pass,
    )
