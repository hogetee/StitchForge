"""Configurable engineering starting points in millimeters, not sew-out claims."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class FabricProfile:
    name: str = 'Custom'
    pull_compensation_mm: float = 0.2
    underlap_mm: float = 0.2
    underlay_spacing_mm: float = 2.0
    underlay_inset_mm: float = 0.4
    minimum_detail_mm: float = 0.6
    trim_distance_mm: float = 3.0
    stagger_period: int = 4
    minimum_stitch_mm: float = 0.1
    narrow_satin_mm: float = 1.5
    wide_satin_mm: float = 3.0
    internal_travel_limit_mm: float = 12.0
    auto_direction: bool = True
    underlay_enabled: bool = True
    contour_tolerance_mm: float = 0.15
    minimum_underlay_area_mm2: float = 4.0
    suggested_row_spacing_mm: float = 0.4
    suggested_stitch_length_mm: float = 4.0

    def validate(self):
        for key in ('pull_compensation_mm','underlap_mm','underlay_spacing_mm',
                    'underlay_inset_mm','minimum_detail_mm','trim_distance_mm',
                    'minimum_stitch_mm','narrow_satin_mm','wide_satin_mm','internal_travel_limit_mm',
                    'contour_tolerance_mm','minimum_underlay_area_mm2'):
            value=getattr(self,key)
            if not isfinite(value) or value<0:
                raise ValueError(f'Invalid fabric parameter: {key}')
        if self.underlay_spacing_mm<0.15 or not isinstance(self.stagger_period,int) or not 1<=self.stagger_period<=16:
            raise ValueError('Invalid underlay spacing or stagger period')
        if self.pull_compensation_mm>2 or self.underlap_mm>2:
            raise ValueError('Compensation and underlap must not exceed 2 mm')
        if not 0.15<=self.suggested_row_spacing_mm<=2 or not 0.5<=self.suggested_stitch_length_mm<=10:
            raise ValueError('Invalid suggested stitch settings')
        return self


PROFILES={
    'Woven / Cotton': FabricProfile('Woven / Cotton'),
    'Knit / T-shirt': FabricProfile('Knit / T-shirt',0.3,0.3,1.8,0.4,0.8,suggested_row_spacing_mm=0.45),
    'Denim': FabricProfile('Denim',0.15,0.15,2.5,0.4,0.6),
    'Fleece': FabricProfile('Fleece',0.35,0.3,1.6,0.5,1.0),
    'Custom': FabricProfile(),
}


def get_profile(value):
    if value is None:
        return None
    if isinstance(value,FabricProfile):
        return value.validate()
    if isinstance(value,dict):
        return FabricProfile(**value).validate()
    if value not in PROFILES:
        raise ValueError(f'Unknown fabric profile: {value}')
    return PROFILES[value].validate()
