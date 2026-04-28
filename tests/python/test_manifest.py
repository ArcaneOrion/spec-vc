from __future__ import annotations

import json
from dataclasses import asdict

from spec_vc.manifest import (
    AuditManifest,
    AuditUnit,
    ComplexityReport,
    DevDocSummary,
    TestUnit,
)


def _make_minimal_manifest(num_specs: int = 1) -> AuditManifest:
    audit_units = []
    test_units = []
    for i in range(num_specs):
        sid = f"{i + 1:03d}"
        ds = DevDocSummary(
            overview=f"overview {sid}",
            interface_contract=f"contract {sid}",
            data_shape=f"data {sid}",
            behavior_rules=f"behavior {sid}",
            non_goals=f"non-goals {sid}",
        )
        formal = {
            "contract.openapi.yaml": f"openapi content {sid}",
            "schema.json": f"schema content {sid}",
            "behavior.feature": f"gherkin content {sid}",
        }
        audit_units.append(
            AuditUnit(
                unit_id=f"audit-{sid}",
                spec_id=sid,
                adr_ref=f"ADR-000",
                dev_doc_summary=ds,
                formal_files=formal,
                complexity_score=5 + i,
            )
        )
        for ft in ["openapi", "jsonschema", "gherkin"]:
            test_units.append(
                TestUnit(
                    unit_id=f"test-{sid}-{ft}",
                    spec_id=sid,
                    formal_type=ft,
                    formal_content=f"content {sid} {ft}",
                    test_dir=f"specs/{sid}/tests/",
                    estimated_complexity=2 + i,
                )
            )

    return AuditManifest(
        repo_root="/tmp/repo",
        specs_root="/tmp/repo/doc/arch/specs",
        staged_files=["src/main.py"],
        staged_diff="diff --git a/src/main.py ...",
        audit_units=audit_units,
        test_units=test_units,
        complexity_report=ComplexityReport(
            total_audit_units=num_specs,
            total_test_units=num_specs * 3,
            recommended_audit_agents=max(1, (num_specs + 2) // 3),
            recommended_test_agents=max(1, (num_specs * 3 + 2) // 3),
        ),
    )


class TestManifestStructure:
    def test_single_spec_produces_units(self):
        m = _make_minimal_manifest(1)
        assert len(m.audit_units) == 1
        assert len(m.test_units) == 3
        assert m.complexity_report.total_audit_units == 1
        assert m.complexity_report.total_test_units == 3

    def test_multiple_specs_produce_correct_counts(self):
        m = _make_minimal_manifest(3)
        assert len(m.audit_units) == 3
        assert len(m.test_units) == 9
        assert m.complexity_report.total_audit_units == 3
        assert m.complexity_report.total_test_units == 9

    def test_zero_specs_empty_manifest(self):
        m = _make_minimal_manifest(0)
        assert len(m.audit_units) == 0
        assert len(m.test_units) == 0
        assert m.complexity_report.total_audit_units == 0
        assert m.complexity_report.total_test_units == 0

    def test_staged_files_preserved(self):
        m = _make_minimal_manifest(1)
        assert "src/main.py" in m.staged_files

    def test_dev_doc_summary_fields_filled(self):
        m = _make_minimal_manifest(1)
        ds = m.audit_units[0].dev_doc_summary
        assert ds.overview == "overview 001"
        assert ds.interface_contract == "contract 001"
        assert ds.data_shape == "data 001"
        assert ds.behavior_rules == "behavior 001"
        assert ds.non_goals == "non-goals 001"


class TestManifestSerialization:
    def test_json_roundtrip(self):
        m = _make_minimal_manifest(1)
        js = json.dumps(asdict(m), ensure_ascii=False)
        data = json.loads(js)
        assert data["repo_root"] == "/tmp/repo"
        assert len(data["audit_units"]) == 1
        assert len(data["test_units"]) == 3

    def test_json_contains_expected_keys(self):
        m = _make_minimal_manifest(2)
        js = json.dumps(asdict(m), ensure_ascii=False)
        data = json.loads(js)
        for key in ["repo_root", "specs_root", "staged_files", "staged_diff",
                     "audit_units", "test_units", "complexity_report"]:
            assert key in data, f"missing key: {key}"

    def test_audit_unit_has_formal_files(self):
        m = _make_minimal_manifest(1)
        js = json.dumps(asdict(m), ensure_ascii=False)
        data = json.loads(js)
        au = data["audit_units"][0]
        assert "contract.openapi.yaml" in au["formal_files"]
        assert "schema.json" in au["formal_files"]
        assert "behavior.feature" in au["formal_files"]


class TestComplexityReport:
    def test_single_spec_agents(self):
        m = _make_minimal_manifest(1)
        assert m.complexity_report.recommended_audit_agents == 1
        assert m.complexity_report.recommended_test_agents == 1

    def test_four_specs_agents(self):
        m = _make_minimal_manifest(4)
        assert m.complexity_report.recommended_audit_agents == 2
        assert m.complexity_report.recommended_test_agents == 4

    def test_seven_specs_agents(self):
        m = _make_minimal_manifest(7)
        assert m.complexity_report.recommended_audit_agents == 3
        assert m.complexity_report.recommended_test_agents == 7
