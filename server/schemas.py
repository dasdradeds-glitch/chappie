"""Contrato FaceState (HANDOFF §3) como schema pydantic. Todo payload que
sai do servidor (WS /face, GET /neuro) e todo payload que entra (POST /say)
deve validar contra isto — e o que tests/test_contract.py cobra."""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

COLOR_RE = re.compile(r"^(#[0-9a-fA-F]{6}|rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\))$")

DOMINANT_KEYS = (
    "happiness", "excitement", "affection", "calm",
    "anger", "fear", "sadness", "curiosity",
)


def _validate_dominant(v: str) -> str:
    if v not in DOMINANT_KEYS:
        raise ValueError(f"dominant invalido: {v}")
    return v


class ChemicalsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dopamine: float = Field(ge=0, le=1)
    serotonin: float = Field(ge=0, le=1)
    oxytocin: float = Field(ge=0, le=1)
    cortisol: float = Field(ge=0, le=1)
    adrenaline: float = Field(ge=0, le=1)
    endorphins: float = Field(ge=0, le=1)
    testosterone: float = Field(ge=0, le=1)
    gaba: float = Field(ge=0, le=1)


class EmotionsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    happiness: float = Field(ge=0, le=1)
    excitement: float = Field(ge=0, le=1)
    affection: float = Field(ge=0, le=1)
    calm: float = Field(ge=0, le=1)
    anger: float = Field(ge=0, le=1)
    fear: float = Field(ge=0, le=1)
    sadness: float = Field(ge=0, le=1)
    curiosity: float = Field(ge=0, le=1)


class FaceGeometryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eyeWidthVw: float
    eyeHeightVh: float
    browAngleDeg: float
    browLiftVh: float
    browLenVw: float
    browThickVh: float
    browCurveVh: float
    mouthCurve: float
    mouthWidthVw: float
    scale: float
    dropYVh: float
    leanXVw: float
    tiltDeg: float
    blink: bool


class FaceStateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chemicals: ChemicalsModel
    emotions: EmotionsModel
    dominant: str
    intensity: float = Field(ge=0, le=1)
    color: str
    speaking: bool
    face: FaceGeometryModel

    @field_validator("dominant")
    @classmethod
    def _dominant_valid(cls, v: str) -> str:
        return _validate_dominant(v)

    @field_validator("color")
    @classmethod
    def _color_valid(cls, v: str) -> str:
        if not COLOR_RE.match(v):
            raise ValueError(f"color invalido: {v}")
        return v


class SayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)


class SayResponse(BaseModel):
    reply: str
    impulses: dict[str, float]


class NeuroSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chemicals: ChemicalsModel
    emotions: EmotionsModel
    dominant: str

    @field_validator("dominant")
    @classmethod
    def _dominant_valid(cls, v: str) -> str:
        return _validate_dominant(v)
