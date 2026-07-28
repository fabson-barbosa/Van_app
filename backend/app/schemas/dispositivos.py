"""Schemas do registro de token de push (Bloco B5)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.device_token import DeviceTokenProvider


class DeviceTokenRegistrar(BaseModel):
    token: str = Field(min_length=1, max_length=255)
    provider: DeviceTokenProvider = DeviceTokenProvider.EXPO


class DeviceTokenRemover(BaseModel):
    token: str = Field(min_length=1, max_length=255)
