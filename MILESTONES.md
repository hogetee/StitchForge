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
- Implementation: connected desktop workflow, worker thread, live progress/ETA bar, launcher, ten representative fixture sets and documentation.
- Acceptance: complete workflow exercised through Qt controls and saved DST; all ten source/mask/DST/readback sets generated and visually inspected.
- Tests: 37 automated tests pass without warnings; progress callbacks are monotonic and the desktop workflow ends at 100% with elapsed time shown; native macOS startup passes. `examples/logos/verification.json` records generated output checks.
- Limitations: engineering V1 with limitations in `docs/LIMITATIONS.md`; no physical sew-outs, signed packaging, underlay, tie-off or automatic trims.
- Next action: sew representative samples on intended fabric/machine, then prioritize underlay, ties and trims. Editable layer persistence is now implemented in milestone 11.

## 11 — Foreground separation and editable object layers — DONE
- Objective: preserve recognizable parts of shaded artwork, allow correction of each part, and export stitches from those layers.
- Tasks: local foreground extraction; edge-preserving color simplification with dark-detail retention; connected-part layers and editing; layer-aware digitizing with common coordinates; image-based and UI acceptance tests.
- Acceptance: background excluded, face/eye/mouth shapes remain visible on a representative character; user can change masks, colors, names and order; hidden parts excluded; layer project survives save/reopen; DST readback preserves the result.
- Implementation: local GrabCut/alpha foreground extraction; edge-preserving simplification with reserved dark palette seed; connected part masks; name/color/visibility/mode/direction edits, mask painting, merge/reorder/new/delete, undo/redo; portable JSON/PNG layer projects; common-frame vectorization and layer-ordered digitizing. Progress and approximate ETA cover separation and generation.
- Tests: 45 public tests plus one configured private-image test pass (46 total). Tests cover background IoU, eye/mouth recall, deterministic proposals, disjoint masks, common coordinates, layer order/visibility, painting ownership, project roundtrip/rejection, direction overrides, fill-row progress/cancellation, and a complete Qt layer edit/save/reopen/DST workflow. Native macOS project startup succeeds.
- Actual-image acceptance: the raw color-band mode separates the user's monkey image into 40 editable regions across 4 colors. The desktop workflow now merges one lighting/shadow band by default (13 editable parts across 3 materials in the same image), and offers a one-material silhouette mode. Each eye and the smile remain separate protected regions; the outer background and the hole in the hanging loop are excluded. Exported DST has 4,616 stitches and 3 color changes at 80 × 87.32 mm in the raw acceptance run; actual readback preview visually retains the face. Output is local in `output/monkey/`, excluded from Git.
- Limitations: local image-based separation proposes regions; it does not assign guaranteed semantic names such as eye or mouth. Arbitrary photographs may require user correction.
- Remaining limitations: background/semantic ambiguity still needs manual correction; many jumps remain around fragmented regions. No physical sew-out has been performed, and underlay/tie-offs/automatic trims are still absent.
- Next action: physical sew-out and better fill travel routing; general semantic naming would require a separately validated model and dataset.

## 12 — Deterministic industrial planning baseline — IMPLEMENTED, SEW-OUT PENDING

- Corrected the misleading Threadform `.emb` export; retained DST and `.stitchforge`, with recovery of old ZIP packages and explicit rejection of native Wilcom imports.
- Added object roles/provenance, conservative neck decomposition, validated dependency graphs and constrained sequencing.
- Added configurable fabric profiles, per-object directions, underlay, compensation and underlap; staggered tatami, turning-satin inference with fallbacks, bounded travel routes and trim requests.
- Added phase-specific preview, object/layer/type labels, entry/exit/direction overlays and sewing-order playback, plus a ten-case benchmark generator.
- Inspected both supplied native EMB containers locally and extracted their embedded thumbnails. Native stitch/object records remain undecoded; numeric property IDs are unverified.
- Production machine brand supplied by the user: Barudan. Model, needle, material and backing remain unknown. Physical sewing, ties, machine trim compatibility, general lettering decomposition and globally optimal routing are not complete.
- See `docs/INDUSTRIAL_UPGRADE.md` for the implemented scope and remaining acceptance criteria. This milestone does not mark the full industrial specification production-ready.

## Verification notes

The initial native launch inside the execution sandbox was blocked by macOS window services. The same startup check outside the sandbox succeeded with exit 0. Offscreen checks and simulated UI interactions run inside the sandbox. An initial worker test used a polling wait that starved Python work; replacing it with Qt's normal event loop verified the worker completes. Geometry-library numerical warnings were eliminated by using OpenCV's oriented rectangle routine for planning.
