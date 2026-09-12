"""Editable raster parts. Masks share source coordinates and never overlap."""
from dataclasses import dataclass, field
from uuid import uuid4
import numpy as np


@dataclass
class ArtworkLayer:
    name: str
    color: str
    mask: np.ndarray
    id: str = field(default_factory=lambda: uuid4().hex)
    enabled: bool = True
    mode: str = "Auto"
    angle: float | None = None
    protect_details: bool = False

    def copy(self):
        return ArtworkLayer(self.name, self.color, self.mask.copy(), self.id,
                            self.enabled, self.mode, self.angle, self.protect_details)


@dataclass
class LayerDocument:
    foreground: np.ndarray
    layers: list[ArtworkLayer] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def copy(self):
        return LayerDocument(self.foreground.copy(), [p.copy() for p in self.layers], list(self.notes))

    def replace_mask(self, index, mask):
        """Painting claims pixels from other parts; subtraction leaves empty fabric."""
        claimed = np.where(mask > 0, 255, 0).astype(np.uint8)
        self.layers[index].mask = claimed
        for i, layer in enumerate(self.layers):
            if i != index:
                layer.mask[claimed > 0] = 0
        self.foreground |= claimed

    def render(self, image, only=None):
        """Render a flat inspection image.

        By default only enabled layers are shown, matching the layers that will
        be used for digitizing.  ``only`` is an optional set of layer indexes
        used by the UI's solo-view command; it deliberately ignores the
        enabled flag so a disabled layer can still be inspected and corrected.
        """
        result = np.full_like(image, 245)
        for index, layer in enumerate(self.layers):
            visible = index in only if only is not None else layer.enabled
            if visible:
                result[layer.mask > 0] = tuple(bytes.fromhex(layer.color.lstrip("#")))
        return result

    def enabled_mask(self):
        result = np.zeros_like(self.foreground)
        for layer in self.layers:
            if layer.enabled:
                result |= layer.mask
        return result
