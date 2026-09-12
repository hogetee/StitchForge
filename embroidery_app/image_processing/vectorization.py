"""Deterministic masked palette quantization and polygon extraction."""
import cv2
import numpy as np
from PIL import Image
from shapely.geometry import Polygon,box
from shapely.affinity import scale,translate
from shapely import make_valid


def polygons(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type=="Polygon":
        return [geometry]
    return [p for part in getattr(geometry,"geoms",[]) for p in polygons(part)]


def vectorize(image,mask,width_mm,height_mm,colors=3,min_area_mm2=0.3,simplify_mm=0.15):
    if image.shape[:2]!=mask.shape or not mask.any():
        raise ValueError("Select a non-empty region first")
    if not 1<=colors<=5 or width_mm<=0 or height_mm<=0:
        raise ValueError("Invalid size or color count")
    ys,xs=np.nonzero(mask)
    x0,y0,x1,y1=xs.min(),ys.min(),xs.max()+1,ys.max()+1
    crop=image[y0:y1,x0:x1]
    selected=mask[y0:y1,x0:x1]>0
    pixels=crop[selected]
    palette_image=Image.fromarray(pixels.reshape(1,-1,3)).quantize(colors=colors,method=Image.Quantize.MEDIANCUT)
    palette=np.array(palette_image.getpalette(),np.uint8).reshape(-1,3)
    label_values=np.array(palette_image).ravel()
    labels=np.full(selected.shape,-1,np.int16)
    labels[selected]=label_values
    sx,sy=width_mm/(x1-x0),height_mm/(y1-y0)
    regions=[]
    for label in np.unique(label_values):
        binary=(labels==label).astype(np.uint8)
        # Upsampling puts contour edges closer to pixel-cell boundaries and preserves narrow features.
        expanded=cv2.resize(binary,None,fx=2,fy=2,interpolation=cv2.INTER_NEAREST)
        contours,hierarchy=cv2.findContours(expanded,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:
            continue
        def ring(contour):
            return [(float(p[0][0])/2+0.25,float(p[0][1])/2+0.25) for p in contour]
        for i,contour in enumerate(contours):
            if hierarchy[0][i][3]!=-1 or len(contour)<3:
                continue
            holes=[]
            child=hierarchy[0][i][2]
            while child!=-1:
                if len(contours[child])>=3:
                    holes.append(ring(contours[child]))
                child=hierarchy[0][child][0]
            geometry=make_valid(Polygon(ring(contour),holes))
            geometry=scale(geometry,xfact=sx,yfact=sy,origin=(0,0))
            geometry=geometry.simplify(simplify_mm,preserve_topology=True)
            color="#"+"".join(f"{c:02x}" for c in palette[label])
            for poly in polygons(geometry):
                if poly.area>=min_area_mm2:
                    regions.append((poly,color))
    if not regions:
        raise ValueError("No regions survive the minimum-area filter")
    return regions
