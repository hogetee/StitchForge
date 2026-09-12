from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Command(str, Enum):
    STITCH = "STITCH"
    JUMP = "JUMP"
    TRIM = "TRIM"
    COLOR_CHANGE = "COLOR_CHANGE"
    END = "END"


class StitchType(str, Enum):
    RUNNING = "RUNNING"
    SATIN = "SATIN"
    TATAMI = "TATAMI"


@dataclass(frozen=True)
class Stitch:
    x: float
    y: float
    command: Command = Command.STITCH


@dataclass
class EmbroideryObject:
    id: str
    geometry: Any
    color: str
    stitch_type: StitchType = StitchType.TATAMI
    density: float = 0.4  # row spacing in mm
    stitch_length: float = 3.0
    angle: float = 0.0
    underlay: bool = False
    pull_compensation: float = 0.0
    entry_point: tuple[float, float] | None = None
    exit_point: tuple[float, float] | None = None
    priority: int = 0


@dataclass
class EmbroideryDesign:
    width_mm: float
    height_mm: float
    source_dimensions: tuple[int, int] = (0, 0)
    regions: list[Any] = field(default_factory=list)
    thread_colors: list[str] = field(default_factory=list)
    objects: list[EmbroideryObject] = field(default_factory=list)
    stitches: list[Stitch] = field(default_factory=list)
    name: str = "Local embroidery"
