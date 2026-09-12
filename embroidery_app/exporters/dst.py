"""DST adapter. Internal millimeters become DST tenths of a millimeter."""
from pathlib import Path
import os
import tempfile
import pyembroidery as pe
from embroidery_app.embroidery.models import Command
from embroidery_app.embroidery.validation import validate

CODES = {c: getattr(pe, c.value) for c in Command}


def export_dst(design, filename):
    errors, warnings = validate(design)
    if errors:
        raise ValueError("; ".join(errors))
    pattern = pe.EmbPattern()
    pattern.extras["name"] = design.name[:16]
    for color in design.thread_colors:
        pattern.add_thread(color)
    for s in design.stitches:
        pattern.add_stitch_absolute(CODES[s.command], round(s.x*10), round(s.y*10))
    if not design.stitches or design.stitches[-1].command != Command.END:
        last = design.stitches[-1]
        pattern.add_stitch_absolute(pe.END, round(last.x*10), round(last.y*10))
    # Normalize once so readback checks include library-required jump subdivision.
    normalized = pattern.get_normalized_pattern({"max_stitch":121,"max_jump":121,
                                                  "full_jump":True})
    target = Path(filename)
    fd, temporary = tempfile.mkstemp(suffix=".dst", dir=target.parent)
    os.close(fd)
    try:
        pe.write_dst(normalized, temporary, {"encode":False})
        restored = pe.read_dst(temporary)
        expected = [(round(x),round(y),c & pe.COMMAND_MASK)
                    for x,y,c in normalized.stitches if (c & pe.COMMAND_MASK) != pe.TRIM]
        actual = [(round(x),round(y),c & pe.COMMAND_MASK) for x,y,c in restored.stitches]
        # DST trim sequences may be interpreted as jumps; compare needle records strictly.
        needle_expected = [p for p in expected if p[2] == pe.STITCH]
        needle_actual = [p for p in actual if p[2] == pe.STITCH]
        if needle_actual != needle_expected:
            raise ValueError("DST readback needle coordinates/count differ")
        for code in (pe.COLOR_CHANGE, pe.END):
            if sum(p[2]==code for p in actual) != sum(p[2]==code for p in expected):
                raise ValueError("DST readback command count differs")
        essential = (pe.STITCH,pe.COLOR_CHANGE,pe.END)
        if [p for p in expected if p[2] in essential] != [p for p in actual if p[2] in essential]:
            raise ValueError("DST readback stitch/color/end sequence differs")
        if not actual or actual[-1][2] != pe.END:
            raise ValueError("DST is missing its final END command")
        os.replace(temporary, target)
        return {"stitches": len(needle_actual), "commands":len(actual), "warnings":warnings,
                "bounds_mm":(min(p[0] for p in needle_actual)/10,min(p[1] for p in needle_actual)/10,
                             max(p[0] for p in needle_actual)/10,max(p[1] for p in needle_actual)/10)}
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
