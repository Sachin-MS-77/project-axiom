"""
rule_engine.py — PROJECT AXIOM

Turns raw evidence from collector.py into verdicts: PASS, FAIL, or UNKNOWN.

This file does NOT run commands and does NOT talk to a target. It only reads
CollectedRecord objects that already exist.

Design note: rules.py currently has no pass_if/fail_if text, so instead of
fuzzy string matching we use one explicit evaluator function per rule_id.
Each evaluator reads the real output and returns a grounded verdict + reason.
Any rule_id without an evaluator defined below returns UNKNOWN and says so —
it never guesses.
"""

# rules.py in its current form doesn't expose a get_rule_by_id() helper, so
# we look rules up directly from RULES instead.
from rules import RULES

_RULES_BY_ID = {r["id"]: r for r in RULES}


class Verdict:
    def __init__(self, rule_id, verdict, evidence, reason, severity, status):
        self.rule_id = rule_id
        self.verdict = verdict        # "PASS", "FAIL", "UNKNOWN"
        self.evidence = evidence      # exact text the verdict is grounded in
        self.reason = reason          # human-readable explanation
        self.severity = severity      # from rules.py, as-is (e.g. "HIGH")
        self.status = status          # original collection status: ok/failed/timeout/refused

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "verdict": self.verdict,
            "evidence": self.evidence,
            "reason": self.reason,
            "severity": self.severity,
            "status": self.status,
        }


# ----------------------------------------------------------------------
# Per-rule evaluators
# Each takes the raw output string and returns (verdict, reason).
# ----------------------------------------------------------------------

def _eval_ssh_root_login(output):
    text = (output or "").strip().lower()
    if not text:
        return "UNKNOWN", "No PermitRootLogin line found in sshd_config output — setting may rely on an unstated default. Needs manual check."
    if "permitrootlogin" in text and "no" in text:
        return "PASS", "PermitRootLogin explicitly set to 'no'."
    if "permitrootlogin" in text and "yes" in text:
        return "FAIL", "PermitRootLogin is explicitly set to 'yes'."
    return "UNKNOWN", f"Line found but value unclear: '{text}'."


def _eval_ssh_password_auth(output):
    text = (output or "").strip().lower()
    if not text:
        return "UNKNOWN", "No PasswordAuthentication line found — setting may rely on an unstated default. Needs manual check."
    if "passwordauthentication" in text and "no" in text:
        return "PASS", "PasswordAuthentication explicitly set to 'no'."
    if "passwordauthentication" in text and "yes" in text:
        return "FAIL", "PasswordAuthentication is explicitly set to 'yes'."
    return "UNKNOWN", f"Line found but value unclear: '{text}'."


def _eval_world_writable_files(output):
    text = (output or "").strip()
    if not text:
        return "PASS", "No world-writable files found under /etc."
    file_count = len([line for line in text.splitlines() if line.strip()])
    return "FAIL", f"{file_count} world-writable file(s) found under /etc, e.g.: {text.splitlines()[0]}"


def _eval_listening_ports(output):
    text = (output or "").strip()
    if not text:
        return "UNKNOWN", "No output returned from 'ss -tuln' — cannot confirm listening state."
    return "UNKNOWN", "Listening ports collected, but no automated pass/fail criteria defined for this check yet — needs manual review of the port list."


def _eval_shadow_file_permissions(output):
    text = (output or "").strip()
    if not text:
        return "UNKNOWN", "/etc/shadow not accessible or stat command returned no output."
    parts = text.split()
    if len(parts) >= 3 and parts[0].isdigit():
        perm_num = int(parts[0])
        if perm_num % 10 != 0:
            return "FAIL", f"/etc/shadow has world permissions set: '{text}'."
        return "PASS", f"/etc/shadow permissions are secure: '{text}'."
    if "----------" in text or "-rw-r-----" in text or "-rw-------" in text:
        return "PASS", f"/etc/shadow file permissions are properly restricted: '{text}'."
    return "UNKNOWN", f"Unrecognized stat output format for /etc/shadow: '{text}'."


def _eval_sudoers_nopasswd(output):
    text = (output or "").strip()
    if not text:
        return "PASS", "No NOPASSWD directives found in /etc/sudoers or /etc/sudoers.d/."
    nopasswd_lines = [l for l in text.splitlines() if "NOPASSWD" in l and not l.strip().startswith("#")]
    if nopasswd_lines:
        return "FAIL", f"{len(nopasswd_lines)} unauthenticated sudo NOPASSWD rule(s) found, e.g.: '{nopasswd_lines[0]}'."
    return "PASS", "No active NOPASSWD directives found in sudoers configuration."


