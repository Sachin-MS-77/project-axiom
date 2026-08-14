"""
prioritizer.py — PROJECT AXIOM

Takes verdicts from rule_engine.py, filters to the ones that need action,
sorts them deterministically by severity, and attaches a fix instruction.

Design note: rules.py currently has no 'fix' field, so fixes are defined
here in FIXES, keyed by rule_id — same pattern as rule_engine.py's
evaluators. Any rule_id without a fix defined returns a clear placeholder,
never a guessed instruction.
"""

# Severity order, highest priority first. rules.py currently uses uppercase
# labels (HIGH/MEDIUM/LOW) with no CRITICAL tier yet — CRITICAL is included
# here so it works automatically if the team adds it later.
SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

FIXES = {
    "ssh_root_login": "Set 'PermitRootLogin no' in /etc/ssh/sshd_config, then restart sshd.",
    "ssh_password_auth": "Set 'PasswordAuthentication no' in /etc/ssh/sshd_config and require key-based auth, then restart sshd.",
    "world_writable_files": "Remove world-write permission on each flagged file: chmod o-w <file>.",
    "listening_ports": "Review the listed ports manually and close/firewall any that aren't expected to be open.",
    "shadow_file_permissions": "Restrict permissions on /etc/shadow: chmod 640 /etc/shadow && chown root:shadow /etc/shadow.",
    "sudoers_nopasswd": "Remove NOPASSWD directives from /etc/sudoers and /etc/sudoers.d/ configuration files.",
    "empty_password_accounts": "Set a secure password or lock blank account(s) using passwd -l <user>.",
    "outdated_packages": "Apply security updates: apt-get update && apt-get upgrade -y.",
}


class PriorityItem:
    def __init__(self, rule_id, severity, verdict, evidence, reason, fix):
        self.rule_id = rule_id
        self.severity = severity
        self.verdict = verdict
        self.evidence = evidence
        self.reason = reason
        self.fix = fix

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "verdict": self.verdict,
            "evidence": self.evidence,
            "reason": self.reason,
            "fix": self.fix,
        }


def _severity_rank(severity):
    """Lower number = higher priority. Unknown severities sort last."""
    severity = (severity or "").upper()
    if severity in SEVERITY_ORDER:
        return SEVERITY_ORDER.index(severity)
    return len(SEVERITY_ORDER)


def build_priority_list(verdicts, include_unknown=False):
    """
    verdicts: list of Verdict objects from rule_engine.py.
    include_unknown: if True, UNKNOWN verdicts are included (clearly
        separated from FAIL, never merged into the same severity ranking
        logic without being labeled).

    Returns a list of PriorityItem, deterministically ordered:
    severity first (CRITICAL > HIGH > MEDIUM > LOW > unrecognized),
    then rule_id alphabetically as a fixed tiebreaker.

    Same input always produces the same output order — no randomness,
    no reliance on dict/set iteration order.
    """
    targets = [v for v in verdicts if v.verdict == "FAIL"]
    if include_unknown:
        targets += [v for v in verdicts if v.verdict == "UNKNOWN"]

    targets.sort(key=lambda v: (_severity_rank(v.severity), v.rule_id))

    priority_list = []
    for v in targets:
        fix = FIXES.get(v.rule_id, f"No fix defined yet for '{v.rule_id}' — add one to prioritizer.py's FIXES dict.")
        priority_list.append(
            PriorityItem(
                rule_id=v.rule_id,
                severity=v.severity,
                verdict=v.verdict,
                evidence=v.evidence,
                reason=v.reason,
                fix=fix,
            )
        )

    return priority_list


# ----------------------------------------------------------------------
# Self-test: confirms deterministic ordering (same input -> same output,
# every time, run twice).
# Run directly with: python3 prioritizer.py
# ----------------------------------------------------------------------

if __name__ == "__main__":
    print("Running prioritizer.py self-test (fake verdicts, no live target needed)...\n")

    class FakeVerdict:
        def __init__(self, rule_id, verdict, severity, evidence="", reason=""):
            self.rule_id = rule_id
            self.verdict = verdict
            self.severity = severity
            self.evidence = evidence
            self.reason = reason

    fake_verdicts = [
        FakeVerdict("world_writable_files", "FAIL", "HIGH", reason="2 files found"),
        FakeVerdict("ssh_password_auth", "FAIL", "MEDIUM", reason="set to yes"),
        FakeVerdict("ssh_root_login", "PASS", "HIGH", reason="set to no"),
        FakeVerdict("listening_ports", "UNKNOWN", "LOW", reason="needs manual review"),
    ]

    run_1 = [item.rule_id for item in build_priority_list(fake_verdicts)]
    run_2 = [item.rule_id for item in build_priority_list(fake_verdicts)]

    expected_order = ["world_writable_files", "ssh_password_auth"]  # HIGH before MEDIUM, PASS excluded

    if run_1 == run_2 == expected_order:
        print(f"PASS: priority order is deterministic and correct: {run_1}")
        for item in build_priority_list(fake_verdicts):
            print(f"  [{item.severity}] {item.rule_id} -> {item.fix}")
    else:
        print("FAIL: ordering was not deterministic or not correctly severity-sorted.")
        print(f"run_1={run_1}")
        print(f"run_2={run_2}")
        print(f"expected={expected_order}")