Feature: 审计模式冻结对齐文档基线

  Rule: review records the alignment document baseline

    Scenario: [ADR-NNN] review writes baseline files
      Given staged code changes exist
      And the commit message contains "[ADR-022]"
      When `spec-vc review --message "feat: x [ADR-022]"` runs
      Then `.git/spec-vc-review.json` contains `document_baseline`
      And the baseline contains the ADR file
      And the baseline contains the selected Plan file when it exists
      And the baseline contains associated Spec dev-doc and formal files when they exist

  Rule: commit-msg hook blocks baseline drift

    Scenario: ADR file changes after review
      Given `spec-vc review` has written review.json for "[ADR-022]"
      When `doc/arch/adr-022.md` changes before commit
      And the commit-msg hook runs
      Then the hook exits non-zero
      And stderr explains that the document baseline changed
      And stderr suggests rerunning `spec-vc review`

    Scenario: Plan file changes after review
      Given `spec-vc review` has written review.json for "[ADR-022]"
      When `doc/arch/plans/ADR-022-plan-001.md` changes before commit
      And the commit-msg hook runs
      Then the hook exits non-zero
      And stderr explains that the document baseline changed

    Scenario: Spec formal file changes after review
      Given `spec-vc review` has written review.json for "[ADR-022]"
      When `doc/arch/specs/022/schema.json` changes before commit
      And the commit-msg hook runs
      Then the hook exits non-zero
      And stderr explains that the document baseline changed

  Rule: compatibility remains stable

    Scenario: legacy review.json has no document_baseline
      Given `.git/spec-vc-review.json` was written by an older spec-vc version
      And the anchor still matches the current staged diff
      When the commit-msg hook runs
      Then the hook does not fail only because `document_baseline` is absent

    Scenario: SPEC_VC_BYPASS is set
      Given document baseline drift exists
      And `SPEC_VC_BYPASS` is non-empty
      When the commit-msg hook runs
      Then bypass logging occurs
      And document baseline verification is skipped
