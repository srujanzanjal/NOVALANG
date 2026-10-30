export default function OutputPanel({ result }) {
  if (!result || result.returnValue === null || result.returnValue === undefined) {
    return <div className="empty-state">Click Run to JIT-compile and execute this program.</div>;
  }
  return (
    <div className="output-panel">
      <pre className="code-block output-text">{result.output || "(no stdout output)"}</pre>
      <div className={`return-code ${result.returnValue === 0 ? "return-ok" : "return-nonzero"}`}>
        process exited with code <strong>{result.returnValue}</strong>
      </div>
    </div>
  );
}
