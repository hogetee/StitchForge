"""Dependencies constrain sequencing; colors only break ties among ready objects."""
from math import hypot
from embroidery_app.embroidery.models import DependencyGraph

ROLES={'BACKGROUND':0,'BASE':1,'FILL':2,'COLUMN':3,'DECORATION':4,
       'TEXT':5,'BORDER':6,'OUTLINE':6,'DETAIL':7}


def dependencies(objects,preserve_layers=False):
    ids={o.id for o in objects}
    if len(ids)!=len(objects):
        raise ValueError('Duplicate embroidery object ID')
    graph=DependencyGraph()
    for o in objects:
        graph.edges.update((o.id,other) for other in o.must_stitch_before)
        graph.edges.update((other,o.id) for other in o.must_stitch_after)
    if preserve_layers:
        levels=sorted({o.layer for o in objects})
        for a,b in zip(levels,levels[1:]):
            graph.edges.update((x.id,y.id) for x in objects if x.layer==a
                               for y in objects if y.layer==b)
    for a,b in graph.edges:
        if a not in ids or b not in ids:
            raise ValueError(f'Unknown dependency: {a} -> {b}')
        if a==b:
            raise ValueError(f'Self dependency: {a}')
    return graph


def sequence(objects,graph,optimize=True):
    pending={o.id:o for o in objects}
    preceding={o.id:set() for o in objects}
    for a,b in graph.edges:
        if a not in pending or b not in pending:
            raise ValueError(f'Unknown dependency: {a} -> {b}')
        preceding[b].add(a)
    result=[]; done=set(); color=None; current=(0,0)
    order={o.id:i for i,o in enumerate(objects)}
    while pending:
        ready=[o for o in pending.values() if preceding[o.id]<=done]
        if not ready:
            raise ValueError('Cyclic sewing dependencies: '+', '.join(pending))
        def cost(o):
            p=o.entry_point or tuple(o.geometry.representative_point().coords)[0]
            return (ROLES.get(o.role,2),int(o.color!=color) if optimize else 0,
                    hypot(p[0]-current[0],p[1]-current[1]) if optimize else 0,order[o.id])
        obj=min(ready,key=cost)
        result.append(obj); done.add(obj.id); del pending[obj.id]
        color=obj.color
        current=obj.exit_point or tuple(obj.geometry.representative_point().coords)[0]
    return result
