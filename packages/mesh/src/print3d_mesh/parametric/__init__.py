"""Modelos paramétricos próprios (sem licença de terceiros: origem 'parametrico')."""

from print3d_mesh.parametric.base import ParametricModel
from print3d_mesh.parametric.box import BoxParams, ParametricBox
from print3d_mesh.parametric.fonts import FONTS, FontSpec
from print3d_mesh.parametric.generator import MODELS, GenerationResult, generate
from print3d_mesh.parametric.keychain import KeychainLetterName, KeychainParams
from print3d_mesh.parametric.openscad import OpenScadError, OpenScadRunner, scad_string

__all__ = [
    "FONTS",
    "MODELS",
    "BoxParams",
    "FontSpec",
    "GenerationResult",
    "KeychainLetterName",
    "KeychainParams",
    "OpenScadError",
    "OpenScadRunner",
    "ParametricBox",
    "ParametricModel",
    "generate",
    "scad_string",
]
