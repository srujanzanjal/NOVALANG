export default function CodeBlock({ content, emptyLabel }) {
  if (!content) {
    return <div className="empty-state">{emptyLabel ?? "Nothing to show yet."}</div>;
  }
  return <pre className="code-block">{content}</pre>;
}
