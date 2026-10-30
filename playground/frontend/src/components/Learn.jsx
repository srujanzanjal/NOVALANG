import { useState } from "react";
import Editor from "@monaco-editor/react";
import { LESSONS } from "../lessons";
import { LANGUAGE_ID } from "../novalang-language";

function groupLessons() {
  const groups = [];
  for (const lesson of LESSONS) {
    let group = groups.find((g) => g.name === lesson.group);
    if (!group) {
      group = { name: lesson.group, lessons: [] };
      groups.push(group);
    }
    group.lessons.push(lesson);
  }
  return groups;
}

const GROUPS = groupLessons();

export default function Learn({ onTryIt }) {
  const [activeId, setActiveId] = useState(LESSONS[0].id);
  const active = LESSONS.find((l) => l.id === activeId);
  const activeIndex = LESSONS.findIndex((l) => l.id === activeId);

  const goTo = (id) => setActiveId(id);
  const goRelative = (delta) => {
    const next = LESSONS[activeIndex + delta];
    if (next) setActiveId(next.id);
  };

  return (
    <div className="learn-shell">
      <nav className="lesson-sidebar">
        {GROUPS.map((group) => (
          <div className="lesson-group" key={group.name}>
            <div className="lesson-group-label">{group.name}</div>
            {group.lessons.map((lesson) => (
              <button
                key={lesson.id}
                type="button"
                className={`lesson-nav-item ${lesson.id === activeId ? "active" : ""}`}
                onClick={() => goTo(lesson.id)}
              >
                {lesson.isErrorLesson && <span className="lesson-error-dot" />}
                {lesson.title}
              </button>
            ))}
          </div>
        ))}
      </nav>

      <div className="lesson-content">
        <div className="lesson-header">
          <span className="lesson-eyebrow">{active.group}{active.isErrorLesson ? " · expected to fail" : ""}</span>
          <h2 className="lesson-title">{active.title}</h2>
          <p className="lesson-summary">{active.summary}</p>
        </div>

        <div className="lesson-editor">
          <Editor
            language={LANGUAGE_ID}
            theme="novalang-dark"
            value={active.snippet}
            options={{
              readOnly: true,
              domReadOnly: true,
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 15.5,
              lineHeight: 25,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              renderLineHighlight: "none",
              padding: { top: 14 },
              lineNumbersMinChars: 3,
            }}
          />
        </div>

        <ul className="lesson-notes">
          {active.notes.map((note, i) => (
            <li key={i}>{note}</li>
          ))}
        </ul>

        <div className="lesson-actions">
          <button type="button" className="lesson-prev" onClick={() => goRelative(-1)} disabled={activeIndex === 0}>
            &larr; Previous
          </button>
          <button type="button" className="run-btn lesson-try-it" onClick={() => onTryIt(active.snippet)}>
            <span className="run-icon">&#9654;</span> Try it in Playground
          </button>
          <button
            type="button"
            className="lesson-next"
            onClick={() => goRelative(1)}
            disabled={activeIndex === LESSONS.length - 1}
          >
            Next &rarr;
          </button>
        </div>
      </div>
    </div>
  );
}
