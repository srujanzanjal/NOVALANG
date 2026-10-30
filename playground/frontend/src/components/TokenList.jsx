import { tokenCategory } from "../token-categories";

export default function TokenList({ tokens }) {
  if (!tokens || tokens.length === 0) {
    return <div className="empty-state">No tokens yet — start typing.</div>;
  }
  return (
    <div className="token-grid">
      {tokens
        .filter((t) => t.type !== "EOF")
        .map((t, i) => (
          <span className={`token-chip token-${tokenCategory(t.type)}`} key={i} title={`${t.type}  @ ${t.line}:${t.col}`}>
            <span className="token-lexeme">{t.lexeme}</span>
            <span className="token-type">{t.type}</span>
          </span>
        ))}
    </div>
  );
}
