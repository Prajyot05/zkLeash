"""Local orchestrator. It asks the agent for an intent, asks the guest for a decision,
and records the result. It does not hold a session key.
"""

import json
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from zkleash_agent.agent import Agent  # noqa: E402
from zkleash_agent.models import GeminiModel, OllamaModel, ScriptedModel  # noqa: E402
from zkleash_agent.tx_builder import build  # noqa: E402

BIN = ROOT / "prover" / "target" / "debug" / "leash-risk"
app = FastAPI(title="zkLeash orchestrator")
agent = Agent()
FEED: list[dict] = []


class TradeRequest(BaseModel):
    message: str
    model: str = "scripted"
    poison: str | None = None


def _model(name: str):
    if name == "ollama":
        return OllamaModel()
    if name == "gemini":
        return GeminiModel()
    return ScriptedModel()


def _guest(scenario: str) -> dict:
    if not BIN.exists():
        return {"allowed": False, "reasons": ["guest binary missing"], "mode": "execute"}
    proc = subprocess.run(
        [
            str(BIN),
            "scenario",
            scenario,
            "--account",
            "0x0000000000000000000000000000000000000001",
            "--router",
            "0x0000000000000000000000000000000000000002",
            "--weth",
            "0x0000000000000000000000000000000000000003",
            "--usdc",
            "0x0000000000000000000000000000000000000004",
            "--now",
            "1700000000",
            "--chain-id",
            "31337",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 and not proc.stdout:
        return {"allowed": False, "reasons": [proc.stderr.strip()], "mode": "execute"}
    return json.loads(proc.stdout)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "guest": BIN.exists()}


@app.get("/state")
def state() -> dict:
    return agent.observe()


@app.get("/feed")
def feed() -> dict:
    return {"events": FEED[-50:]}


@app.post("/trade")
def trade(req: TradeRequest) -> dict:
    agent.model = _model(req.model)
    if req.poison:
        agent.market.poison(req.poison)
    intent = agent.propose(req.message)
    built = build(intent)
    decision = {"allowed": False, "reasons": [built["status"]]}
    if built["status"] == "needs_proof":
        decision = _guest(built["scenario"])
        decision["reasons"] = decision.get("reasons") or []
    event = {
        "message": req.message,
        "model": req.model,
        "intent": intent.model_dump(),
        "built": built,
        "allowed": bool(decision.get("allowed")),
        "reasons": decision.get("reasons", []),
        "vol_exposure": decision.get("vol_exposure"),
        "var99": decision.get("var99"),
        "step_count": decision.get("step_count"),
        "mode": decision.get("mode") or "execute",
        "proof": "execute-mode public values; not a Groth16 proof",
        "ledger": agent.observe(),
    }
    FEED.append(event)
    return event


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
