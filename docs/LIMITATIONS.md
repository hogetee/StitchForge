# V1 boundaries

This is a runnable Python desktop V1, not a signed/notarized installer. The included local virtual environment runs on this Mac; install the declared dependencies on other machines. Runtime operations require no network.

- Intended for flat artwork with 1–5 colors. Photos, gradients, intricate tiny text and realistic shading are outside scope.
- Images are orientation-corrected and downsampled to at most 1600 pixels on either side. Transparent pixels cannot be selected. Partial alpha is treated as artwork, not composited into a fabric color.
- Quantization uses deterministic Pillow median cut on selected pixels only. Palette order or reverse palette order is supported; arbitrary manual thread reordering is not yet exposed.
- Contours approximate raster pixel boundaries, with configurable region area filtering and 0.15 mm topology-preserving simplification. Tiny features may disappear. Width and height describe the selected crop; stitch extents may be slightly smaller.
- Running stitches follow polygon boundaries (including holes). The generator accepts arbitrary open polylines, but automatic raster centerline tracing is not implemented.
- Tatami is clipped alternating scanline fill. Unsafe connections across holes or outside concavities use jumps. This can create many travel moves and floating threads. Staggered needle penetration, edge routing, and automatic trims are future improvements.
- Satin uses alternating samples from inferred opposing rails. Automatic satin is restricted to elongated, nearly convex, hole-free columns within the configured maximum stitch length. Any unsafe span falls back to tatami. Branching/curved satin columns and manual rail editing are unsupported.
- Underlay and pull compensation exist in the model but are not generated/applied. No automatic tie-in/tie-off or machine-specific tension/fabric compensation is provided. This is an engineering digitizing V1; physical sew-outs are required to establish embroidery quality.
- Optimization groups color blocks and uses greedy nearest-entry ordering. It reports before/after jump distance; it does not globally minimize travel or remove jumps within fill objects. Automatic trims are not emitted.
- Validation catches missing/invalid/out-of-bounds stitches, maximum-length violations, short stitches, long jumps and dense row settings. It is not a full fabric simulation or hoop collision model. DST quantizes to 0.1 mm; very short segments can collapse after rounding and generate warnings.
- Export verifies needle records and stitch/color-change/end sequence after library normalization. Travel commands may be subdivided by the library. Trim encoding is format-specific and not compared command-for-command. Dimensions in export reports use sewn needle extents, excluding travel.
- DST stores color-change positions, not exact RGB thread colors. Use the UI palette; example verification JSON retains palette information.
- The editor has add/subtract/clear selection, but no undo history or saved editable project format. Settings or mask changes invalidate export until regeneration.
- Output sizes are limited to 300 mm per side, row spacing to at least 0.15 mm, and generated designs to 150,000 commands. These limits keep V1 previews responsive; the UI disables editing during background generation.
