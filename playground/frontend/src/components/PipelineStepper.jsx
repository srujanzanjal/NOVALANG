const STAGES = [
  { key: "lexer", label: "Lex" },
  { key: "parser", label: "Parse" },
  { key: "semantic", label: "Semantic" },
  { key: "ir", label: "TAC" },
  { key: "optimizer", label: "Optimize" },
  { key: "codegen", label: "LLVM IR" },
  { key: "run", label: "JIT Run" },
];

export default function PipelineStepper({ result, phase }) {
  const order = STAGES.map((s) => s.key);
  const reachedIndex = result ? order.indexOf(result.stage) : -1;
  const errorStage = result?.errors?.[0]?.stage;
  const errorIndex = errorStage ? order.indexOf(errorStage) : -1;
  const successUpTo = errorIndex >= 0 ? Math.min(reachedIndex, errorIndex - 1) : reachedIndex;

  return (
    <div className="stepper">
      {STAGES.map((stage, i) => {
        let state = "pending";
        if (i === errorIndex) state = "error";
        else if (i <= successUpTo) state = "success";

        const isBusy = phase !== "idle" && i === successUpTo + 1 && state === "pending";

        return (
          <div className={`step step-${state} ${isBusy ? "step-busy" : ""}`} key={stage.key}>
            <span className="step-dot" />
            <span className="step-label">{stage.label}</span>
            {i < STAGES.length - 1 && <span className="step-connector" />}
          </div>
        );
      })}
    </div>
  );
}
