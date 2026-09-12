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
    phase: str = "TOP"
    object_id: str | None = None


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
    layer_id: str | None = None
    layer_name: str | None = None
    source_region_id: str | None = None
    role: str = "FILL"
    layer: int = 0
    angle_mode: str = "MANUAL"
    underlay_types: tuple[str, ...] = ()
    must_stitch_before: list[str] = field(default_factory=list)
    must_stitch_after: list[str] = field(default_factory=list)
    allow_hidden_travel: bool = True
    parent_object: str | None = None
    child_objects: list[str] = field(default_factory=list)
    centerline: list[tuple[float, float]] = field(default_factory=list)
    left_rail: list[tuple[float, float]] = field(default_factory=list)
    right_rail: list[tuple[float, float]] = field(default_factory=list)
    artwork_geometry: Any = None
    warnings: list[str] = field(default_factory=list)
    auto_stitch: bool = True


@dataclass
class DependencyGraph:
    edges: set[tuple[str, str]] = field(default_factory=set)


@dataclass
class EmbroideryPlan:
    objects: list[EmbroideryObject]
    graph: DependencyGraph = field(default_factory=DependencyGraph)
    warnings: list[str] = field(default_factory=list)


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
    plan: EmbroideryPlan | None = None
    warnings: list[str] = field(default_factory=list)
