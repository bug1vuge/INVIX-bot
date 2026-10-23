// Liveness probe for Docker and the gateway. Intentionally does not call the
// API: a slow API must not make every web replica look dead.
export function GET() {
  return Response.json({ status: "ok" }, { headers: { "Cache-Control": "no-store" } });
}
