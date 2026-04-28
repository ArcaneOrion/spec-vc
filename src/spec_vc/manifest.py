from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DevDocSummary:
    overview: str = ""
    interface_contract: str = ""
    data_shape: str = ""
    behavior_rules: str = ""
    non_goals: str = ""


@dataclass(slots=True)
class AuditUnit:
    unit_id: str
    spec_id: str
    adr_ref: str
    dev_doc_summary: DevDocSummary
    formal_files: dict[str, str]         # fname -> content
    complexity_score: int = 0


@dataclass(slots=True)
class TestUnit:
    __test__ = False                     # not a pytest test class

    unit_id: str
    spec_id: str
    formal_type: str                     # openapi | jsonschema | gherkin
    formal_content: str
    test_dir: str
    estimated_complexity: int = 0


@dataclass(slots=True)
class ComplexityReport:
    total_audit_units: int = 0
    total_test_units: int = 0
    recommended_audit_agents: int = 1
    recommended_test_agents: int = 1


@dataclass(slots=True)
class AuditManifest:
    repo_root: str
    specs_root: str
    staged_files: list[str]
    staged_diff: str
    audit_units: list[AuditUnit]
    test_units: list[TestUnit]
    complexity_report: ComplexityReport


@dataclass(slots=True)
class AuditFinding:
    symbol: str                          # ✅ / ⚠️ / ❌
    spec_id: str
    formal_file: str
    description: str
    location: str                        # path:line


@dataclass(slots=True)
class AuditReport:
    findings: list[AuditFinding]
    summary_pass: int = 0
    summary_warn: int = 0
    summary_fail: int = 0
    judgment: str = ""                   # 通过 | 阻塞


@dataclass(slots=True)
class TestUnitResult:
    __test__ = False                     # not a pytest test class

    spec_id: str
    formal_type: str
    test_files: list[str]
    test_case_count: int = 0
    passed: int = 0
    failed: int = 0
    judgment: str = ""                   # 通过 | 失败


@dataclass(slots=True)
class TestReport:
    __test__ = False                     # not a pytest test class

    unit_results: list[TestUnitResult]
    total_cases: int = 0
    total_passed: int = 0
    total_failed: int = 0
    judgment: str = ""                   # 通过 | 失败


@dataclass(slots=True)
class VerificationResult:
    coverage_pass: bool = True
    coverage_issues: list[str] = field(default_factory=list)
    format_pass: bool = True
    format_issues: list[str] = field(default_factory=list)
    evidence_pass: bool = True
    evidence_issues: list[str] = field(default_factory=list)
    all_pass: bool = True
