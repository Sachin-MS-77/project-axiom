"""
report.py — PROJECT AXIOM

Takes the full verdict list (rule_engine.py) and the prioritized fix list
(prioritizer.py) and produces one readable Markdown report, plus a short
terminal summary.

This file does NOT connect to a target and does NOT judge anything — it only
formats data it's given. It can be re-run standalone on saved verdict/
priority data, without a live connection, which is deliberate: you should be
able to regenerate a report from a past run at any time.

Extras (posture strip, CEO summary, confidence-receipt hashes, self-audit,
diff mode) are NOT wired in yet — that happens in the next phase, in
extras.py, without needing to touch this file's core structure.
"""

import datetime


def generate_report(verdicts, priority_list, target_info=None, extras=None):
    """
    verdicts: list of Verdict objects from rule_engine.py.
    priority_list: list of PriorityItem objects from prioritizer.py.
    target_info: optional dict, e.g. {"target": "...", "method": "ssh"/"docker"}.
    extras: optional dict, any/all of:
        {
          "posture_strip": str,
          "ceo_summary": str,
          "receipts": {rule_id: hash_str},
          "self_audit": {rule_id, verdict, evidence, reason, severity, status},
          "diff": [{rule_id, old_verdict, new_verdict}, ...],
        }
        Any key can be missing or None — that section is silently skipped.
        This function never raises because of missing/malformed extras data;
        a broken extra must never break the core report.

    Returns the full report as a Markdown string. Does not write to disk —
    call write_report() separately for that.
    """
    target_info = target_info or {}
    extras = extras or {}
    timestamp = datetime.datetime.now(datetime.UTC).isoformat()

    total = len(verdicts)
    pass_count = sum(1 for v in verdicts if v.verdict == "PASS")
    fail_count = sum(1 for v in verdicts if v.verdict == "FAIL")
    unknown_count = sum(1 for v in verdicts if v.verdict == "UNKNOWN")

    lines = []
    lines.append("# PROJECT AXIOM — Audit Report")
    lines.append("")

    # --- Extra: posture strip, right under the title ---
    try:
        strip = extras.get("posture_strip")
        if strip:
            lines.append(f"**Posture at a glance:** {strip}")
            lines.append("")
    except Exception:
        pass

    lines.append(f"- **Target:** {target_info.get('target', 'unspecified')}")
    lines.append(f"- **Connection method:** {target_info.get('method', 'unspecified')}")
    lines.append(f"- **Run timestamp (UTC):** {timestamp}")
    lines.append("")

    # --- Extra: plain-English summary, before the technical summary ---
    try:
        summary_text = extras.get("ceo_summary")
        if summary_text:
            lines.append("## In Plain English")
            lines.append("")
            lines.append(summary_text)
            lines.append("")
    except Exception:
        pass

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total checks: **{total}**")
    lines.append(f"- PASS: **{pass_count}**")
    lines.append(f"- FAIL: **{fail_count}**")
    lines.append(f"- UNKNOWN: **{unknown_count}**")
    lines.append("")

    # --- Extra: self-audit shown as its own called-out line ---
    try:
        self_audit = extras.get("self_audit")
        if self_audit:
            lines.append(
                f"- **Self-audit (AXIOM's own privilege check):** "
                f"{self_audit.get('verdict', 'UNKNOWN')} — {self_audit.get('reason', '')}"
            )
            lines.append("")
    except Exception:
        pass

    # --- Extra: confidence-receipt hashes, added as an extra column ---
    receipts = {}
    try:
        receipts = extras.get("receipts") or {}
    except Exception:
        receipts = {}

    lines.append("## All Checks")
    lines.append("")
    if receipts:
        lines.append("| Rule ID | Verdict | Severity | Reason | Evidence | Receipt |")
        lines.append("|---|---|---|---|---|---|")
    else:
        lines.append("| Rule ID | Verdict | Severity | Reason | Evidence |")
        lines.append("|---|---|---|---|---|")

    for v in verdicts:
        evidence_short = (v.evidence or "").replace("\n", " ").strip()
        if len(evidence_short) > 80:
            evidence_short = evidence_short[:77] + "..."
        reason_short = (v.reason or "").replace("\n", " ").strip()
        if receipts:
            receipt = receipts.get(v.rule_id, "—")
            lines.append(f"| {v.rule_id} | {v.verdict} | {v.severity} | {reason_short} | `{evidence_short}` | `{receipt}` |")
        else:
            lines.append(f"| {v.rule_id} | {v.verdict} | {v.severity} | {reason_short} | `{evidence_short}` |")
    lines.append("")

    lines.append("## Prioritized Fix List")
    lines.append("")
    if not priority_list:
        lines.append("No FAIL items — nothing to prioritize.")
    else:
        lines.append("| Priority | Rule ID | Severity | Fix |")
        lines.append("|---|---|---|---|")
        for i, item in enumerate(priority_list, start=1):
            lines.append(f"| {i} | {item.rule_id} | {item.severity} | {item.fix} |")
    lines.append("")

    # --- Extra: diff mode, only if a previous run was supplied ---
    try:
        diff = extras.get("diff")
        if diff:
            lines.append("## Changes Since Last Run")
            lines.append("")
            lines.append("| Rule ID | Previous Verdict | Current Verdict |")
            lines.append("|---|---|---|")
            for change in diff:
                lines.append(f"| {change['rule_id']} | {change['old_verdict']} | {change['new_verdict']} |")
            lines.append("")
    except Exception:
        pass

    return "\n".join(lines)


