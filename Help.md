Test Report Storage Strategy and Markdown Templates

Recommendation

Use Gitea as the human-facing home for test results and Artifactory as the storage location for large or binary evidence.

• Gitea gives development and systems engineers a readable, searchable, version-controlled entry point. Markdown renders directly and can contain instructions, conclusions, links, and traceability.
• Artifactory is designed for large, immutable, downloadable files such as firmware, disk images, packet captures, videos, and compressed log bundles.

If only one system can be used, choose Gitea when the reports and artifacts are small. For a scalable long-term design, use both.

> **Gitea:** explanation, navigation, traceability, and instructions  
> **Artifactory:** binaries, captures, logs, images, and downloadable evidence

Content Placement

|Content                                   |Recommended location                     |Notes                                             |
|------------------------------------------|-----------------------------------------|--------------------------------------------------|
|Test summary and conclusions              |Gitea                                    |Primary entry point for reviewers                 |
|Reproduction and debugging instructions   |Gitea                                    |Keep beside the report                            |
|Known failures                            |Gitea                                    |One Markdown file per important failure works well|
|Requirement coverage                      |Gitea                                    |Tables are easy to review and diff                |
|Environment and configuration             |Gitea                                    |Remove secrets before publishing                  |
|Small logs/configuration snapshots        |Gitea                                    |Only when reasonably sized and useful for review  |
|PCAP files                                |Artifactory                              |Link from the report and include a checksum       |
|Screenshots and short evidence files      |Gitea or Artifactory                     |Choose based on size and retention needs          |
|Videos, core dumps, memory dumps          |Artifactory                              |Avoid storing these in Git                        |
|WIC images, firmware, and root filesystems|Artifactory                              |Treat as immutable build artifacts                |
|Large raw test-output bundles             |Artifactory                              |Prefer a compressed archive                       |
|pytest HTML report                        |Gitea Pages/static hosting or Artifactory|Link it from the run README                       |

Suggested Repository Structure

Use a dedicated test-results repository rather than mixing generated reports into the product source repository.

```text
product-test-results/
├── README.md
├── releases/
│   └── product-a/
│       └── 2.4.1/
│           └── run-2026-08-27_001/
│               ├── README.md
│               ├── summary.md
│               ├── environment.md
│               ├── reproduction.md
│               ├── requirements.md
│               ├── failures/
│               │   ├── REQ-1042.md
│               │   └── REQ-1067.md
│               └── artifact-links.md
└── templates/
    ├── test-run-template.md
    ├── qualification-report-template.md
    ├── failure-template.md
    └── requirements-template.md
```

Design Rules

1. Create a new, immutable directory for every published run; never overwrite an older result.
2. Record the product version, product commit, test-framework commit, configuration version, and hardware revision.
3. Link large evidence from Gitea to Artifactory.
4. Include SHA-256 checksums for important downloaded artifacts.
5. Do not commit credentials, tokens, private keys, or configurations containing secrets.
6. Publish meaningful runs such as release candidates, qualification runs, nightlies, and requested investigations—not every local developer execution.
7. Have CI generate the repeated tables and metadata. Allow engineers to add conclusions and investigation notes afterward.
8. Use stable requirement IDs so results can be compared across releases.
9. Distinguish product failures from test-infrastructure failures.
10. State whether a failed or skipped test affects release readiness.

────────

Template 1: Test Run README

Use this as the entry point for one test execution.

