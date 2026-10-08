#!/usr/bin/env bash
# Set up opendbc's environment and run the Subaru longitudinal tests.
#   bash docker/test-subaru-long.sh               setup + tests
#   bash docker/test-subaru-long.sh --setup-only  setup only
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/opendbc_repo"

# keep the venv outside the source tree so a bind-mounted checkout stays clean
export UV_PROJECT_ENVIRONMENT=/opt/venv/opendbc
export PYTHONPATH="$ROOT/opendbc_repo"
uv sync --all-extras --all-groups --inexact --quiet
source "$UV_PROJECT_ENVIRONMENT/bin/activate"

if [[ "$1" == "--setup-only" ]]; then
  exit 0
fi

echo "*** panda safety: subaru"
python -m unittest -q opendbc.safety.tests.test_subaru

echo "*** car: subaru"
python -m unittest -q opendbc.car.subaru.tests.test_subaru opendbc.car.subaru.tests.test_longitudinal

echo "*** car interfaces: subaru"
python -m unittest -q -k SUBARU opendbc.car.tests.test_car_interfaces

echo "*** safety static analysis (MISRA)"
if [[ -n "$SKIP_MISRA" ]]; then
  echo "skipped (SKIP_MISRA set)"
else
  opendbc/safety/tests/misra/test_misra.sh
fi

echo "All Subaru longitudinal tests passed."
