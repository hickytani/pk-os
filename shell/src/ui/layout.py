"""
PK-OS Shell Adaptive Layout Engine
Calculates layer surface geometries, anchor alignments, and margin bounds
for desktop (>=1024px) and mobile/touch (<1024px) displays.
"""

from enum import Enum
from typing import Dict, Any
import dataclasses


class DisplayFormFactor(Enum):
    DESKTOP = "desktop"
    MOBILE = "mobile"


@dataclasses.dataclass(frozen=True)
class SurfaceGeometry:
    width: int
    height: int
    anchor_top: bool
    anchor_bottom: bool
    anchor_left: bool
    anchor_right: bool
    exclusive_zone: int
    margin_top: int = 0
    margin_bottom: int = 0
    margin_left: int = 0
    margin_right: int = 0


class LayoutCalculator:
    DESKTOP_BREAKPOINT = 1024

    @classmethod
    def get_form_factor(cls, screen_width: int) -> DisplayFormFactor:
        if screen_width >= cls.DESKTOP_BREAKPOINT:
            return DisplayFormFactor.DESKTOP
        return DisplayFormFactor.MOBILE

    @classmethod
    def calculate_top_panel(cls, screen_width: int, screen_height: int) -> SurfaceGeometry:
        form = cls.get_form_factor(screen_width)
        height = 36 if form == DisplayFormFactor.DESKTOP else 44

        return SurfaceGeometry(
            width=screen_width,
            height=height,
            anchor_top=True,
            anchor_bottom=False,
            anchor_left=True,
            anchor_right=True,
            exclusive_zone=height
        )

    @classmethod
    def calculate_launcher_modal(cls, screen_width: int, screen_height: int) -> SurfaceGeometry:
        form = cls.get_form_factor(screen_width)

        if form == DisplayFormFactor.DESKTOP:
            # Floating modal centered on screen
            width = min(680, int(screen_width * 0.6))
            height = min(520, int(screen_height * 0.65))
            return SurfaceGeometry(
                width=width,
                height=height,
                anchor_top=False,
                anchor_bottom=False,
                anchor_left=False,
                anchor_right=False,
                exclusive_zone=0
            )
        else:
            # Full-screen drawer for phone touch layout
            return SurfaceGeometry(
                width=screen_width,
                height=screen_height,
                anchor_top=True,
                anchor_bottom=True,
                anchor_left=True,
                anchor_right=True,
                exclusive_zone=0
            )

    @classmethod
    def calculate_voice_hud(cls, screen_width: int, screen_height: int) -> SurfaceGeometry:
        form = cls.get_form_factor(screen_width)

        if form == DisplayFormFactor.DESKTOP:
            # Anchored to top-right below panel
            width = 380
            height = 140
            return SurfaceGeometry(
                width=width,
                height=height,
                anchor_top=True,
                anchor_bottom=False,
                anchor_left=False,
                anchor_right=True,
                exclusive_zone=0,
                margin_top=44,
                margin_right=16
            )
        else:
            # Bottom drawer card on mobile
            height = 180
            return SurfaceGeometry(
                width=screen_width,
                height=height,
                anchor_top=False,
                anchor_bottom=True,
                anchor_left=True,
                anchor_right=True,
                exclusive_zone=0,
                margin_bottom=0
            )
