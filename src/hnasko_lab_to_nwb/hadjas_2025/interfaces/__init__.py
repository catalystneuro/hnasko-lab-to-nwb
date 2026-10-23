"""Data interfaces of the Hadjas 2025 conversion."""

from .concatenated_tdt_fp_interface import ConcatenatedTDTFiberPhotometryInterface
from .processed_fp_interface import Hadjas2025ProcessedFiberPhotometryInterface
from .tdt_optogenetic_stimulus_interface import Hadjas2025TDTOptogeneticStimulusInterface

__all__ = [
    "ConcatenatedTDTFiberPhotometryInterface",
    "Hadjas2025ProcessedFiberPhotometryInterface",
    "Hadjas2025TDTOptogeneticStimulusInterface",
]