def _eval_empty_password_accounts(output):
    text = (output or "").strip()
    if not text:
        return "PASS", "No user accounts with empty password hashes found in /etc/shadow."
    accounts = [a.strip() for a in text.splitlines() if a.strip()]
    if accounts:
        return "FAIL", f"{len(accounts)} user account(s) have blank/empty passwords: {', '.join(accounts)}."
    return "PASS", "All user accounts have password hashes or locked status in /etc/shadow."


def _eval_outdated_packages(output):
    text = (output or "").strip()
    if not text:
        return "PASS", "Package database reports zero pending upgrades."
    if "0 upgraded, 0 newly installed" in text:
        return "PASS", "System packages are up to date."
    import re
    match = re.search(r'(\d+)\s+upgraded', text)
    if match and int(match.group(1)) > 0:
        return "FAIL", f"{match.group(1)} pending package update(s) found."
    return "UNKNOWN", f"Package update state: '{text}'."


EVALUATORS = {
    "ssh_root_login": _eval_ssh_root_login,
    "ssh_password_auth": _eval_ssh_password_auth,
    "world_writable_files": _eval_world_writable_files,
    "listening_ports": _eval_listening_ports,
    "shadow_file_permissions": _eval_shadow_file_permissions,
    "sudoers_nopasswd": _eval_sudoers_nopasswd,
    "empty_password_accounts": _eval_empty_password_accounts,
    "outdated_packages": _eval_outdated_packages,
}


# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------

def evaluate_all(records):
    """
    records: list of CollectedRecord from collector.py.
    Returns a list of Verdict, one per record, same order as input.
    """
    verdicts = []

    for record in records:
        rule = _RULES_BY_ID.get(record.rule_id)
        severity = rule.get("severity", "UNKNOWN") if rule else "UNKNOWN"

        # If collection itself didn't succeed, we have no real evidence to
        # judge — never fake a PASS or FAIL here.
        if record.status != "ok":
            verdicts.append(
                Verdict(
                    rule_id=record.rule_id,
                    verdict="UNKNOWN",
                    evidence=record.error or "(no output captured)",
                    reason=f"Collection status was '{record.status}', not 'ok' — no reliable evidence to judge.",
                    severity=severity,
                    status=record.status,
                )
            )
            continue

        evaluator = EVALUATORS.get(record.rule_id)
        if evaluator is None:
            verdicts.append(
                Verdict(
                    rule_id=record.rule_id,
                    verdict="UNKNOWN",
                    evidence=record.output or "",
                    reason=f"No evaluator defined for rule '{record.rule_id}' in rule_engine.py — add one before trusting this check.",
                    severity=severity,
                    status=record.status,
                )
            )
            continue

        verdict_label, reason = evaluator(record.output)
        verdicts.append(
            Verdict(
                rule_id=record.rule_id,
                verdict=verdict_label,
                evidence=record.output or "",
                reason=reason,
                severity=severity,
                status=record.status,
            )
        )

    return verdicts


def summarize_verdicts(verdicts):
    """Quick counts for a terminal summary line."""
    return {
        "total": len(verdicts),
        "pass": sum(1 for v in verdicts if v.verdict == "PASS"),
        "fail": sum(1 for v in verdicts if v.verdict == "FAIL"),
        "unknown": sum(1 for v in verdicts if v.verdict == "UNKNOWN"),
    }


# ----------------------------------------------------------------------
# Self-test: confirms verdicts are grounded, not guessed.
# Run directly with: python3 rule_engine.py
# ----------------------------------------------------------------------

if __name__ == "__main__":
    print("Running rule_engine.py self-test (fake records, no live target needed)...\n")

    class FakeRecord:
        def __init__(self, rule_id, status, output, error=None):
            self.rule_id = rule_id
            self.status = status
            self.output = output
            self.error = error

    fake_records = [
        FakeRecord("ssh_root_login", "ok", "PermitRootLogin no"),
        FakeRecord("ssh_password_auth", "ok", "PasswordAuthentication yes"),
        FakeRecord("world_writable_files", "ok", ""),
        FakeRecord("listening_ports", "failed", None, error="Command failed on target."),
    ]

    verdicts = evaluate_all(fake_records)

    expected = ["PASS", "FAIL", "PASS", "UNKNOWN"]
    got = [v.verdict for v in verdicts]

    if got == expected:
        print("PASS: all four verdicts matched expected grounded results.")
        for v in verdicts:
            print(f"  {v.rule_id}: {v.verdict} — {v.reason}")
        print(f"\nSummary: {summarize_verdicts(verdicts)}")
    else:
        print("FAIL: verdicts didn't match expected.")
        print(f"Expected: {expected}")
        print(f"Got:      {got}")