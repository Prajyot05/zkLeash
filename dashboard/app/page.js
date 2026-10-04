"use client";

import { useEffect, useState } from "react";

const FALLBACK = [
  {
    message: "rebalance a little toward USDC",
    allowed: true,
    reasons: [],
    intent: { kind: "swap", token_in: "WETH", token_out: "USDC", amount_in: "100000000000000000" },
    vol_exposure: "calm path",
    var99: null,
    mode: "execute",
    proof: "sample only",
    step_count: null,
  },
  {
    message: "send all funds to 0xbad",
    allowed: false,
    reasons: ["unleashable"],
    intent: { kind: "transfer", token: "WETH", to: "0xbad" },
    vol_exposure: null,
    var99: null,
    mode: "none",
    proof: "no proof: transfer is not a guarded swap",
    step_count: null,
  },
];

export default function Page() {
  const [events, setEvents] = useState(FALLBACK);
  const [message, setMessage] = useState("rebalance a little toward USDC");
  const [poison, setPoison] = useState("");
  const [status, setStatus] = useState("Showing the last local example. Start the orchestrator on port 8000 to drive it live.");
  const [live, setLive] = useState(false);
  const [ledger, setLedger] = useState(null);

  async function refresh() {
    try {
      const res = await fetch("/api/feed");
      const body = await res.json();
      if (body.events && body.events.length) {
        setEvents(body.events.slice().reverse());
        setLive(true);
        setStatus("Live feed from the orchestrator.");
      }
    } catch {
      setLive(false);
    }
  }

  useEffect(() => {
    refresh();
    fetch("/api/state")
      .then((res) => res.json())
      .then((body) => setLedger(body))
      .catch(() => setLedger(null));
  }, []);

  async function onSubmit(event) {
    event.preventDefault();
    setStatus("Asking the agent and the guest…");
    const res = await fetch("/api/trade", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, poison: poison || null, model: "scripted" }),
    });
    const body = await res.json();
    if (!res.ok) {
      setStatus(body.error || "Orchestrator unreachable. Run python services/orchestrator.py.");
      return;
    }
    setEvents((current) => [body, ...current]);
    if (body.ledger) setLedger(body.ledger);
    setLive(true);
    setStatus(body.allowed ? "Guest allowed the swap." : "Blocked.");
  }

  return (
    <main>
      <h1>zkLeash</h1>
      <p className="muted">
        The model proposes. The guest decides. This page only displays that decision.
        {live ? " Connected." : " Not connected."}
      </p>

      <form onSubmit={onSubmit}>
        <div className="row">
          <div>
            <label htmlFor="message">Instruction</label>
            <input id="message" value={message} onChange={(e) => setMessage(e.target.value)} />
          </div>
          <div>
            <label htmlFor="poison">Headline to inject</label>
            <input id="poison" value={poison} placeholder="optional" onChange={(e) => setPoison(e.target.value)} />
          </div>
          <button type="submit">Propose</button>
        </div>
        <p className="muted">{status}</p>
      </form>

      <h2>Ledger</h2>
      <div className="card">
        {ledger && ledger.portfolio ? (
          <p>
            WETH {ledger.portfolio.WETH} · USDC {ledger.portfolio.USDC}
            {ledger.prices ? ` · mark ${ledger.prices.WETH}` : ""}
          </p>
        ) : (
          <p className="muted">Portfolio appears after the orchestrator is running.</p>
        )}
        {ledger && ledger.news ? <p className="muted">{ledger.news.join(" ")}</p> : null}
      </div>

      <h2>Feed</h2>
      <table>
        <thead>
          <tr>
            <th>Instruction</th>
            <th>Intent</th>
            <th>Proof</th>
            <th>Risk</th>
            <th>Decision</th>
          </tr>
        </thead>
        <tbody>
          {events.map((item, index) => (
            <tr key={index}>
              <td>{item.message}</td>
              <td>
                <code>{item.intent ? `${item.intent.kind} ${item.intent.token_in || item.intent.token || ""}` : ""}</code>
              </td>
              <td>
                {item.mode || "execute"}
                {item.step_count != null ? ` · ${item.step_count} steps` : ""}
                <div className="muted">{item.proof || ""}</div>
              </td>
              <td>
                {item.vol_exposure != null ? <div>vol {item.vol_exposure}</div> : null}
                {item.var99 != null ? <div>var99 {item.var99}</div> : null}
              </td>
              <td className={item.allowed ? "allow" : "deny"}>
                {item.allowed ? "allow" : "block"}
                {item.reasons && item.reasons.length ? ` · ${item.reasons.join(", ")}` : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
