#!/usr/bin/env bash
# Suite COMPLETA: incluye breakpoint, spike y llamadas al LLM (MAX_LLM_REQUESTS).
set -e
cd "$(dirname "$0")/../.."
bash tests/stress/run_safe_suite.sh
python tests/stress/load/run_load.py breakpoint
python tests/stress/load/run_load.py spike
python tests/stress/quality/run_end_to_end_quality.py
python tests/stress/analysis/generate_report.py
