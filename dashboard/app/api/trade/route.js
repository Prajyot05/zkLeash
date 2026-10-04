const ORCHESTRATOR = process.env.ORCHESTRATOR_URL || "http://127.0.0.1:8000";

export async function POST(request) {
  const body = await request.json();
  try {
    const res = await fetch(`${ORCHESTRATOR}/trade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const json = await res.json();
    return Response.json(json, { status: res.status });
  } catch (error) {
    return Response.json(
      { error: `orchestrator unreachable at ${ORCHESTRATOR}: ${error.message}` },
      { status: 502 }
    );
  }
}
