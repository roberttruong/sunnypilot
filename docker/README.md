# Docker: build and test Subaru Impreza longitudinal

The comma device compiles sunnypilot itself when you install a branch, so Docker isn't needed to run on the car. It's for building and testing on Linux before the branch goes anywhere near the car.

Works with OrbStack or Docker Desktop. Run everything from the repo root.

## Quick tests (about 1 minute after the first run)

Mounts your checkout into the container, so edits are tested immediately. The volumes cache the Python environments between runs.

```bash
docker build -f Dockerfile.subaru-long --target dev -t sunnypilot-subaru-long:dev .
docker run --rm -v "$PWD":/sunnypilot -v sp-venv:/opt/venv -v sp-uvcache:/root/.cache/uv sunnypilot-subaru-long:dev
```

Runs `docker/test-subaru-long.sh`:
- panda safety tests for Subaru (`opendbc/safety/tests/test_subaru.py`), including the restored longitudinal checks
- Subaru car tests, including the feedforward tables (`opendbc/car/subaru/tests/test_longitudinal.py`)
- car interface tests for every Subaru platform
- MISRA static analysis of the safety code (set `-e SKIP_MISRA=1` to skip)

## Full build

Builds all of sunnypilot with scons, including the panda firmware, then runs the maneuver tool tests:

```bash
docker run --rm -v "$PWD":/sunnypilot -v sp-venv:/opt/venv -v sp-uvcache:/root/.cache/uv sunnypilot-subaru-long:dev \
  bash docker/build-sunnypilot.sh --test
```

Or bake a self-contained image, which copies the repo in and builds during `docker build`:

```bash
docker build -f Dockerfile.subaru-long --target build -t sunnypilot-subaru-long .
```

## Maneuver reports

After a maneuver session (see `openpilot/tools/longitudinal_maneuvers/README.md`), with the route uploaded to comma connect:

```bash
docker run --rm -it -v "$PWD":/sunnypilot -v sp-venv:/opt/venv sunnypilot-subaru-long:dev bash -c '
  source /opt/venv/sunnypilot/bin/activate &&
  python openpilot/tools/longitudinal_maneuvers/generate_report.py <route> "new tables" &&
  python openpilot/tools/longitudinal_maneuvers/subaru_report.py <baseline route> <new route> --labels baseline new'
```

Reports are written to `openpilot/tools/longitudinal_maneuvers/longitudinal_reports/`.

## Notes

- The image is native arm64 on Apple Silicon. Add `--platform linux/amd64` to match upstream CI exactly, at the cost of a slower build under emulation.
- Model weights are Git LFS files and aren't needed for these tests. Clone with `GIT_LFS_SKIP_SMUDGE=1` to save space.
