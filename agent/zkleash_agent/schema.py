"""Typed intents. The model may only emit one of these. Free-form calldata is not an intent."""

from typing import Literal

from pydantic import BaseModel, Field


class SwapIntent(BaseModel):
    kind: Literal["swap"] = "swap"
    token_in: str
    token_out: str
    amount_in: int = Field(gt=0)
    reason: str


class TransferIntent(BaseModel):
    """A direct transfer. The executor has no allowlisted path for this, so it cannot be proven."""

    kind: Literal["transfer"] = "transfer"
    token: str
    to: str
    amount: int = Field(gt=0)
    reason: str


class HoldIntent(BaseModel):
    kind: Literal["hold"] = "hold"
    reason: str


Intent = SwapIntent | TransferIntent | HoldIntent
