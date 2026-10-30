import { useState } from "react";
import TokenList from "./TokenList";
import CodeBlock from "./CodeBlock";
import ErrorList from "./ErrorList";
import OutputPanel from "./OutputPanel";

const TABS = [
  { key: "tokens", label: "Tokens" },
  { key: "ast", label: "AST" },
  { key: "tac", label: "TAC" },
  { key: "optimizedTac", label: "Optimized TAC" },
  { key: "llvmIr", label: "LLVM IR" },
  { key: "output", label: "Output" },
];

export default function StagePanels({ result, phase }) {
  const [active, setActive] = useState("tokens");

  return (
    <div className="stage-panels">
      <div className="tab-bar">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={`tab-btn ${active === tab.key ? "active" : ""}`}
            onClick={() => setActive(tab.key)}
          >
            {tab.label}
          </button>
        ))}
        {phase !== "idle" && <span className="tab-bar-spinner" />}
      </div>

      <ErrorList errors={result?.errors} />

      <div className="tab-content">
        {active === "tokens" && <TokenList tokens={result?.tokens} />}
        {active === "ast" && <CodeBlock content={result?.ast} emptyLabel="AST will appear once the source parses." />}
        {active === "tac" && <CodeBlock content={result?.tac} emptyLabel="TAC IR will appear after semantic analysis passes." />}
        {active === "optimizedTac" && (
          <CodeBlock content={result?.optimizedTac} emptyLabel="Optimized TAC will appear here." />
        )}
        {active === "llvmIr" && <CodeBlock content={result?.llvmIr} emptyLabel="LLVM IR will appear once codegen runs." />}
        {active === "output" && <OutputPanel result={result} />}
      </div>
    </div>
  );
}
