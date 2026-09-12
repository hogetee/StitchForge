# Milestone progress

Status vocabulary: NOT STARTED, IN PROGRESS, BLOCKED, DONE. DONE means the acceptance criteria below were exercised; it does not mean production sew-out quality.

## 0 — Repository and Architecture — DONE
- Objective: runnable local Python 3.12 application and separate engine/UI/export layers.
- Implementation: package metadata, pinned tested dependencies, dataclasses, desktop shell, README and test suite; researched pyembroidery's official API.
- Acceptance: native macOS app starts and exits normally; offscreen UI also renders.
- Tests: Python 3.12.14; native `--smoke-test` exit 0; package imports and all tests pass.
- Limitations: source application with launcher; no signed installer.
- Next action: distribution packaging after engine hardening.

## 1 — DST Proof of Concept — DONE
- Objective: internal commands → valid DST → readback → visualization.
- Implementation: square/circle/multiple-color designs; normalized library export, temporary file, verification before replace.
- Acceptance: three DSTs exported, read back and inspected in preview.
- Tests: exact needle count and 0.1 mm coordinate agreement; color/end sequence, dimensions and destination preservation. Square 49 stitches, circle 121, combined 170.
- Limitations: no machine sew-out; DST RGB colors are not retained by the format.
- Next action: physical format compatibility check on intended machine.

## 2 — Image Viewer and Selection — DONE
- Objective: manually select artwork locally.
- Implementation: rectangle, polygon, brush, connected-color selection; add/subtract/clear/select-all; overlay, zoom/pan/fit/reset and PNG mask export.
- Acceptance: selection interactions exercised and exported PNG equals the internal mask.
- Tests: Qt simulated mouse input for each selection tool; complete workflow uses connected selection preserving a hole.
- Limitations: no selection undo; images downsample to 1600 px.
- Next action: add undo and editable project persistence.

## 3 — Raster to Geometry — DONE
- Objective: turn selected colors into clean polygons.
- Implementation: selected-only deterministic quantization, contour hierarchy, hole extraction, valid polygon cleanup, mm scaling and minimum-area filter.
- Acceptance: disconnected components and holes preserved; ten logo outlines inspected with preview.
- Tests: polygon validity, component/hole counts, approximate selected area and ten fixtures.
- Limitations: contour simplification can remove tiny details.
- Next action: improve pixel-cell accuracy and anti-aliased edge handling.

## 4 — Running Stitch — DONE
- Objective: deterministic open/closed path stitches and outline export.
- Implementation: length-bounded segment resampling; outline mode follows exterior/interior rings.
- Acceptance: square/circle running paths export successfully.
- Tests: maximum segment length, endpoints and DST readback.
- Limitations: no inferred raster centerlines; short corner segments can remain.
- Next action: curvature-aware spacing and centerline inference.

## 5 — Tatami Fill — DONE
- Objective: fill selected solid logos while preserving holes.
- Implementation: angled clipped scanlines, alternating traversal, length-bounded stitch rows and containment-aware connections.
- Acceptance: concave and holed artwork fills and exports without stitched segments crossing empty regions.
- Tests: segment containment and maximum length for three geometries at four angles; ten DST fixtures.
- Limitations: many jumps around holes; no underlay/stagger pattern.
- Next action: route around holes and stagger needle positions.

## 6 — Automatic Planner — DONE
- Objective: choose a basic strategy automatically.
- Implementation: centralized configurable width/aspect/convexity rules; Auto/Outline/Fill overrides.
- Acceptance: ten simple logo cases digitize with shared settings.
- Tests: running/fill/satin classifications and safety fallback.
- Limitations: heuristic, no fabric-aware prediction.
- Next action: tune rules against physical sew-outs.

## 7 — Satin Stitch — DONE
- Objective: real two-rail zigzags for simple narrow elements.
- Implementation: infer rail samples from a single column, alternate sides, reject unsafe/overlong spans and fall back to fill.
- Acceptance: narrow rectangular column has alternating rail needle points and exports.
- Tests: rail endpoint alternation, sample count and classification; narrow-column example readback.
- Limitations: curved, branching, holed and wide shapes fall back to tatami.
- Next action: manual rail editing and curved-column inference.

## 8 — Preview and Validation — DONE
- Objective: inspect geometry, needle paths and problems before export.
- Implementation: color stitches, dashed jumps, boundary, polygons and object-order layers; statistics and validation messages; stale export disabled.
- Acceptance: two-color ring selection workflow rendered and visually inspected; errors block export and warnings are shown.
- Tests: invalid/empty/long/dense data; UI export and stale-settings guard; screenshot at `examples/workflow-preview.png`.
- Limitations: no thread simulation, penetration-density heatmap or machine hoop profile.
- Next action: spatial density analysis.

## 9 — Path Optimization — DONE
- Objective: reduce unnecessary inter-object travel and color changes.
- Implementation: group by palette, greedy nearest-entry ordering, retain original order when no color benefit and travel increases; before/after metrics.
- Acceptance: synthetic out-of-order objects show reduced jump distance with identical object membership.
- Tests: measured travel reduction and full pipeline fixture runs.
- Limitations: no global optimization; no automatic trims; intra-object jump count unchanged.
- Next action: better fill traversal and trim policy.

## 10 — Usable V1 — DONE
- Objective: image → manual selection → settings → automatic digitizing → preview → verified DST.
- Implementation: connected desktop workflow, worker thread, launcher, ten representative fixture sets and documentation.
- Acceptance: complete workflow exercised through Qt controls and saved DST; all ten source/mask/DST/readback sets generated and visually inspected.
- Tests: 36 automated tests pass without warnings; native macOS startup passes. `examples/logos/verification.json` records generated output checks.
- Limitations: engineering V1 with limitations in `docs/LIMITATIONS.md`; no physical sew-outs, signed packaging, underlay, tie-off or automatic trims.
- Next action: sew representative samples on intended fabric/machine, then prioritize underlay, ties, trims and project persistence.

## Verification notes

The initial native launch inside the execution sandbox was blocked by macOS window services. The same startup check outside the sandbox succeeded with exit 0. Offscreen checks and simulated UI interactions run inside the sandbox. An initial worker test used a polling wait that starved Python work; replacing it with Qt's normal event loop verified the worker completes. Geometry-library numerical warnings were eliminated by using OpenCV's oriented rectangle routine for planning.
