#!/bin/bash
set -e

# Always change directory to the script's directory (project-axiom)
cd "$(dirname "$0")"

# Activate virtual environment if available
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

METHOD="${2:-docker}"

verify_target() {
    local TARGET="$1"
    echo "Running AXIOM determinism check (2 consecutive runs) against '$TARGET' via $METHOD..."

    python3 axiom.py --target "$TARGET" --method "$METHOD" --output run1.md --json run1.json > /dev/null
    python3 axiom.py --target "$TARGET" --method "$METHOD" --output run2.md --json run2.json > /dev/null

    grep -v "Run timestamp" run1.md > run1_clean.md
    grep -v "Run timestamp" run2.md > run2_clean.md

    if diff -q run1_clean.md run2_clean.md > /dev/null; then
        echo "PASS [$TARGET]: identical Markdown reports across two runs (no drift)."
    else
        echo "FAIL [$TARGET]: Markdown results differ between runs."
        diff run1_clean.md run2_clean.md
        exit 1
    fi

    # Also verify JSON determinism (excluding timestamp)
    grep -v '"timestamp":' run1.json > run1_jclean.json
    grep -v '"timestamp":' run2.json > run2_jclean.json

    if diff -q run1_jclean.json run2_jclean.json > /dev/null; then
        echo "PASS [$TARGET]: identical JSON exports across two runs (no drift)."
    else
        echo "FAIL [$TARGET]: JSON exports differ between runs."
        diff run1_jclean.json run2_jclean.json
        exit 1
    fi

    rm -f run1.md run2.md run1_clean.md run2_clean.md run1.json run2.json run1_jclean.json run2_jclean.json
}

if [ -n "$1" ]; then
    verify_target "$1"
else
    verify_target "axiom-clean-target"
    echo ""
    verify_target "axiom-broken-target"
fi

echo ""
echo "OVERALL DRIFT VERIFICATION PASS: All target runs demonstrated 100% determinism."
