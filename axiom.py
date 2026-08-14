"""
axiom.py — PROJECT AXIOM
The command-line entry point. Wires together:
  connector -> collector -> rule_engine -> prioritizer -> report

Usage:
  python3 axiom.py --target axiom-clean-target --method docker
  python3 axiom.py --target 192.168.1.50 --method ssh --username root --key-path ~/.ssh/id_rsa
  python3 axiom.py --target 192.168.1.50 --method ssh --username root --password mypass

Safety contract:
  - This file does not run any command itself. It only calls connector.run(),
    which enforces the allowlist. Nothing here can bypass that.
  - Any unexpected failure at any stage is caught, logged with which stage
    failed, and exits cleanly. It never produces a fake/guessed result just
    to avoid printing an error.
"""

import argparse
import datetime
import json
import os
import sys

from connector import Connector
from collector import collect_all
from rule_engine import evaluate_all, summarize_verdicts
from prioritizer import build_priority_list
from report import generate_report, write_report, print_short_summary
from extras import posture_strip, ceo_summary, confidence_receipts, self_audit_check


def parse_args():
    parser = argparse.ArgumentParser(description="PROJECT AXIOM — read-only security audit tool")
    parser.add_argument("--target", required=True, help="Hostname/IP (ssh) or container name (docker)")
    parser.add_argument("--method", required=True, choices=["ssh", "docker"], help="Connection method")
    parser.add_argument("--username", help="SSH username (required for --method ssh)")
    parser.add_argument("--key-path", help="SSH private key path (ssh only)")
    parser.add_argument("--password", help="SSH password (ssh only, used if --key-path not given)")
    parser.add_argument("--port", type=int, default=22, help="SSH port (default 22)")
    parser.add_argument("--output", default="REPORT.md", help="Path to write the report (default REPORT.md)")
    parser.add_argument("--json", help="Optional path to write structured JSON export (e.g. REPORT.json)")
    return parser.parse_args()


def run():
    args = parse_args()

    connector_kwargs = {}
    if args.method == "ssh":
        if not args.username:
            print("STAGE FAILED: argument parsing — SSH requires --username.")
            sys.exit(1)
        connector_kwargs["username"] = args.username
        connector_kwargs["port"] = args.port
        if args.key_path:
            connector_kwargs["key_path"] = args.key_path
        elif args.password:
            connector_kwargs["password"] = args.password
        else:
            print("STAGE FAILED: argument parsing — SSH requires --key-path or --password.")
            sys.exit(1)

    print(f"[1/5] Connecting to '{args.target}' via {args.method}...")
    connector = Connector(method=args.method, target=args.target, **connector_kwargs)
    try:
        ok, err = connector.connect()
    except Exception as e:
        print(f"STAGE FAILED: connect — unexpected exception: {e}")
        sys.exit(1)

    if not ok:
        print(f"STAGE FAILED: connect — {err}")
        sys.exit(1)
    print("      connected.")

    print("[2/5] Running approved checks and collecting evidence...")
    try:
        records = collect_all(connector)
    except Exception as e:
        print(f"STAGE FAILED: collect — unexpected exception: {e}")
        connector.close()
        sys.exit(1)
    print(f"      {len(records)} checks collected.")

    print("[3/5] Evaluating verdicts (PASS/FAIL/UNKNOWN)...")
    try:
        verdicts = evaluate_all(records)
    except Exception as e:
        print(f"STAGE FAILED: evaluate — unexpected exception: {e}")
        connector.close()
        sys.exit(1)

    print("[4/5] Building prioritized fix list...")
    try:
        priority = build_priority_list(verdicts)
    except Exception as e:
        print(f"STAGE FAILED: prioritize — unexpected exception: {e}")
        connector.close()
        sys.exit(1)

    # Extras are best-effort: each one is wrapped so a single broken extra
    # never stops the report from being generated.
    extras_data = {}
    try:
        extras_data["posture_strip"] = posture_strip(verdicts)
    except Exception:
        pass
    try:
        extras_data["ceo_summary"] = ceo_summary(verdicts)
    except Exception:
        pass
    try:
        extras_data["receipts"] = confidence_receipts(verdicts)
    except Exception:
        pass
    try:
        extras_data["self_audit"] = self_audit_check(connector)
    except Exception:
        pass

    print("[5/5] Generating report...")
    try:
        report_text = generate_report(
            verdicts, priority,
            target_info={"target": args.target, "method": args.method},
            extras=extras_data,
        )
        write_report(report_text, path=args.output)

        # Always build structured export (used by dashboard + optional --json flag)
        summary = summarize_verdicts(verdicts)
        json_export = {
            "metadata": {
                "target": args.target,
                "method": args.method,
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                "total_checks": summary["total"],
                "pass_count": summary["pass"],
                "fail_count": summary["fail"],
                "unknown_count": summary["unknown"],
            },
            "posture_strip": extras_data.get("posture_strip", ""),
            "ceo_summary": extras_data.get("ceo_summary", ""),
            "self_audit": extras_data.get("self_audit", {}),
            "verdicts": [v.to_dict() for v in verdicts],
            "priority_list": [p.to_dict() for p in priority],
            "receipts": extras_data.get("receipts", {}),
        }

        # Always write report_data.js so dashboard.html auto-loads without upload
        report_dir = os.path.dirname(os.path.abspath(args.output))
        js_path = os.path.join(report_dir, "report_data.js")
        with open(js_path, "w") as f:
            f.write("// Auto-generated by axiom.py — do not edit manually\n")
            f.write("window.AXIOM_AUTOLOAD = ")
            json.dump(json_export, f, indent=2)
            f.write(";\n")

        if args.json:
            with open(args.json, "w") as f:
                json.dump(json_export, f, indent=2)
    except Exception as e:
        print(f"STAGE FAILED: report — unexpected exception: {e}")
        connector.close()
        sys.exit(1)

    connector.close()

    print()
    print_short_summary(verdicts)
    print(f"Report written to: {args.output}")
    print(f"Dashboard data:    {js_path}  (open index.html to view)")
    if args.json:
        print(f"JSON export:       {args.json}")


if __name__ == "__main__":
    run()