```markdown
# <Product> <Version> — Test Run <Run ID>

## Result

**Overall status:** PASS / PASS WITH KNOWN ISSUES / FAIL / INCOMPLETE

<Two or three sentences explaining what was tested, the result, and the most important concern.>

| Metric | Result |
|---|---:|
| Requirements selected | <number> |
| Requirements executed | <number> |
| Passed | <number> |
| Failed | <number> |
| Skipped | <number> |
| Blocked | <number> |
| Infrastructure errors | <number> |
| Duration | <duration> |

## Release Recommendation

**GO / GO WITH CONDITIONS / NO-GO / NOT EVALUATED**

<Explain the recommendation and any conditions.>

## Build Under Test

| Field | Value |
|---|---|
| Product | <name> |
| Version | <version> |
| Product commit | `<commit>` |
| Test-framework commit | `<commit>` |
| Build/artifact | [<artifact name>](<Artifactory URL>) |
| Hardware | <board/model/revision> |
| Run ID | `<run-id>` |
| Started | <ISO-8601 timestamp> |
| Completed | <ISO-8601 timestamp> |
| Triggered by | <pipeline/user/schedule> |

## Important Findings

- <Finding one>
- <Finding two>
- <Finding three>

## Failed or Blocked Requirements

| Requirement | Test | Status | Impact | Failure report |
|---|---|---|---|---|
| REQ-1042 | `test_engine_status` | Failed | High | [Details](failures/REQ-1042.md) |
| REQ-1067 | `test_rtp_stream` | Blocked | Medium | [Details](failures/REQ-1067.md) |

## Documentation

- [Detailed summary](summary.md)
- [Environment and configuration](environment.md)
- [Requirement results](requirements.md)
- [Reproduction instructions](reproduction.md)
- [Failures](failures/)
- [Artifacts and evidence](artifact-links.md)

## Approvals

| Role | Name | Decision | Date | Notes |
|---|---|---|---|---|
| Test | <name> | Pending | | |
| Development | <name> | Pending | | |
| Systems | <name> | Pending | | |
```

────────

Template 2: Detailed Qualification Report

Use this for release, formal verification, or milestone testing.

```markdown
# Qualification Test Report — <Product> <Version>

## 1. Executive Summary

**Qualification status:** PASS / CONDITIONAL PASS / FAIL / INCOMPLETE

<Summarize scope, outcome, risks, and recommendation in plain language.>

## 2. Objective

The objective of this run was to verify:

- <capability or requirement group>
- <supported operating mode>
- <regression area>

## 3. Scope

### Included

- <item>
- <item>

### Excluded

- <item and reason>
- <item and reason>

## 4. Test Items

| Item | Version/Revision | Identifier |
|---|---|---|
| Product software | <version> | `<commit>` |
| Test framework | <version> | `<commit>` |
| Hardware | <model> | <revision/serial> |
| Configuration | <name> | `<config revision>` |

## 5. Test Environment

| Component | Address/ID | OS/Firmware | Role |
|---|---|---|---|
| Controller VM | <hostname/IP> | <version> | pytest controller |
| Product A | <hostname/IP> | <version> | device under test |
| Test point | <hostname/IP> | <version> | traffic generation/capture |

See [environment.md](environment.md) for the complete configuration.

## 6. Entry Criteria

- [ ] Approved build was available
- [ ] Test environment passed health checks
- [ ] Required interfaces were reachable
- [ ] Configuration was reviewed
- [ ] Known limitations were documented

## 7. Exit Criteria

- [ ] All planned critical requirements executed
- [ ] All failures documented
- [ ] Evidence retained
- [ ] No unresolved release-blocking infrastructure errors
- [ ] Development and systems review completed

## 8. Results

| Capability | Planned | Passed | Failed | Skipped | Blocked | Status |
|---|---:|---:|---:|---:|---:|---|
| <Capability A> | 20 | 19 | 1 | 0 | 0 | Conditional |
| <Capability B> | 12 | 12 | 0 | 0 | 0 | Pass |

## 9. Deviations

| ID | Deviation | Reason | Effect on validity | Approved by |
|---|---|---|---|---|
| DEV-001 | <description> | <reason> | None/Low/High | <name> |

## 10. Failures and Anomalies

| ID | Requirement | Severity | Owner | Status | Details |
|---|---|---|---|---|---|
| FAIL-001 | REQ-1042 | High | Development | Open | [Failure report](failures/REQ-1042.md) |

## 11. Risks and Limitations

- **Risk:** <description>  
  **Impact:** <impact>  
  **Mitigation:** <mitigation>

## 12. Conclusion

<State exactly what the evidence supports and what remains unverified.>

## 13. Release Recommendation

**GO / GO WITH CONDITIONS / NO-GO**

Conditions:

1. <condition>
2. <condition>

## 14. References

- [Requirement results](requirements.md)
- [Artifacts](artifact-links.md)
- [Reproduction instructions](reproduction.md)
- [pytest HTML report](<URL>)
```

────────

Template 3: Failure Report

Create one of these for each failure that needs engineering attention.

