from math import hypot, isfinite
from embroidery_app.embroidery.models import Command


def validate(design, max_length=12.1):
    errors, warnings = [], []
    if not any(s.command == Command.STITCH for s in design.stitches):
        errors.append("Design has no stitches")
    for obj in design.objects:
        if obj.density < 0.2:
            warnings.append("Very dense row spacing below 0.2 mm")
    previous = None
    for s in design.stitches:
        if not isfinite(s.x) or not isfinite(s.y):
            errors.append("Invalid stitch coordinates")
            continue
        if not (-0.05 <= s.x <= design.width_mm + 0.05 and
                -0.05 <= s.y <= design.height_mm + 0.05):
            errors.append("Design lies outside target bounds")
        if previous:
            distance = hypot(s.x-previous.x, s.y-previous.y)
            if s.command == Command.STITCH:
                if distance > max_length + 0.01:
                    errors.append("Stitch exceeds maximum length")
                if distance < 0.1:
                    warnings.append("Extremely short stitches")
            elif s.command == Command.JUMP and distance > 30:
                warnings.append("Jump exceeds 30 mm")
        previous = s
    return sorted(set(errors)), sorted(set(warnings))
