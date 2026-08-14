"""
extras.py — PROJECT AXIOM

The differentiator features from the plan's Section 5:
  1. posture_strip        — one line of colored blocks, overall health at a glance
  2. ceo_summary           — one plain-English paragraph, zero jargon
  3. confidence_receipts    — short hash per finding, independently re-checkable
  4. self_audit_check      — the tool checks its own connection's privilege level
  5. diff_runs             — compares two saved verdict runs, shows what changed

Every function here is independent and defensive: if one fails, it must
never take down the others or the core report. report.py calls these
optionally — if any of them raises or returns nothing, the report still
generates normally without that section.
"""

import hashlib


# ----------------------------------------------------------------------
# 1. Visual posture strip
# ----------------------------------------------------------------------

_BLOCK = {
    "PASS": "\U0001F7E9",     # green square
    "FAIL": "\U0001F7E5",     # red square
    "UNKNOWN": "\U0001F7E8",  # yellow square
}


def posture_strip(verdicts):
    """
    Returns one line of colored blocks, one per verdict, in the same order
    as verdicts. Never raises — any unexpected verdict value falls back to
    a neutral block instead of crashing the whole report.
    """
    try:
        return "".join(_BLOCK.get(v.verdict, "\u2b1c") for v in verdicts)
    except Exception:
        return ""  # report.py must treat an empty string as "skip this section"


# ----------------------------------------------------------------------
# 2. Plain-English "CEO" summary
# ----------------------------------------------------------------------

def ceo_summary(verdicts):
    """
    Returns one non-technical paragraph describing the overall finding.
    Grounded only in counts and severities already computed — never
    invents specifics beyond what verdicts actually show.
    """
    try:
        total = len(verdicts)
        fails = [v for v in verdicts if v.verdict == "FAIL"]
        unknowns = [v for v in verdicts if v.verdict == "UNKNOWN"]

        if not fails and not unknowns:
            return f"We checked {total} things on this server, and everything passed. No action needed right now."

        high_sev_fails = [v for v in fails if (v.severity or "").upper() in ("CRITICAL", "HIGH")]

        parts = [f"We checked {total} things on this server."]

        if high_sev_fails:
            names = ", ".join(v.rule_id.replace("_", " ") for v in high_sev_fails[:3])
            parts.append(f"{len(high_sev_fails)} serious issue(s) need attention soon, including: {names}.")
        elif fails:
            parts.append(f"{len(fails)} issue(s) were found, none of the most severe kind, but still worth fixing.")

        if unknowns:
            parts.append(f"{len(unknowns)} check(s) couldn't be automatically confirmed and need a human to look, rather than being guessed.")

        parts.append("See the prioritized fix list below for exact next steps.")
        return " ".join(parts)
    except Exception:
        return ""  # report.py skips this section if empty


# ----------------------------------------------------------------------
# 3. Confidence-receipt hashes
# ----------------------------------------------------------------------

def confidence_receipts(verdicts):
    """
    Returns {rule_id: short_hash}. Each hash is computed over
    (rule_id + verdict + evidence), so anyone can independently re-run
    that one check and recompute the same hash to verify nothing was
    altered after the fact.
    """
    receipts = {}
    for v in verdicts:
        try:
            raw = f"{v.rule_id}|{v.verdict}|{v.evidence or ''}".encode("utf-8")
            receipts[v.rule_id] = hashlib.sha256(raw).hexdigest()[:10]
        except Exception:
            receipts[v.rule_id] = "unavailable"
    return receipts


def verify_receipt(verdict, expected_hash):
    """
    Independently re-checks a single verdict against a previously issued
    hash. Returns True/False. This is what a judge or teammate would run
    to prove a specific finding wasn't altered after the report was made.
    """
    try:
        raw = f"{verdict.rule_id}|{verdict.verdict}|{verdict.evidence or ''}".encode("utf-8")
        actual = hashlib.sha256(raw).hexdigest()[:10]
        return actual == expected_hash
    except Exception:
        return False


# ----------------------------------------------------------------------
# 4. Self-audit: does AXIOM itself have more privilege than it needs?
# ----------------------------------------------------------------------

