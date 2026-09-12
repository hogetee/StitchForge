# Threadform

A standalone, CPU-only Python 3.12 desktop embroidery application. No cloud, AI, or external digitizing application is required.

## Run

```sh
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m embroidery_app.app
```

Generate proof files: `.venv/bin/python -m embroidery_app.app --proof examples`

Run tests: `.venv/bin/python -m pytest`

Desktop smoke test: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m embroidery_app.app --smoke-test`

## Architecture

The UI handles interaction; image processing produces millimeter polygons; the planner selects deterministic generators; the optimizer orders paths; validation checks the resulting generic commands; the DST adapter writes and reads back the file before replacing the destination. Internal coordinates are millimeters with positive y downward. The adapter alone converts to 0.1 mm DST units.

`embroidery/models.py` owns the design, object, stitch, and command representation. No UI code constructs binary DST data. The exporter uses [pyembroidery](https://github.com/EmbroidePy/pyembroidery), whose documented API supports absolute stitch commands and DST read/write. Export verifies needle coordinates/count, color changes, and END after readback. DST cannot store exact thread RGB values; use the displayed palette when threading the machine.

See [MILESTONES.md](MILESTONES.md) for tested progress and limitations. Digital format validation does not establish fabric quality; physical sew-outs remain required.

## Use the desktop app

On this configured Mac, double-click `Launch.command`, or run `.venv/bin/python -m embroidery_app.app`.

1. Open a PNG/JPG. Drag a rectangle, paint with Brush, click polygon vertices and right-click to close, or click a connected Color region.
2. Use Subtract to remove unwanted areas. Clean mask applies a small open/close filter; Save mask writes a debug PNG. Select all includes the background unless it is transparent.
3. Set output size (selection aspect ratio is maintained by default), maximum colors, row spacing, direction, maximum stitch length, and minimum region area. Smaller row spacing means denser stitching.
4. Choose Auto, Outline, or Fill and click Auto Digitize. Generation runs in a worker while the UI remains responsive. The progress bar reports the current stage, percentage, elapsed time, and an ETA based on completed region work. The estimate becomes more stable after the first planning stage.
5. Inspect stitches, dashed jumps, polygon boundaries, object order and statistics. Adjust and regenerate as needed.
6. Export DST. Review any displayed warnings. The app reads the temporary DST back and verifies it before saving the destination.

For development, `requirements-lock.txt` records the exact dependency versions tested on macOS arm64. Install with `.venv/bin/pip install -r requirements-lock.txt` followed by `.venv/bin/pip install -e . --no-deps`.

## Verification and examples

- 36 automated tests cover DST round trips, geometric containment, planner rules, satin rails, optimizer travel, selection tools, and the complete desktop selection-to-export workflow.
- Auto Digitize progress reports are covered by engine and desktop tests; the UI keeps the final elapsed time visible after completion.
- `examples/` contains square, circle and multiple-color proof DSTs.
- `examples/logos/` contains ten source images, selection masks, DST files, actual readback previews and `verification.json`. Regenerate with `.venv/bin/python scripts/build_examples.py`.
- `examples/workflow-preview.png` shows the desktop running the two-color selection workflow.

See [known limitations](docs/LIMITATIONS.md) before judging sew-out quality. The current implementation has no automatic underlay, tie-offs, or trims; complex satin falls back to fill. It has been digitally verified, not physically sewn.
