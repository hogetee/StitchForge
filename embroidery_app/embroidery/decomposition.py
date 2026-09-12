"""Conservative neck decomposition with exact source coverage and provenance.

This handles lobes joined by thin necks. Branching letters still require manual
column editing; the planner reports unreliable automatic satin as a fallback.
"""
from dataclasses import dataclass,replace
from shapely import voronoi_polygons
from shapely.geometry import MultiPoint
from embroidery_app.image_processing.vectorization import polygons


@dataclass(frozen=True)
class DecompositionRules:
    neck_radius_mm: float = 1.5
    minimum_core_area_mm2: float = 4.0
    maximum_children: int = 12


def decompose(objects,rules=DecompositionRules()):
    result=[]
    for obj in objects:
        cores=[p for p in polygons(obj.geometry.buffer(-rules.neck_radius_mm)) if p.area>=rules.minimum_core_area_mm2]
        if obj.role in ('OUTLINE','BORDER','TEXT') or not 2<=len(cores)<=rules.maximum_children:
            result.append(obj); continue
        cells=voronoi_polygons(MultiPoint([p.representative_point() for p in cores]),extend_to=obj.geometry.envelope)
        pieces=[p for cell in cells.geoms for p in polygons(obj.geometry.intersection(cell)) if p.area>1e-8]
        if not 2<=len(pieces)<=rules.maximum_children:
            result.append(obj); continue
        # Geometry union is exact up to GEOS tolerance; IDs are stable by spatial order.
        pieces.sort(key=lambda p:p.bounds)
        children=[]
        for i,p in enumerate(pieces):
            children.append(replace(obj,id=f'{obj.id}/part-{i+1}',geometry=p,source_region_id=obj.id,
                parent_object=obj.id,child_objects=[],must_stitch_before=[],must_stitch_after=[],warnings=list(obj.warnings)))
        obj.child_objects=[p.id for p in children]
        result.extend(children)
    # A dependency on a source object expands to all of its resulting children.
    lookup={o.id:[p.id for p in result if p.id==o.id or p.parent_object==o.id] for o in objects}
    source={o.id:o for o in objects}
    for obj in result:
        parent=source.get(obj.parent_object) or source.get(obj.id)
        obj.must_stitch_before=[child for target in parent.must_stitch_before for child in lookup.get(target,[target])]
        obj.must_stitch_after=[child for target in parent.must_stitch_after for child in lookup.get(target,[target])]
    return result