```markdown
# Failure Report — <FAIL-ID>: <Short Title>

## Classification

| Field | Value |
|---|---|
| Failure ID | FAIL-001 |
| Requirement | REQ-1042 |
| Test | `test_engine_status` |
| Severity | Critical / High / Medium / Low |
| Category | Product / Test / Environment / Configuration / Unknown |
| Reproducibility | Always / Intermittent / Once / Not retried |
| Owner | <team/person> |
| Tracking issue | [Issue #123](<Gitea issue URL>) |
| Status | Open / Investigating / Fixed / Accepted / Cannot reproduce |

## Summary

<Explain the failure in a few sentences.>

## Expected Behavior

<What should have happened?>

## Actual Behavior

<What happened instead?>

## Release Impact

**Blocking / Conditionally blocking / Non-blocking / Unknown**

<Explain the user, system, safety, or mission impact.>

## Steps to Reproduce

1. <step>
2. <step>
3. <step>

## Observations

- <timestamped or specific observation>
- <relevant error message, kept short>

## Evidence

| Evidence | Link | SHA-256 | Notes |
|---|---|---|---|
| Application log | [Download](<URL>) | `<checksum>` | <notes> |
| Packet capture | [Download](<URL>) | `<checksum>` | Filter: `<filter>` |
| Screenshot | [View](<URL>) | `<checksum>` | <notes> |

## Initial Analysis

<State confirmed facts separately from hypotheses.>

### Confirmed

- <fact>

### Hypotheses

- <hypothesis and evidence needed>

## Workaround

<Workaround, or “None known.”>

## Retest Criteria

- [ ] Candidate fix is identified
- [ ] Same environment/configuration is available
- [ ] Original failing test passes
- [ ] Related regression tests pass
- [ ] New evidence is linked

## Resolution

<Complete after resolution, including the fixing commit and retest run.>
```

────────

Template 4: Requirement Coverage and Traceability

```markdown
# Requirement Coverage — <Product> <Version>

## Summary

| Status | Count |
|---|---:|
| Passed | <number> |
| Failed | <number> |
| Skipped | <number> |
| Blocked | <number> |
| Not selected | <number> |
| Not implemented | <number> |

## Coverage

| Requirement | Description | Capability | Test | Result | Evidence | Issue |
|---|---|---|---|---|---|---|
| REQ-1001 | Engine status is reported | Status | `test_engine_status` | Pass | [Log](<URL>) | — |
| REQ-1002 | RTP packets are transmitted | Streaming | `test_rtp_stream` | Fail | [PCAP](<URL>) | [#123](<URL>) |
| REQ-1003 | System recovers after restart | Recovery | `test_restart_recovery` | Blocked | [Failure](failures/REQ-1003.md) | [#124](<URL>) |

## Status Definitions

- **Pass:** The observed result satisfied the requirement.
- **Fail:** The test executed and the observed result did not satisfy the requirement.
- **Skipped:** The test was intentionally not executed and includes a reason.
- **Blocked:** The test could not execute because a prerequisite failed.
- **Not selected:** The requirement was outside this run's selected scope.
- **Not implemented:** No automated or manual verification method currently exists.
```

────────

Template 5: Environment and Configuration

```markdown
# Test Environment — <Run ID>

## Topology

<Add a small diagram or link to the controlled architecture document.>

## Systems

| Name | Type | Role | IP/Interface | OS/Firmware | Identifier |
|---|---|---|---|---|---|
| test-controller | VM | pytest execution | 192.0.2.10 | RHEL <version> | <VM/build ID> |
| product-a-01 | Dev board | DUT | 192.0.2.20 | <version> | <serial/revision> |
| capture-01 | VM | tshark capture | 192.0.2.30 | RHEL <version> | <VM ID> |

## Network Configuration

| Network/VLAN | CIDR | Purpose | Notes |
|---|---|---|---|
| Test control | 192.0.2.0/24 | Management and API | Isolated |
| Data plane | 198.51.100.0/24 | RTP/multicast | Capture enabled |

## Software

| Component | Version | Commit/Build | Source |
|---|---|---|---|
| Product | <version> | `<id>` | [Artifact](<URL>) |
| Test framework | <version> | `<commit>` | [Gitea](<URL>) |
| pytest | <version> | — | Python environment |
| tshark | <version> | — | Capture VM |

## Configuration

| Configuration | Revision | Purpose | Sanitized copy |
|---|---|---|---|
| Operational config | `<revision>` | Product setup | [View](<path-or-URL>) |
| Capability config | `<revision>` | Test selection | [View](<path-or-URL>) |

## Pre-Test Health Checks

- [ ] All targets reachable
- [ ] Time synchronized
- [ ] Required services running
- [ ] Disk space sufficient
- [ ] Capture interfaces verified
- [ ] Previous run state removed

## Deviations

<Document anything that differs from the controlled/expected environment.>

> Do not include passwords, access tokens, private keys, or other secrets.
```

