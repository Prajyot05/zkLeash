const ORCHESTRATOR = process.env.ORCHESTRATOR_URL || "http://127.0.0.1:8000";

export async function GET() {
  try {
    const res = await fetch(`${ORCHESTRATOR}/feed`, { cache: "no-store" });
    const json = await res.json();
    return Response.json(json);
  } catch {
    return Response.json({ events: [] });
  }
}
