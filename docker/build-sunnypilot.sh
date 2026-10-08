#!/usr/bin/env bash
# Full sunnypilot build on Linux: python deps, then scons (includes the panda firmware with the Subaru safety code).
#   bash docker/build-sunnypilot.sh            build everything
#   bash docker/build-sunnypilot.sh --test     build, then run the maneuver tool tests
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export UV_PROJECT_ENVIRONMENT=/opt/venv/sunnypilot
uv sync --frozen --all-extras --quiet
source "$UV_PROJECT_ENVIRONMENT/bin/activate"

# tinygrad compiles the driver monitoring warp models on the CPU through LLVM
export LLVM_PATH="${LLVM_PATH:-$(ls /usr/lib/*/libLLVM*.so* 2>/dev/null | head -n 1)}"

scons -j"$(nproc)"

echo "*** panda firmware"
ls -la panda/board/obj/*.bin* 2>/dev/null || echo "no panda firmware built"

if [[ "$1" == "--test" ]]; then
  python -m unittest -q openpilot.tools.longitudinal_maneuvers.test_maneuver_sets
fi

echo "sunnypilot build finished."
