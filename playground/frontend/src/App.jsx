import { useCallback, useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import { LANGUAGE_ID, languageConfiguration, monarchTokensProvider, theme } from "./novalang-language";
import { fetchExamples, compile } from "./api";
import Header from "./components/Header";
import Toolbar from "./components/Toolbar";
import PipelineStepper from "./components/PipelineStepper";
import StagePanels from "./components/StagePanels";
import Learn from "./components/Learn";
import "./App.css";

const FALLBACK_SOURCE = `func main() -> int {
    print("hello, NovaLang");
    return 0;
}
`;

function handleMonacoWillMount(monaco) {
  monaco.languages.register({ id: LANGUAGE_ID });
  monaco.languages.setLanguageConfiguration(LANGUAGE_ID, languageConfiguration);
  monaco.languages.setMonarchTokensProvider(LANGUAGE_ID, monarchTokensProvider);
  monaco.editor.defineTheme("novalang-dark", theme);
}

export default function App() {
  const [examples, setExamples] = useState([]);
  const [selectedExampleId, setSelectedExampleId] = useState("");
  const [source, setSource] = useState(FALLBACK_SOURCE);
  const [optLevel, setOptLevel] = useState("O2");
  const [result, setResult] = useState(null);
  const [phase, setPhase] = useState("idle"); // idle | analyzing | running
  const [view, setView] = useState("playground"); // playground | learn
  const debounceRef = useRef(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    fetchExamples()
      .then((list) => {
        setExamples(list);
        const helloWorld = list.find((e) => e.id === "hello_world" && e.category === "valid");
        if (helloWorld) {
          setSelectedExampleId(helloWorld.id);
          setSource(helloWorld.source);
        }
      })
      .catch(() => {
        // backend not reachable yet — keep the fallback source, toolbar shows empty example list
      });
  }, []);

  const runCompile = useCallback((src, level, shouldRun) => {
    const requestId = ++requestIdRef.current;
    setPhase(shouldRun ? "running" : "analyzing");
    compile({ source: src, optLevel: level, run: shouldRun })
      .then((data) => {
        if (requestId !== requestIdRef.current) return; // stale response, a newer request superseded it
        setResult(data);
      })
      .catch((err) => {
        if (requestId !== requestIdRef.current) return;
        setResult({
          stage: "lexer",
          tokens: [], ast: null, tac: null, optimizedTac: null, llvmIr: null,
          output: null, returnValue: null,
          errors: [{ stage: "connection", message: err.message + " — is the backend running on :8000?" }],
        });
      })
      .finally(() => {
        if (requestId === requestIdRef.current) setPhase("idle");
      });
  }, []);

  // debounced live compile+run on every source/opt-level change — output is
  // generated automatically; the Run button stays as an explicit trigger.
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runCompile(source, optLevel, true), 400);
    return () => clearTimeout(debounceRef.current);
  }, [source, optLevel, runCompile]);

  const handleRun = () => {
    clearTimeout(debounceRef.current);
    runCompile(source, optLevel, true);
  };

  const handleExampleChange = (id) => {
    setSelectedExampleId(id);
    const found = examples.find((e) => e.id === id);
    if (found) setSource(found.source);
  };

  const handleTryLesson = (snippet) => {
    setSelectedExampleId("");
    setSource(snippet);
    setView("playground");
    clearTimeout(debounceRef.current);
    runCompile(snippet, optLevel, true);
  };

  return (
    <div className="app-shell">
      <Header view={view} onViewChange={setView} />
      {view === "learn" ? (
        <Learn onTryIt={handleTryLesson} />
      ) : (
        <div className="app-body">
          <section className="pane pane-editor">
            <Toolbar
              examples={examples}
              selectedExampleId={selectedExampleId}
              onExampleChange={handleExampleChange}
              optLevel={optLevel}
              onOptLevelChange={setOptLevel}
              onRun={handleRun}
              phase={phase}
              hasErrors={!!result?.errors?.length}
            />
            <div className="editor-wrap">
              <Editor
                language={LANGUAGE_ID}
                theme="novalang-dark"
                value={source}
                onChange={(value) => setSource(value ?? "")}
                beforeMount={handleMonacoWillMount}
                options={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 16,
                  lineHeight: 26,
                  minimap: { enabled: false },
                  scrollBeyondLastLine: false,
                  padding: { top: 18 },
                  renderLineHighlight: "gutter",
                  cursorBlinking: "smooth",
                }}
              />
            </div>
          </section>

          <section className="pane pane-stages">
            <PipelineStepper result={result} phase={phase} />
            <StagePanels result={result} phase={phase} />
          </section>
        </div>
      )}
    </div>
  );
}
