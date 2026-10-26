async function call(path, opts) {
  const res = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    throw new Error(typeof e.detail === "string" ? e.detail : "Request failed");
  }
  return res.json();
}
export const api = {
  health: () => call("/health"),
  start: (body) => call("/sessions", { method: "POST", body: JSON.stringify(body) }),
  turn: (id, argument) => call(`/sessions/${id}/turn`, { method: "POST", body: JSON.stringify({ argument }) }),
  summary: (id) => call(`/sessions/${id}/summary`),
};
