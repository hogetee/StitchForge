"""CPU region proposals, not semantic face recognition or a cloud service."""
import cv2
import numpy as np
from .layers import ArtworkLayer, LayerDocument
from embroidery_app.embroidery.exceptions import DigitizeCancelled


def _emit(progress, value, message):
    if progress:
        progress(value, message)


def _check(cancel_check):
    if cancel_check is not None and cancel_check():
        raise DigitizeCancelled()


def extract_foreground(image, selection=None, alpha=None, progress=None, cancel_check=None):
    _check(cancel_check)
    h, w = image.shape[:2]
    allowed = np.ones((h, w), np.uint8) * 255 if selection is None else selection.copy()
    if alpha is not None:
        allowed[alpha == 0] = 0
    if not allowed.any():
        raise ValueError("Select an area containing the object first")
    if alpha is not None and np.any(alpha == 0):
        return allowed
    # Work within the selected crop, but retain a shared full-image coordinate system.
    ys, xs = np.nonzero(allowed)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max()+1, ys.max()+1
    crop = image[y0:y1, x0:x1]
    limit = min(1.0, 640/max(crop.shape[:2]))
    size = (max(3, round(crop.shape[1]*limit)), max(3, round(crop.shape[0]*limit)))
    small = cv2.resize(crop, size, interpolation=cv2.INTER_AREA)
    scope = cv2.resize(allowed[y0:y1, x0:x1], size, interpolation=cv2.INTER_NEAREST) > 0
    smooth = cv2.bilateralFilter(small, 7, 35, 5)
    lab = cv2.cvtColor(smooth, cv2.COLOR_RGB2LAB).astype(np.float32)
    border = np.zeros(scope.shape, bool)
    border[:2] = border[-2:] = True
    border[:, :2] = border[:, -2:] = True
    samples = lab[border & scope]
    if len(samples) < 5:
        samples = lab[border]
    background = np.median(samples, axis=0)
    distance = np.linalg.norm(lab-background, axis=2)
    threshold = max(12.0, min(32.0, float(np.percentile(np.linalg.norm(samples-background, axis=1), 65))+8))
    likely = (distance > threshold) & scope
    if np.count_nonzero(likely) < 5:
        raise ValueError("No distinct foreground found. Turn off Remove background and draw the object mask manually.")
    gc = np.where(likely, cv2.GC_PR_FGD, cv2.GC_PR_BGD).astype(np.uint8)
    gc[~scope | (border & (distance < threshold))] = cv2.GC_BGD
    interior = cv2.erode(likely.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    gc[interior & (distance > threshold*1.5)] = cv2.GC_FGD
    if not np.any(gc == cv2.GC_FGD):
        gc.flat[np.argmax(distance*scope)] = cv2.GC_FGD
    if not np.any(gc == cv2.GC_BGD):
        raise ValueError("Background is ambiguous. Leave margin around the object or turn off Remove background.")
    cv2.setRNGSeed(0)
    bg, fg = np.zeros((1,65), np.float64), np.zeros((1,65), np.float64)
    for i in range(3):
        _check(cancel_check)
        _emit(progress, 0.05+0.09*i, f"Separating background · pass {i+1}/3")
        cv2.grabCut(smooth, gc, None, bg, fg, 1, cv2.GC_INIT_WITH_MASK if i == 0 else cv2.GC_EVAL)
    found = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)*255
    found = cv2.resize(found, (x1-x0, y1-y0), interpolation=cv2.INTER_NEAREST)
    result = np.zeros((h,w), np.uint8)
    result[y0:y1, x0:x1] = found
    result &= allowed
    if not result.any():
        raise ValueError("Foreground extraction was empty; refine the selection or disable background removal")
    return result


def _cluster(samples, count, preserve_dark):
    """Balanced deterministic Lloyd clustering; sparse dark details get a seed."""
    if len(samples) > 40000:
        samples = samples[np.linspace(0, len(samples)-1, 40000, dtype=int)]
    centers = [np.median(samples, axis=0)]
    if preserve_dark and count > 1:
        dark = samples[samples[:,0] <= np.percentile(samples[:,0], 3)]
        centers.append(np.median(dark, axis=0))
    while len(centers) < count:
        distances = np.min(np.sum((samples[:,None,:]-np.array(centers)[None,:,:])**2, axis=2), axis=1)
        centers.append(samples[np.argmax(distances)])
    centers = np.array(centers, np.float32)
    # Keep the reserved dark seed fixed so large shaded surfaces cannot consume it.
    for _ in range(15):
        labels = np.argmin(np.sum((samples[:,None,:]-centers[None,:,:])**2, axis=2), axis=1)
        updated = centers.copy()
        for i in range(count):
            if preserve_dark and i == 1:
                continue
            members = samples[labels == i]
            if len(members):
                updated[i] = np.median(members, axis=0)
        if np.max(np.abs(updated-centers)) < 0.2:
            break
        centers = updated
    return centers


