const ORCHESTRATOR = process.env.ORCHESTRATOR_URL || "http://127.0.0.1:8000";

export async function GET() {
  try {
    const res = await fetch(`${ORCHESTRATOR}/state`, { cache: "no-store" });
    return Response.json(await res.json());
  } catch {
    return Response.json({ prices: null, portfolio: null, news: [] });
  }
}
