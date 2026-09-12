# Threadform

A standalone, CPU-only Python 3.12 desktop embroidery application. No cloud, AI, or external digitizing application is required.

The desktop now includes an experimental fabric-aware planning pipeline: object
dependencies, per-object underlay, compensation, staggered fill, turning satin
inference, covered travel and sequence playback. See the [upgrade status and limits](docs/INDUSTRIAL_UPGRADE.md).
Choose a fabric in **Stitches**, review its values and test sew before production.
**Save Project** writes editable `.stitchforge`; **Export DST** writes machine
stitches. Native Wilcom EMB is not supported. The earlier misleading EMB export
has been removed; Open Project can recover the old Threadform ZIP packages.

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
3. Set output size (selection aspect ratio is maintained by default), fabric, row spacing, direction, maximum stitch length, and minimum region area. Review compensation, underlap, underlay and stagger values. Smaller row spacing means denser stitching. Fabric presets are uncalibrated starting points for test sewing.
4. Choose Auto, Outline, or Fill and click Auto Digitize. Generation runs in a worker while the UI remains responsive. The progress bar reports the current stage, percentage, elapsed time, and an ETA based on completed region work. The estimate becomes more stable after the first planning stage.
5. Inspect top stitches, underlay, travel, dashed jumps, trims, boundaries, directions and entry/exit markers. Play/Pause and the slider show sewing order. Adjust and regenerate as needed.
6. Export DST. Review any displayed warnings. The app reads the temporary DST back and verifies it before saving the destination. During separation or digitizing, the Cancel button stops after the current GrabCut pass or fill row and keeps the previous preview.

## Separate shaded artwork into editable parts

1. In **Select**, open the image and optionally draw a loose rectangle around the object. With no selection, separation uses the full image. Leave some background margin around opaque objects.
2. Choose 3–5 **Separation colors**, leave **Remove background** and **Preserve dark details** enabled, and click **Separate into layers**. Transparent images use their alpha mask. Turn off background removal to use a carefully drawn foreground mask as-is.
3. Review the simplified artwork. **Layers** lists connected parts, with dark details kept as distinct parts where possible. Each row is one proposed object part and its swatch is the proposed thread color; the algorithm does not automatically know names such as eye, ear, or mouth. Double-click a part's name to rename it.
4. Select a part, then use Brush/Polygon in **Select** to correct its mask. Painting claims pixels from other parts; subtracting leaves empty fabric. **Pick layer** lets you click a part on the canvas. **Edit foreground selection** switches back to the overall object mask. Changing overall selection clips existing parts and creates an Added foreground part for newly included pixels.
5. Change part color, strategy or direction; toggle its checkbox to include/exclude it from DST. To inspect the masks, select a row and click **Show selected**, then click **Show all** to restore the composite view. **Group by color** combines separate parts with the same color into one color layer; Undo restores the object parts. Use Up/Down to set sewing order, Cmd/Ctrl-select parts and Merge to combine them, or New part to paint a separate feature. Undo/Redo applies to layer edits (up to 20 steps, bounded by memory).
6. In **Stitches**, set physical size and stitch settings, then **Auto Digitize**. Checked layers share one coordinate system and preserve the chosen layer order. Hidden layers do not change the scale of remaining features. Small protected details use a lower area threshold; omitted layers are listed in the result.
7. **Save Project** stores the source, masks, colors, names, order and settings in an editable `.stitchforge` file. **Open Project** restores them; regenerate the preview before export. Exact RGB colors live in the project, because DST itself does not store them.

Jumps are hidden by default so they do not obscure the face; enable Jumps to inspect travel. Segmentation and digitizing have progress/elapsed/approximate ETA displays. Stage weights estimate remaining work; ETA is not a completion-time guarantee, especially during one expensive region.

Open a saved project with `.venv/bin/python -m embroidery_app.app --project path/to/artwork.stitchforge --digitize`.

Run a local image acceptance export with `.venv/bin/python scripts/digitize_layers.py "image.png" output/review`. It writes an editable project, foreground mask, simplified artwork, DST, actual DST readback preview and verification report. `output/` is ignored by Git so private images and derivatives stay local.

Foreground extraction uses the local [OpenCV GrabCut mask API](https://docs.opencv.org/4.12.0/dd/dfc/tutorial_js_grabcut.html). Edge-preserving smoothing, deterministic color clustering with a reserved dark-detail seed, and connected components produce the editable parts. No model download or cloud service is required.

For development, `requirements-lock.txt` records the exact dependency versions tested on macOS arm64. Install with `.venv/bin/pip install -r requirements-lock.txt` followed by `.venv/bin/pip install -e . --no-deps`.

## Verification and examples

- Automated tests cover DST round trips, geometry containment, dependencies and cycles, decomposition coverage, turning satin, underlay order, compensation, stagger, covered routing, fabric persistence, legacy project recovery and desktop workflows.
- An additional private-image acceptance test runs when `STITCHFORGE_MONKEY_IMAGE` points to the user's original monkey image. It verifies removed background, separate dark eye/mouth regions and nearby dark needle points in the exported DST.
- Auto Digitize progress reports are covered by engine and desktop tests; the UI keeps the final elapsed time visible after completion.
- `examples/` contains square, circle and multiple-color proof DSTs.
- `examples/logos/` contains ten source images, selection masks, DST files, actual readback previews and `verification.json`. Regenerate with `.venv/bin/python scripts/build_examples.py`.
- `examples/workflow-preview.png` shows the desktop running the two-color selection workflow.

Run `.venv/bin/python scripts/benchmark_planning.py` to generate ten planning benchmark cases with vectors, object plans, sequence, preview, editable project, DST and metrics under `output/planning-benchmark/`.

See [known limitations](docs/LIMITATIONS.md) before judging sew-out quality. Planned mode generates underlay and trim requests; automatic tie-offs and machine-specific trim execution are not verified. Difficult satin/lettering falls back to fill. The upgrade has been digitally tested, not physically sewn.
