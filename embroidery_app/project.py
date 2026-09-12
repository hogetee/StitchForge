"""Portable local layer projects: JSON and PNGs, never executable pickle data."""
import io
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
import numpy as np
from PIL import Image
from embroidery_app.image_processing.layers import ArtworkLayer, LayerDocument


def _png(array):
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    return buffer.getvalue()


def save_project(filename, image, alpha, document, settings, format_name=None):
    target = Path(filename)
    format_name = format_name or ("threadform-emb" if target.suffix.lower() == ".emb" else "stitchforge")
    metadata = dict(version=1, format=format_name, settings=settings, notes=document.notes, layers=[])
    fd, temporary = tempfile.mkstemp(suffix=".stitchforge", dir=target.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("source.png", _png(np.dstack((image,alpha))))
            archive.writestr("foreground.png", _png(document.foreground))
            for i, layer in enumerate(document.layers):
                entry = dict(id=layer.id, name=layer.name, color=layer.color, enabled=layer.enabled,
                             mode=layer.mode, angle=layer.angle, protect_details=layer.protect_details)
                metadata['layers'].append(entry)
                archive.writestr(f"masks/{i}.png", _png(layer.mask))
            archive.writestr("project.json", json.dumps(metadata, ensure_ascii=False))
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_project(filename):
    with zipfile.ZipFile(filename) as archive:
        if sum(info.file_size for info in archive.infolist()) > 200_000_000:
            raise ValueError("Layer project is too large")
        metadata = json.loads(archive.read("project.json"))
        if metadata.get('version') != 1 or len(metadata.get('layers', [])) > 128:
            raise ValueError("Unsupported layer project version or too many layers")

        def read_image(name, mode):
            with Image.open(io.BytesIO(archive.read(name))) as source:
                if max(source.size) > 1600:
                    raise ValueError("Project images exceed 1600 pixels")
                return np.array(source.convert(mode))

        rgba = read_image("source.png", "RGBA")
        foreground = read_image("foreground.png", "L")
        if foreground.shape != rgba.shape[:2]:
            raise ValueError("Project masks do not match the source image")
        foreground = np.where((foreground > 0) & (rgba[:,:,3] > 0),255,0).astype(np.uint8)
        document = LayerDocument(foreground, notes=[str(n) for n in metadata.get('notes', [])])
        used = np.zeros_like(foreground, bool)
        ids = set()
        for i, entry in enumerate(metadata['layers']):
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", entry['color']) or entry['mode'] not in ('Auto','Outline','Fill'):
                raise ValueError("Invalid layer color or strategy")
            if entry['angle'] is not None and not (isinstance(entry['angle'], (int,float)) and 0 <= entry['angle'] < 180):
                raise ValueError("Invalid layer stitch direction")
            if not isinstance(entry['id'], str) or entry['id'] in ids:
                raise ValueError("Duplicate or invalid layer ID")
            ids.add(entry['id'])
            mask = read_image(f"masks/{i}.png", "L")
            if mask.shape != foreground.shape or np.any((mask > 0) & (used | (foreground == 0))):
                raise ValueError("Layer masks overlap or lie outside the foreground")
            mask = np.where(mask > 0,255,0).astype(np.uint8)
            used |= mask > 0
            document.layers.append(ArtworkLayer(str(entry['name'])[:160], entry['color'], mask, entry['id'],
                bool(entry['enabled']),entry['mode'],entry['angle'],bool(entry.get('protect_details',False))))
        return rgba[:,:,:3].copy(), rgba[:,:,3].copy(), document, metadata.get('settings', {})