def separate_layers(image, selection=None, alpha=None, colors=4, remove_background=True,
                    smoothing=11, min_pixels=100, preserve_dark=True, merge_shades=False,
                    single_material=False, progress=None, cancel_check=None):
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise ValueError("Segmentation needs an RGB image")
    if not 1 <= colors <= 5:
        raise ValueError("Choose 1–5 thread colors")
    if not isinstance(merge_shades, (bool, np.bool_)) or not isinstance(single_material, (bool, np.bool_)):
        raise ValueError("Shading and material options must be boolean")
    _check(cancel_check)
    foreground = (extract_foreground(image, selection, alpha, progress, cancel_check) if remove_background
                  else np.full(image.shape[:2],255,np.uint8) if selection is None else selection.copy())
    if alpha is not None:
        foreground[alpha == 0] = 0
    if not foreground.any():
        raise ValueError("No foreground selected")
    _emit(progress, 0.35, "Smoothing texture while retaining edges")
    smooth = cv2.bilateralFilter(image, max(3, int(smoothing) | 1), 40, max(3, smoothing))
    lab = cv2.cvtColor(smooth, cv2.COLOR_RGB2LAB)
    samples = lab[foreground > 0].astype(np.float32)
    _emit(progress, 0.45, "Finding object colors and dark details")
    # Photographs contain illumination bands that are not separate embroidery
    # materials.  Keep the old color-band mode available for callers that need
    # it, while the UI can spend one color bin on those lighting variations.
    # Silhouette mode keeps one non-dark material for a single-color patch.
    cluster_count = (2 if preserve_dark else 1) if single_material else (max(2, colors-1) if merge_shades else colors)
    group_materials = bool(merge_shades or single_material)
    centers = _cluster(samples, cluster_count, preserve_dark)
    labels = np.full(foreground.shape, -1, np.int16)
    # Chunk assignment bounds memory even on the 1600 px canvas.
    assigned = np.empty(len(samples), np.int16)
    for offset in range(0, len(samples), 50000):
        _check(cancel_check)
        chunk = samples[offset:offset+50000]
        assigned[offset:offset+len(chunk)] = np.argmin(np.sum((chunk[:,None,:]-centers[None,:,:])**2, axis=2), axis=1)
    labels[foreground > 0] = assigned
    filtered = cv2.medianBlur((labels+1).astype(np.uint8), 3).astype(np.int16)-1
    change = (foreground > 0) & (filtered >= 0)
    labels[change] = filtered[change]
    # Remove tiny islands by assigning them to the nearest retained region.
    retained = np.zeros_like(foreground, bool)
    dark_index = int(np.argmin(centers[:,0]))
    for i in range(cluster_count):
        _check(cancel_check)
        count, components, stats, _ = cv2.connectedComponentsWithStats((labels == i).astype(np.uint8), 8)
        threshold = max(3, min_pixels//3) if preserve_dark and i == dark_index else min_pixels
        good = np.flatnonzero(stats[:,cv2.CC_STAT_AREA] >= threshold)
        good = good[good != 0]
        retained |= np.isin(components, good)
    if retained.any():
        _, nearest = cv2.distanceTransformWithLabels((~retained).astype(np.uint8), cv2.DIST_L2, 5,
                                                    labelType=cv2.DIST_LABEL_PIXEL)
        lookup = np.zeros(int(nearest.max())+1, np.int16)
        lookup[nearest[retained]] = labels[retained]
        labels[(foreground > 0) & ~retained] = lookup[nearest[(foreground > 0) & ~retained]]
    _emit(progress, 0.70, "Building editable connected parts")
    rgb = cv2.cvtColor(np.clip(centers,0,255).astype(np.uint8)[None,:,:], cv2.COLOR_LAB2RGB)[0]
    layers = []
    material_number = 1
    for i in range(cluster_count):
        count, components, stats, _ = cv2.connectedComponentsWithStats((labels == i).astype(np.uint8), 8)
        indices = sorted(range(1,count), key=lambda j:-stats[j,cv2.CC_STAT_AREA])
        color = "#"+"".join(f"{int(c):02x}" for c in rgb[i])
        detail = preserve_dark and i == dark_index
        if group_materials and not detail:
            mask=(labels == i).astype(np.uint8)*255
            if np.count_nonzero(mask) >= min_pixels:
                layers.append(ArtworkLayer(f"Material {material_number}", color, mask))
                material_number += 1
            continue
        for j in indices:
            if len(layers) >= 128:
                raise ValueError("More than 128 parts: increase smoothing or the minimum part size")
            layers.append(ArtworkLayer(f"{'Dark detail' if detail else 'Color '+str(i+1)} · part {indices.index(j)+1}",
                                       color, (components == j).astype(np.uint8)*255, protect_details=detail))
    # Sew broader regions before small features, keeping dark detail parts on top.
    layers.sort(key=lambda layer:(layer.protect_details, layer.color, -np.count_nonzero(layer.mask)))
    document = LayerDocument(foreground, layers, ["Region proposals use color and connectivity; rename parts and correct masks before exporting."])
    _emit(progress, 1.0, f"Separated {len(layers)} editable parts")
    return document