────────

Template 6: Reproduction Instructions

````markdown
# Reproducing Test Run <Run ID>

## Prerequisites

- Python <version>
- pytest <version>
- Network access to <targets>
- Product artifact: [<name>](<URL>)
- Test-framework commit: `<commit>`
- Configuration revision: `<revision>`

## Prepare the Environment

```bash
git clone <test-framework-url>
cd <repository>
git checkout <test-framework-commit>
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
````

Deploy the Build

1. Download the exact build listed above.
2. Verify its SHA-256 checksum.
3. Deploy it using the controlled deployment procedure.
4. Confirm the reported product version.

Execute the Same Scope

```bash
pytest \
  --product <product> \
  --capability <capability> \
  --config <sanitized-config-path> \
  --html report.html \
  --self-contained-html
```

Expected Result

<Describe the expected passing result or the exact failure being reproduced.>

Collect Evidence

• Save report.html.
• Export structured results such as JUnit XML or JSON.
• Save relevant application and system logs.
• Save PCAP files only when network evidence is required.
• Record all artifact checksums.

Troubleshooting

|Symptom                 |Check                          |Resolution|
|------------------------|-------------------------------|----------|
|Target unreachable      |Address, VLAN, route           |<action>  |
|Capture is empty        |Interface and capture filter   |<action>  |
|Test collection is empty|Markers and selection arguments|<action>  |

````

---

# Template 7: Artifact Manifest

```markdown
# Artifact Manifest — <Run ID>

## Retention

| Classification | Retention | Delete after |
|---|---|---|
| Qualification evidence | <policy> | <date/never> |
| Debug artifacts | <policy> | <date> |

## Artifacts

| Artifact | Type | Size | Location | SHA-256 | Purpose |
|---|---|---:|---|---|---|
| `report.html` | HTML report | <size> | [View](<URL>) | `<checksum>` | Human-readable pytest results |
| `results.xml` | JUnit XML | <size> | [Download](<URL>) | `<checksum>` | Machine-readable results |
| `traffic.pcapng` | Packet capture | <size> | [Download](<URL>) | `<checksum>` | Network evidence |
| `logs.tar.zst` | Log bundle | <size> | [Download](<URL>) | `<checksum>` | Product and system logs |
| `<image>.wic` | Product image | <size> | [Download](<URL>) | `<checksum>` | Exact build under test |

## Checksum Verification

```bash
sha256sum <downloaded-file>
````

The calculated value must match the value in the table.

````

---

# Template 8: Short Developer Test Report

Use this lighter template for a developer handoff or targeted investigation.

```markdown
# Test Note — <Short Title>

**Date:** <date>  
**Product/build:** <version or commit>  
**Test scope:** <feature/capability>  
**Result:** PASS / FAIL / INCONCLUSIVE

## What Was Tested

<Brief description.>

## Result

<Brief conclusion with actual values where possible.>

## Commands

```bash
<command used>
````

Evidence

• Test report
• Logs
• Packet capture

Follow-Up

☐ <action and owner>
☐ <action and owner>

````

---

# CI Publication Workflow

A useful publication flow is:

1. CI executes pytest and captures structured results.
2. CI generates the run directory and Markdown tables.
3. CI uploads large artifacts to a run-specific immutable Artifactory path.
4. CI calculates SHA-256 checksums.
5. CI inserts Artifactory links and checksums into the Markdown.
6. CI commits the report directory to the test-results Gitea repository.
7. CI optionally opens or updates Gitea issues for new failures.
8. Development and systems reviewers add conclusions or approval decisions.

Example identifiers:

```text
Run ID: product-a_2.4.1_2026-08-27_001
Gitea:  releases/product-a/2.4.1/run-2026-08-27_001/
Artifactory: test-results/product-a/2.4.1/run-2026-08-27_001/
````

Final Recommendation

Start with one Gitea test-results repository and a single consistent run template. Store the Markdown, small sanitized configuration files, and links there. Upload PCAPs, firmware, WIC images, videos, dumps, and large logs to Artifactory. Once the manual structure works well, automate its generation in the pytest/Jenkins pipeline.
