// Monaco language definition for NovaLang, mirrored from docs/grammar.ebnf
// and novac/tokens.py's KEYWORDS table.

export const LANGUAGE_ID = "novalang";

export const languageConfiguration = {
  comments: { lineComment: "//" },
  brackets: [
    ["{", "}"],
    ["[", "]"],
    ["(", ")"],
  ],
  autoClosingPairs: [
    { open: "{", close: "}" },
    { open: "[", close: "]" },
    { open: "(", close: ")" },
    { open: '"', close: '"' },
  ],
};

export const monarchTokensProvider = {
  keywords: [
    "func", "let", "if", "else", "while", "for", "return",
  ],
  typeKeywords: ["int", "float", "bool", "string"],
  booleanLiterals: ["true", "false"],

  operators: [
    "+", "-", "*", "/", "%", "<", "<=", ">", ">=", "==", "!=",
    "=", "&&", "||", "!", "->",
  ],

  symbols: /[=><!~?:&|+\-*/%^]+/,

  tokenizer: {
    root: [
      [/[a-zA-Z_]\w*/, {
        cases: {
          "@keywords": "keyword",
          "@typeKeywords": "type",
          "@booleanLiterals": "number.boolean",
          "@default": "identifier",
        },
      }],
      [/\/\/.*$/, "comment"],
      [/\d+\.\d+/, "number.float"],
      [/\d+/, "number"],
      [/".*?"/, "string"],
      [/[{}()[\]]/, "@brackets"],
      [/@symbols/, {
        cases: {
          "@operators": "operator",
          "@default": "",
        },
      }],
      [/[;,.:]/, "delimiter"],
    ],
  },
};

export const theme = {
  base: "vs-dark",
  inherit: true,
  rules: [
    { token: "keyword", foreground: "c792ea", fontStyle: "bold" },
    { token: "type", foreground: "22d3ee" },
    { token: "number.boolean", foreground: "f78c6c" },
    { token: "number", foreground: "f78c6c" },
    { token: "number.float", foreground: "f78c6c" },
    { token: "string", foreground: "c3e88d" },
    { token: "comment", foreground: "6b6b80", fontStyle: "italic" },
    { token: "operator", foreground: "89ddff" },
    { token: "identifier", foreground: "e9e9f0" },
    { token: "delimiter", foreground: "9494a8" },
  ],
  colors: {
    "editor.background": "#14141d",
    "editor.lineHighlightBackground": "#1a1a26",
    "editorLineNumber.foreground": "#4a4a5e",
    "editorLineNumber.activeForeground": "#9494a8",
    "editorCursor.foreground": "#22d3ee",
    "editor.selectionBackground": "#8b5cf640",
  },
};
