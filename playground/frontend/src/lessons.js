// Curated NovaLang curriculum for the "Learn" mode. Every snippet is real,
// runnable NovaLang — verified against docs/grammar.ebnf and the semantic
// rules in docs/decisions.md, and loadable straight into the Playground via
// "Try it". Error-lesson snippets are *meant* to fail; that's the lesson.

export const LESSONS = [
  {
    id: "hello-world",
    group: "Basics",
    title: "Hello, NovaLang",
    summary: "Every program is a set of functions; execution starts at main().",
    notes: [
      "main() must return int — NovaLang has no void return type.",
      "print(expr) is a built-in that accepts int, float, bool, or a string literal.",
    ],
    snippet: `func main() -> int {
    print("hello, NovaLang");
    return 0;
}
`,
  },
  {
    id: "variables-types",
    group: "Basics",
    title: "Variables & Types",
    summary: "let type: name = value; — four scalar types, no implicit conversion.",
    notes: [
      "The four types are int, float, bool, string — string may only appear as a print() argument (no string variables or concatenation).",
      "int op float is a compile-time type error. There's no implicit promotion in either direction — you'd need an explicit cast (not yet supported) or matching types.",
    ],
    snippet: `func main() -> int {
    let int: count = 42;
    let float: ratio = 3.14;
    let bool: active = true;
    print(count);
    print(ratio);
    print(active);
    return 0;
}
`,
  },
  {
    id: "operators",
    group: "Basics",
    title: "Operators",
    summary: "Arithmetic, relational, logical, and unary — with C-like integer division.",
    notes: [
      "int / and % truncate toward zero (C / LLVM sdiv/srem semantics), not Python's floor-based // and % — -7 / 2 is -3 here, not Python's -4.",
      "&& and || are logical (short-circuit), operating on bool only.",
    ],
    snippet: `func main() -> int {
    let int: a = 7;
    let int: b = 2;
    print(a / b);        // 3
    print(-a / b);        // -3, truncates toward zero (not Python's -4)
    print(a % b);         // 1
    print(a > b && b > 0);
    return 0;
}
`,
  },
  {
    id: "control-flow",
    group: "Control Flow",
    title: "if / else chains",
    summary: "Every path through a function must return — the compiler checks this statically.",
    notes: [
      "An if only 'always returns' if it has an else and both branches return on every path — that's what lets this pass semantic analysis.",
      "A function that could fall off the end without returning is rejected before codegen, since every LLVM block needs a terminator.",
    ],
    snippet: `func classify(int: n) -> int {
    if (n < 0) {
        return -1;
    } else if (n == 0) {
        return 0;
    } else {
        return 1;
    }
}

func main() -> int {
    print(classify(-5));
    print(classify(0));
    print(classify(9));
    return 0;
}
`,
  },
  {
    id: "loops",
    group: "Control Flow",
    title: "while & for loops",
    summary: "Classic C-style loops — while(cond) and for(init; cond; incr).",
    notes: [
      "for's increment clause has no trailing semicolon: for (let int: i = 0; i < 5; i = i + 1) { ... }.",
      "Loops are never assumed to always-return, even ones that obviously terminate — a return must follow the loop.",
    ],
    snippet: `func main() -> int {
    let int: sum = 0;
    for (let int: i = 1; i <= 5; i = i + 1) {
        sum = sum + i;
    }
    print(sum); // 15

    let int: n = 5;
    let int: result = 1;
    while (n > 1) {
        result = result * n;
        n = n - 1;
    }
    print(result); // 120
    return 0;
}
`,
  },
  {
    id: "functions-recursion",
    group: "Functions",
    title: "Functions & recursion",
    summary: "Declare with func name(params) -> type. Direct and mutual recursion both work.",
    notes: [
      "isEven calls isOdd before isOdd is defined below it — that's fine. Codegen is two-pass: every function signature is declared first, so forward references and mutual recursion resolve regardless of source order.",
    ],
    snippet: `func factorial(int: n) -> int {
    if (n <= 1) { return 1; } else { return n * factorial(n - 1); }
}

func isEven(int: n) -> bool {
    if (n == 0) { return true; } else { return isOdd(n - 1); }
}
func isOdd(int: n) -> bool {
    if (n == 0) { return false; } else { return isEven(n - 1); }
}

func main() -> int {
    print(factorial(6));
    print(isEven(10));
    return 0;
}
`,
  },
  {
    id: "arrays",
    group: "Arrays",
    title: "Arrays",
    summary: "Fixed-size, single-dimension, local-variable-only.",
    notes: [
      "int[5] is valid; int[5][3] is not — only one array dimension is supported.",
      "Arrays can't be function parameters or return types — they never cross a function boundary, by design.",
      "A compile-time bounds error is raised only when both the array size and the index are integer literals known at compile time (e.g. scores[10] on a size-5 array). A variable index like scores[i] is unchecked — a runtime concern outside this project's scope.",
    ],
    snippet: `func main() -> int {
    let int[5]: scores = [10, 20, 30, 40, 50];
    let int: total = 0;
    for (let int: i = 0; i < 5; i = i + 1) {
        total = total + scores[i];
    }
    print(total);      // 150
    print(scores[2]);   // 30
    return 0;
}
`,
  },
  {
    id: "scopes",
    group: "Arrays",
    title: "Scopes & shadowing",
    summary: "A bare { } block introduces a new scope; inner declarations can shadow outer ones.",
    notes: [
      "statement includes block directly in the grammar — braces alone, with no if/while/for attached, are a valid statement that opens a new scope.",
    ],
    snippet: `func main() -> int {
    let int: x = 1;
    {
        let int: x = 2;
        print(x); // 2 — inner x shadows the outer one
    }
    print(x); // 1 — outer x is unaffected
    return 0;
}
`,
  },
  {
    id: "err-undeclared",
    group: "Common Errors",
    title: "Undeclared variable",
    summary: "Referencing a name that was never declared with let (or as a parameter).",
    isErrorLesson: true,
    notes: ["Try it below — the Semantic stage will fail and the stepper will turn red right there."],
    snippet: `func main() -> int {
    return y;
}
`,
  },
  {
    id: "err-type-mismatch",
    group: "Common Errors",
    title: "int + float type mismatch",
    summary: "No implicit conversion means mixing int and float in one expression is a compile error.",
    isErrorLesson: true,
    notes: ["This is decisions.md #4 in action — not a bug, a deliberate simplification."],
    snippet: `func main() -> int {
    let int: a = 3;
    let float: b = 2.0;
    print(a + b);
    return 0;
}
`,
  },
  {
    id: "err-array-bounds",
    group: "Common Errors",
    title: "Array index out of bounds (static case)",
    summary: "Caught only when both the size and the index are literal — this is exactly that case.",
    isErrorLesson: true,
    notes: ["Swap the literal 5 for a variable and this same out-of-range access would compile fine (and be a runtime concern instead)."],
    snippet: `func main() -> int {
    let int[3]: arr = [1, 2, 3];
    return arr[5];
}
`,
  },
  {
    id: "err-missing-return",
    group: "Common Errors",
    title: "Not every path returns",
    summary: "An if without an else can fall off the end — the compiler rejects that statically.",
    isErrorLesson: true,
    notes: ["Add an else branch that also returns and this compiles cleanly."],
    snippet: `func check(int: n) -> int {
    if (n > 0) {
        return 1;
    }
}

func main() -> int {
    return check(5);
}
`,
  },
];
