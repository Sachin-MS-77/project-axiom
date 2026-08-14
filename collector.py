"""
collector.py — PROJECT AXIOM

Runs through every rule in rules.py, one at a time, through an already-open
Connector's guarded run() method — and records exactly what came back.

This file makes NO pass/fail judgment. It only collects raw evidence.
That decision belongs entirely to rule_engine.py.

Safety contract:
  - Never calls anything on the target except through Connector.run(), which
    already enforces the allowlist. This file does not add or bypass that.
  - One rule's failure/timeout/error must never stop the rest of the run.
"""

import datetime

from rules import RULES


class CollectedRecord:
    """One rule's full evidence record."""

    def __init__(self, rule_id, command, status, output, error, timestamp):
        self.rule_id = rule_id
        self.command = command
        self.status = status          # "ok", "failed", "timeout", "refused"
        self.output = output
        self.error = error
        self.timestamp = timestamp

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "command": self.command,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "timestamp": self.timestamp,
        }


def collect_all(connector, rules=None):
    """
    connector: an already-connected Connector instance (connector.py).
    rules: optional override list of rule dicts; defaults to the full RULES list.

    Returns a list of CollectedRecord, one per rule, in the same order as
    rules.py. Never raises — any per-rule problem is captured in that
    record's status/error fields and the loop continues.
    """
    if rules is None:
        rules = RULES

    records = []

    for rule in rules:
        rule_id = rule["id"]
        timestamp = datetime.datetime.now(datetime.UTC).isoformat()

        try:
            result = connector.run(rule_id)
        except Exception as e:
            # Defensive catch-all: connector.run() is designed to never raise,
            # but if something unexpected slips through, don't let it kill
            # the rest of the collection run.
            records.append(
                CollectedRecord(
                    rule_id=rule_id,
                    command=rule.get("command"),
                    status="failed",
                    output=None,
                    error=f"Unexpected exception during collection: {e}",
                    timestamp=timestamp,
                )
            )
            continue

        if not result.success:
            if result.error and "REFUSED" in result.error:
                status = "refused"
            elif result.error and "timed out" in result.error.lower():
                status = "timeout"
            else:
                status = "failed"
        else:
            status = "ok"

        records.append(
            CollectedRecord(
                rule_id=result.rule_id,
                command=result.command,
                status=status,
                output=result.output,
                error=result.error,
                timestamp=timestamp,
            )
        )

    return records


def summarize_collection(records):
    """Quick counts, useful for a terminal progress line while collecting."""
    total = len(records)
    ok = sum(1 for r in records if r.status == "ok")
    failed = sum(1 for r in records if r.status in ("failed", "timeout", "refused"))
    return {"total": total, "ok": ok, "failed": failed}


# ----------------------------------------------------------------------
# Self-test: confirms one broken rule doesn't stop the whole collection.
# Run directly with: python3 collector.py
# (Uses a fake connector, no live target needed.)
# ----------------------------------------------------------------------

if __name__ == "__main__":
    print("Running collector.py self-test (fake connector, no live target needed)...\n")

    class FakeResult:
        def __init__(self, rule_id, command, success, output, error=None):
            self.rule_id = rule_id
            self.command = command
            self.success = success
            self.output = output
            self.error = error

    class FakeConnector:
        """Simulates: every rule succeeds except one, which times out."""

        def run(self, rule_id):
            if rule_id == RULES[0]["id"]:
                return FakeResult(rule_id, RULES[0]["command"], success=False, output=None, error="Command timed out.")
            return FakeResult(rule_id, "fake-command", success=True, output="fake output")

    fake = FakeConnector()
    records = collect_all(fake)

    expected_count = len(RULES)
    got_count = len(records)
    first_status_ok = records[0].status == "timeout"
    rest_ok = all(r.status == "ok" for r in records[1:])

    if got_count == expected_count and first_status_ok and rest_ok:
        print(f"PASS: collected {got_count}/{expected_count} records.")
        print(f"First rule correctly marked '{records[0].status}', run continued past it.")
        print(f"Summary: {summarize_collection(records)}")
    else:
        print("FAIL: collection did not behave as expected.")
        print(f"got_count={got_count}, expected={expected_count}, "
              f"first_status={records[0].status}, rest_ok={rest_ok}")