export default function Header({ view, onViewChange }) {
  return (
    <header className="app-header">
      <div className="brand">
        <svg className="brand-mark" viewBox="0 0 32 32" width="26" height="26">
          <defs>
            <linearGradient id="brand-g" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#8b5cf6" />
              <stop offset="100%" stopColor="#22d3ee" />
            </linearGradient>
          </defs>
          <rect width="32" height="32" rx="8" fill="#1a1a26" />
          <path d="M9 24V8h3.2l7.6 11.2V8H23v16h-3.2L12.2 12.8V24H9z" fill="url(#brand-g)" />
        </svg>
        <div className="brand-text">
          <span className="brand-title">NovaLang</span>
          <span className="brand-subtitle">Compiler Playground</span>
        </div>
      </div>

      <div className="view-switch" role="group" aria-label="View">
        <button
          type="button"
          className={`view-switch-btn ${view === "playground" ? "active" : ""}`}
          onClick={() => onViewChange("playground")}
        >
          Playground
        </button>
        <button
          type="button"
          className={`view-switch-btn ${view === "learn" ? "active" : ""}`}
          onClick={() => onViewChange("learn")}
        >
          Learn NovaLang
        </button>
      </div>

      <div className="header-meta">
        <span className="pipeline-caption">lexer &rarr; parser &rarr; semantic &rarr; TAC &rarr; optimizer &rarr; LLVM IR &rarr; JIT</span>
      </div>
    </header>
  );
}
