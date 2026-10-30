// The compiler intentionally keeps parsing/analyzing after the first error
// (up to MAX_ERRORS in novac/parser.py + semantic.py) so it can report
// several real problems in one pass — but a single bad token can also
// cascade into a wall of identical "expected X, got Y" repeats. Dedupe by
// message so the banner shows each distinct problem once, with a count.
function dedupe(errors) {
  const seen = new Map();
  for (const e of errors) {
    const key = `${e.stage}\n${e.message}`;
    const entry = seen.get(key);
    if (entry) entry.count += 1;
    else seen.set(key, { ...e, count: 1 });
  }
  return [...seen.values()];
}

export default function ErrorList({ errors }) {
  if (!errors || errors.length === 0) return null;
  const distinct = dedupe(errors);
  return (
    <div className="error-banner">
      {distinct.map((e, i) => (
        <div className="error-line" key={i}>
          <span className="error-stage">{e.stage}</span>
          <span className="error-message">{e.message}</span>
          {e.count > 1 && <span className="error-count">&times;{e.count}</span>}
        </div>
      ))}
    </div>
  );
}
