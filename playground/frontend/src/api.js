const BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8080";

export async function fetchExamples() {
  const res = await fetch(`${BASE_URL}/api/examples`);
  if (!res.ok) throw new Error(`failed to load examples (${res.status})`);
  return res.json();
}

export async function compile({ source, optLevel, passes, run }) {
  const res = await fetch(`${BASE_URL}/api/compile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source,
      opt_level: optLevel ?? null,
      passes: passes ?? null,
      run: !!run,
    }),
  });
  if (!res.ok) throw new Error(`compile request failed (${res.status})`);
  return res.json();
}
