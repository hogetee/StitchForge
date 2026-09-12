# Digitizing planning upgrade

This is a deterministic planning baseline, not a claim of production readiness.
The user's specification prioritizes object planning over replacing the working
DST writer. Native Wilcom EMB import/export is not implemented.

## Implemented pipeline

Artwork selection → segmentation → vectors in mm → conservative object
decomposition → fabric/direction/underlay/compensation planning → dependency
graph → valid sewing sequence → entry selection → underlay and top generators
→ covered travel or jump/trim → validation → existing verified DST export.

| Specification phase | Implemented | Limits requiring further work |
| --- | --- | --- |
| 1: Model | Object provenance, roles, layers, rails, underlay types, dependencies, phase-tagged stitches, plan and fabric profiles | Native Wilcom properties are not decoded |
| 2: Sequence | Before/after edges, duplicate/missing/self/cycle checks; layer order is a hard constraint | Roles are user-provided or geometric heuristics, not semantic recognition |
| 3: Entry/travel | Rotate initial closed contours, reverse safe continuous paths, visibility routes, future-object coverage, distance-based trims | No globally optimal joint entry/exit solution; thread coverage is a geometric approximation |
| 4: Tatami | Rotated clipped rows, holes/islands, alternating rows, global stagger phase, constrained internal detours, sparse perpendicular underlay | Some complicated regions still require many jumps and trims |
| 5: Satin | Local skeleton, centerline tangent/normal intersections, two rails, turning columns, span/coverage validation; center/contour/zigzag underlay | Branches, holes and unstable/wide columns fall back to fill; no manual rail editor |
| 6: Compensation | Configurable physical profiles, directional fill expansion, satin offset, lower-fill underlap and overlap dependencies | Not calibrated to actual fabric/stabilizer/thread; outer expansion is clipped to target size |
| 7: Decomposition | Multiple connected components; separate lobes connected by thin necks; source/parent IDs and exact clipped coverage | Arbitrary lettering is not split into professional satin strokes; difficult letters use fill or manual masks |
| 8: Optimization | Color and distance choices among dependency-ready objects; bounded geometric connectors | Heuristic costs, no global optimum, no proven Barudan trim execution or automatic tie-in/tie-off |
| 9: Preview | Batched vector rendering; top/underlay/travel/jump/trim controls; entry/exit, directions, layer/type/sequence labels; playback and scrubbing | Playback shows order, not a physical cloth or machine-time simulation |

## Using the upgrade

1. Open artwork, select or separate it, and review the Layers tab.
2. Set a layer's Sewing role and order with Up/Down. Explicit layer order takes
   precedence over role and color preferences.
3. In Stitches select Fabric, set actual physical size, and review compensation,
   underlap, underlay spacing and stagger. These presets are engineering starting
   values. They are not automatically inferred from an image or the machine brand.
4. Enable Plan direction per object, or enter a part direction to override it.
5. Auto Digitize; inspect Top stitches, Underlay, Travel, Jumps, Trims, Entry/exit,
   Directions and Object order. Use Play/Pause and the scrub slider to see order.
6. Save Project as `.stitchforge` for further editing. Export DST for machine-file
   interchange, including opening in Wilcom subject to its object reconstruction.
7. Sew a test on the intended material before customer production.

Legacy / no planning retains the previous generators and color-order behavior.
Old projects without fabric settings load in legacy mode for repeatability.
Changing fabric or geometry requires regenerating stitches.

## Format correction and recovery

The earlier `.emb` export was a ZIP project with a misleading extension. That
feature has been removed. No function writes `.emb` project files now. Open Project
offers **Recover old Threadform package** to recover those old ZIP files; save them
again as `.stitchforge`. Real OLE-based Wilcom EMB files produce a clear unsupported
format message. Renaming a ZIP or DST is never a native EMB conversion.

## Reference inspection

`pip install -e '.[reference]'` installs an optional OLE container reader.
`scripts/inspect_emb.py INPUT.EMB OUTPUT_DIRECTORY` reads the supplied file without
changing it, hashes it, inventories streams, records raw property IDs and extracts
an embedded thumbnail when available. Raw numeric IDs are deliberately not labeled
as stitch counts or physical dimensions without a verified schema.

The two supplied customer files contain Wilcom document/property streams and an
embedded 100×100 BMP thumbnail. Their native `DesignDocument` object/stitch data
has **not** been decoded. Neither their thumbnails nor unverified property numbers
establish underlay settings, sewing sequence or fabric parameters. User files and
derived reports live under ignored `output/references/` and are not published.

The user identified the production machine brand as **Barudan**. Machine model,
needle, fabric, backing and thread specifications remain unknown. Brand alone does
not calibrate density/compensation or verify how the machine executes DST trims.

## Verification and physical acceptance

Run `python -m pytest -q`. Set `STITCHFORGE_MONKEY_IMAGE` for the private image test.
Run `python scripts/benchmark_planning.py` for ten reproducible cases: circle,
rectangle, concave U, hole, curved column, A, word, overlapping colors,
fill/text/border and a multicolor logo. Each output includes input artwork,
vectors/object plan/dependencies, masks in an editable project, preview, DST
readback verification and metrics. Artifacts go under ignored `output/`.

For physical acceptance record machine/model, needle, fabric, backing, thread,
size, spacing, underlay and compensation. Inspect gaps, puckering, thread breaks,
edge registration, visible travel and loss of small details. No customer-ready or
industrial-ready claim is made until those sew-outs pass. Stitch intersections in
satin/underlay are often intentional, so the validator does not reject every
geometric crossing; a fabric simulation remains outside this implementation.

## Technical references

- [Ink/Stitch satin column](https://inkstitch.org/docs/stitches/satin-column/): rails, directional control and underlays.
- [Wilcom machine-file conversion](https://docs.wilcom.com/embroiderystudio/26/en/OnlineHelp/Production/convert/Opening_machine_files.htm): reconstruction differs from preserving original objects.
- [Wilcom pull compensation](https://docs.wilcom.com/embroiderystudio/28/en/OnlineHelp/Release/rn-28-notes/rn-28-notes-14.htm): compensation must be controlled relative to material and overlap.

The source specification remains a roadmap for refining this baseline; the limits
above are not completed industrial acceptance criteria.