def write_report(markdown_text, path="REPORT.md"):
    """Writes the report string to disk. Returns the path written."""
    with open(path, "w") as f:
        f.write(markdown_text)
    return path


def print_short_summary(verdicts):
    """Terminal-friendly one-liner, useful right after a run."""
    total = len(verdicts)
    pass_count = sum(1 for v in verdicts if v.verdict == "PASS")
    fail_count = sum(1 for v in verdicts if v.verdict == "FAIL")
    unknown_count = sum(1 for v in verdicts if v.verdict == "UNKNOWN")
    print(f"AXIOM run complete: {total} checks -> {pass_count} PASS / {fail_count} FAIL / {unknown_count} UNKNOWN")


# ----------------------------------------------------------------------
# Self-test: confirms a full report generates correctly from fake data,
# with no live connection needed.
# Run directly with: python3 report.py
# ----------------------------------------------------------------------

if __name__ == "__main__":
    print("Running report.py self-test (fake verdicts + priority list, no live target needed)...\n")

    class FakeVerdict:
        def __init__(self, rule_id, verdict, severity, evidence="", reason=""):
            self.rule_id = rule_id
            self.verdict = verdict
            self.severity = severity
            self.evidence = evidence
            self.reason = reason

    class FakePriorityItem:
        def __init__(self, rule_id, severity, fix):
            self.rule_id = rule_id
            self.severity = severity
            self.fix = fix

    fake_verdicts = [
        FakeVerdict("ssh_root_login", "PASS", "HIGH", evidence="PermitRootLogin no", reason="set to no"),
        FakeVerdict("ssh_password_auth", "FAIL", "MEDIUM", evidence="PasswordAuthentication yes", reason="set to yes"),
        FakeVerdict("world_writable_files", "FAIL", "HIGH", evidence="/etc/foo.conf", reason="1 file found"),
        FakeVerdict("listening_ports", "UNKNOWN", "LOW", evidence="tcp LISTEN 0 128 *:22", reason="needs manual review"),
    ]

    fake_priority = [
        FakePriorityItem("world_writable_files", "HIGH", "chmod o-w /etc/foo.conf"),
        FakePriorityItem("ssh_password_auth", "MEDIUM", "Set PasswordAuthentication no"),
    ]

    report_text = generate_report(fake_verdicts, fake_priority, target_info={"target": "test-container", "method": "docker"})
    path = write_report(report_text, path="REPORT_selftest.md")

    checks = [
        "# PROJECT AXIOM — Audit Report" in report_text,
        "Total checks: **4**" in report_text,
        "PASS: **1**" in report_text,
        "FAIL: **2**" in report_text,
        "UNKNOWN: **1**" in report_text,
        "world_writable_files" in report_text,
        "chmod o-w /etc/foo.conf" in report_text,
    ]

    if all(checks):
        print(f"PASS: report generated correctly and written to {path}")
        print_short_summary(fake_verdicts)
    else:
        print("FAIL: report content did not match expectations.")
        print(f"Checks: {checks}")