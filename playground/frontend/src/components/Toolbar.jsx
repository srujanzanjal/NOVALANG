const OPT_LEVELS = ["O0", "O1", "O2"];

const STATUS = {
  idle: { label: "Ready", className: "dot-idle" },
  analyzing: { label: "Compiling…", className: "dot-busy" },
  running: { label: "Running…", className: "dot-busy" },
  error: { label: "Error", className: "dot-error" },
  success: { label: "Success", className: "dot-success" },
};

export default function Toolbar({
  examples,
  selectedExampleId,
  onExampleChange,
  optLevel,
  onOptLevelChange,
  onRun,
  phase,
  hasErrors,
}) {
  const validExamples = examples.filter((e) => e.category === "valid");
  const errorExamples = examples.filter((e) => e.category === "error");

  let statusKey = phase;
  if (phase === "idle") statusKey = hasErrors ? "error" : "success";
  const status = STATUS[statusKey] ?? STATUS.idle;

  return (
    <div className="toolbar">
      <select
        className="example-select"
        value={selectedExampleId}
        onChange={(e) => onExampleChange(e.target.value)}
      >
        <option value="" disabled>
          Load an example…
        </option>
        {validExamples.length > 0 && (
          <optgroup label="Examples">
            {validExamples.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
              </option>
            ))}
          </optgroup>
        )}
        {errorExamples.length > 0 && (
          <optgroup label="Error cases">
            {errorExamples.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
              </option>
            ))}
          </optgroup>
        )}
      </select>

      <div className="opt-level-group" role="group" aria-label="Optimization level">
        {OPT_LEVELS.map((level) => (
          <button
            key={level}
            type="button"
            className={`opt-level-btn ${optLevel === level ? "active" : ""}`}
            onClick={() => onOptLevelChange(level)}
          >
            -{level}
          </button>
        ))}
      </div>

      <button type="button" className="run-btn" onClick={onRun} disabled={phase === "running"}>
        <span className="run-icon">&#9654;</span> Run
      </button>

      <div className="status-pill">
        <span className={`status-dot ${status.className}`} />
        {status.label}
      </div>
    </div>
  );
}
