import math
import pyembroidery as pe
import pytest
from embroidery_app.examples import proof_design
from embroidery_app.exporters.dst import export_dst
from embroidery_app.embroidery.models import EmbroideryDesign, Stitch
from embroidery_app.embroidery.generators.running import running


@pytest.mark.parametrize("kind",["square","circle","multicolor"])
def test_proof_roundtrip(tmp_path,kind):
    design = proof_design(kind)
    file = tmp_path/f"{kind}.dst"
    report = export_dst(design,file)
    restored = pe.read_dst(str(file))
    assert report["stitches"] > 40
    assert file.stat().st_size >= 512
    assert restored.stitches[-1][2] & pe.COMMAND_MASK == pe.END
    assert restored.count_color_changes() == (1 if kind=="multicolor" else 0)
    expected = [s for s in design.stitches if s.command.value=="STITCH"]
    actual = [s for s in restored.stitches if s[2]&pe.COMMAND_MASK==pe.STITCH]
    assert len(expected)==len(actual)
    for a,b in zip(expected,actual):
        assert abs(a.x-b[0]/10)<=0.051
        assert abs(a.y-b[1]/10)<=0.051


def test_running_length():
    stitches = running([(0,0),(13,0),(13,7)],2.5)
    assert (stitches[-1].x,stitches[-1].y)==(13,7)
    assert all(math.hypot(b.x-a.x,b.y-a.y)<=2.5 for a,b in zip(stitches,stitches[1:]))


def test_export_rejects_invalid(tmp_path):
    with pytest.raises(ValueError,match="no stitches"):
        export_dst(EmbroideryDesign(10,10),tmp_path/"bad.dst")
    with pytest.raises(ValueError,match="Invalid"):
        export_dst(EmbroideryDesign(10,10,stitches=[Stitch(float('nan'),0)]),tmp_path/"bad.dst")


def test_multicolor_sequence_and_bounds(tmp_path):
    report=export_dst(proof_design("multicolor"),tmp_path/"multi.dst")
    assert report["bounds_mm"]==pytest.approx((5,5,72,37),abs=0.051)


def test_existing_file_preserved_on_invalid(tmp_path):
    output=tmp_path/"existing.dst"
    output.write_bytes(b"original")
    with pytest.raises(ValueError):
        export_dst(EmbroideryDesign(10,10),output)
    assert output.read_bytes()==b"original"
