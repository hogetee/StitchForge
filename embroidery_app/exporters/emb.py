"""Editable Threadform EMB project package.

The native Wilcom EMB format is proprietary and is not a format that
pyembroidery can write.  Threadform's EMB export is therefore an editable
project archive with an ``.emb`` extension.  It contains the same portable
source, foreground, masks, colors, order and settings as a ``.stitchforge``
project and can be reopened with Threadform's Open Project action.
"""
from pathlib import Path

from embroidery_app.project import load_project, save_project


def export_emb(image, alpha, document, settings, filename):
    """Write and verify a Threadform editable EMB project."""
    if document is None or not document.layers:
        raise ValueError("An editable layer document is required for EMB export")
    target = Path(filename)
    if target.suffix.lower() != ".emb":
        target = target.with_suffix(".emb")
    save_project(target, image, alpha, document, settings, format_name="threadform-emb")
    _, _, restored, _ = load_project(target)
    if len(restored.layers) != len(document.layers):
        raise ValueError("EMB project verification failed: layer count changed")
    return {
        "parts": len(restored.layers),
        "colors": len({layer.color for layer in restored.layers}),
        "filename": str(target),
    }
