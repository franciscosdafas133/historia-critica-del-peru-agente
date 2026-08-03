#!/usr/bin/env bash
# Suite SEGURA: sin costo de LLM, carga acotada, fail-fast activo.
set -e
cd "$(dirname "$0")/../.."
python tests/stress/quality/build_dataset.py
python tests/stress/load/preflight.py
python tests/stress/quality/run_retrieval_quality.py
python tests/stress/quality/validate_token_packing.py
python tests/stress/resilience/malformed_inputs.py
python tests/stress/resilience/user_isolation.py
python tests/stress/load/run_load.py smoke
python tests/stress/analysis/generate_report.py