def self_audit_check(connector):
    """
    Runs one extra read-only check against the connector's own session:
    confirms the connecting identity isn't root/admin. Returns a dict
    shaped like a normal verdict so it can be dropped straight into the
    verdicts list if desired. Never raises — any failure here becomes
    UNKNOWN, exactly like every other ungrounded result in this project.
    """
    try:
        if connector.method == "ssh":
            username = connector.kwargs.get("username", "")
            if not username:
                return _self_audit_result("UNKNOWN", "", "No username recorded for this session.")
            if username.lower() in ("root", "admin", "administrator"):
                return _self_audit_result("FAIL", username, f"AXIOM connected as privileged user '{username}'.")
            return _self_audit_result("PASS", username, f"AXIOM connected as non-privileged user '{username}'.")

        elif connector.method == "docker":
            # docker exec_run defaults to the container's default user unless
            # overridden; we check it directly rather than assuming.
            result = connector._docker_container.exec_run(["sh", "-c", "whoami"])
            whoami = result.output.decode(errors="replace").strip()
            if whoami in ("root", "admin"):
                return _self_audit_result("FAIL", whoami, f"AXIOM's docker exec session is running as '{whoami}'.")
            return _self_audit_result("PASS", whoami, f"AXIOM's docker exec session is running as non-root user '{whoami}'.")

        return _self_audit_result("UNKNOWN", "", f"Unknown connection method '{connector.method}'.")
    except Exception as e:
        return _self_audit_result("UNKNOWN", "", f"Self-audit check failed to run: {e}")


def _self_audit_result(verdict, evidence, reason):
    return {
        "rule_id": "axiom_self_privilege_check",
        "verdict": verdict,
        "evidence": evidence,
        "reason": reason,
        "severity": "HIGH",
        "status": "ok" if verdict != "UNKNOWN" else "failed",
    }


# ----------------------------------------------------------------------
# 5. Diff mode — compare two saved verdict runs
# ----------------------------------------------------------------------

def diff_runs(old_verdicts, new_verdicts):
    """
    old_verdicts, new_verdicts: lists of objects with .rule_id and .verdict
    (Verdict objects from rule_engine.py, or dict-like equivalents).

    Returns a list of {rule_id, old_verdict, new_verdict} for every rule
    whose verdict changed between the two runs. Rules present in only one
    run are reported with the missing side as "not run".
    """
    def to_map(verdicts):
        result = {}
        for v in verdicts:
            rule_id = v.rule_id if hasattr(v, "rule_id") else v.get("rule_id")
            verdict = v.verdict if hasattr(v, "verdict") else v.get("verdict")
            result[rule_id] = verdict
        return result

    try:
        old_map = to_map(old_verdicts)
        new_map = to_map(new_verdicts)
        all_ids = sorted(set(old_map.keys()) | set(new_map.keys()))

        changes = []
        for rule_id in all_ids:
            old_v = old_map.get(rule_id, "not run")
            new_v = new_map.get(rule_id, "not run")
            if old_v != new_v:
                changes.append({"rule_id": rule_id, "old_verdict": old_v, "new_verdict": new_v})
        return changes
    except Exception:
        return []


# ----------------------------------------------------------------------
# Self-test: exercises every function independently, confirms none of
# them raise even with imperfect/edge-case input.
# Run directly with: python3 extras.py
# ----------------------------------------------------------------------

if __name__ == "__main__":
    print("Running extras.py self-test (all five features, no live target needed)...\n")

    class FakeVerdict:
        def __init__(self, rule_id, verdict, severity, evidence=""):
            self.rule_id = rule_id
            self.verdict = verdict
            self.severity = severity
            self.evidence = evidence

    fake_verdicts = [
        FakeVerdict("ssh_root_login", "PASS", "HIGH", "PermitRootLogin no"),
        FakeVerdict("ssh_password_auth", "FAIL", "MEDIUM", "PasswordAuthentication yes"),
        FakeVerdict("world_writable_files", "FAIL", "HIGH", "/etc/foo.conf"),
        FakeVerdict("listening_ports", "UNKNOWN", "LOW", "tcp LISTEN 0 128 *:22"),
    ]

    strip = posture_strip(fake_verdicts)
    summary = ceo_summary(fake_verdicts)
    receipts = confidence_receipts(fake_verdicts)
    receipt_check = verify_receipt(fake_verdicts[0], receipts["ssh_root_login"])
    bad_receipt_check = verify_receipt(fake_verdicts[0], "0000000000")

    old_run = [FakeVerdict("ssh_password_auth", "FAIL", "MEDIUM")]
    new_run = [FakeVerdict("ssh_password_auth", "PASS", "MEDIUM")]
    diff = diff_runs(old_run, new_run)

    checks = [
        len(strip) > 0,
        len(summary) > 0,
        len(receipts) == 4,
        receipt_check is True,
        bad_receipt_check is False,
        len(diff) == 1 and diff[0]["old_verdict"] == "FAIL" and diff[0]["new_verdict"] == "PASS",
    ]

    if all(checks):
        print(f"PASS: all five extras ran cleanly.\n")
        print(f"Posture strip: {strip}")
        print(f"CEO summary: {summary}")
        print(f"Receipts: {receipts}")
        print(f"Receipt self-check (should verify): {receipt_check}")
        print(f"Receipt self-check with wrong hash (should fail): {bad_receipt_check}")
        print(f"Diff mode: {diff}")
    else:
        print("FAIL: one or more extras did not behave as expected.")
        print(f"Checks: {checks}")