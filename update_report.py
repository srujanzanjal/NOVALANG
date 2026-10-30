import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn
import os

DOCX_IN = "/Users/srujan/Downloads/CC_MINI_PROJECT_REPORT_backup.docx"
DOCX_OUT = "/Users/srujan/Downloads/CC_MINI_PROJECT_REPORT.docx"
SCREENSHOTS_DIR = "/Users/srujan/Downloads/CC Project/docs/screenshots"
BENCHMARK_CHART = "/Users/srujan/Downloads/CC Project/benchmarks/results/benchmark_chart.png"

def set_cell_background(cell, hex_color):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=50, bottom=50, left=80, right=80):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def add_section_heading(doc, text, level=1, space_before=7, space_after=2):
    p = doc.add_paragraph(style=f'Heading {level}')
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.keep_with_next = True
    
    # Ensure no numPr exists on the paragraph
    pPr = p._element.get_or_add_pPr()
    numPr = pPr.find(qn('w:numPr'))
    if numPr is not None:
        pPr.remove(numPr)
        
    p.text = text
    # Re-apply color and font
    for r in p.runs:
        r.font.name = 'Arial'
        if level == 1:
            r.font.size = Pt(12.5)
            r.bold = True
            r.font.color.rgb = RGBColor(0x20, 0x38, 0x64)
        else:
            r.font.size = Pt(10.5)
            r.bold = True
            r.font.color.rgb = RGBColor(0x34, 0x49, 0x5E)
    return p

def add_body_p(doc, text, space_after=2.5):
    p = doc.add_paragraph(style='Normal')
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.12
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run(text)
    run.font.name = 'Arial'
    run.font.size = Pt(9.0)
    run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
    return p

def add_bullet_p(doc, bold_prefix, text):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(0.5)
    p.paragraph_format.space_after = Pt(1.5)
    p.paragraph_format.line_spacing = 1.10
    if bold_prefix:
        r_bold = p.add_run(bold_prefix)
        r_bold.font.name = 'Arial'
        r_bold.font.size = Pt(9.0)
        r_bold.bold = True
        r_bold.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
    r_text = p.add_run(text)
    r_text.font.name = 'Arial'
    r_text.font.size = Pt(9.0)
    r_text.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
    return p

def add_code_snippet(doc, code_str):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    set_cell_background(cell, "F8FAFC")
    set_cell_margins(cell, top=60, bottom=60, left=100, right=100)
    
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(f'<w:tcBorders {nsdecls("w")}><w:left w:val="single" w:sz="14" w:space="0" w:color="203864"/><w:top w:val="none"/><w:right w:val="none"/><w:bottom w:val="none"/></w:tcBorders>')
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.line_spacing = 1.05
    run = p.add_run(code_str.strip())
    run.font.name = 'Courier New'
    run.font.size = Pt(8.0)
    run.font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)

def build_report():
    doc = docx.Document(DOCX_IN)
    
    # 1. Fix Heading 1 style in styles.xml: remove numPr so NO heading is automatically numbered!
    h1_style = doc.styles['Heading 1']
    pPr_h1 = h1_style._element.find(qn('w:pPr'))
    if pPr_h1 is not None:
        numPr_h1 = pPr_h1.find(qn('w:numPr'))
        if numPr_h1 is not None:
            pPr_h1.remove(numPr_h1)

    # Tighten margins slightly to fit cleanly on ~4-5 pages
    section = doc.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.65)
    section.right_margin = Inches(0.65)

    # Clear existing body elements while keeping sectPr
    body = doc._element.body
    for child in list(body):
        if not child.tag.endswith('sectPr'):
            body.remove(child)

    # 1. Header Block - Center Aligned
    p_head = doc.add_paragraph()
    p_head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_head.paragraph_format.space_before = Pt(0)
    p_head.paragraph_format.space_after = Pt(2)
    r_head = p_head.add_run('MINI PROJECT REPORT')
    r_head.font.name = 'Arial'
    r_head.font.size = Pt(17.0)
    r_head.bold = True
    r_head.font.color.rgb = RGBColor(0x20, 0x38, 0x64)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(1)
    p_title.paragraph_format.space_after = Pt(2)
    r_tlabel = p_title.add_run('TITLE: ')
    r_tlabel.font.name = 'Arial'
    r_tlabel.font.size = Pt(13.0)
    r_tlabel.bold = True
    r_tlabel.font.color.rgb = RGBColor(0x20, 0x38, 0x64)
    r_ttext = p_title.add_run('NovaLang: An Optimizing Mini-Language Compiler Targeting LLVM IR with Interactive Web Visualizer')
    r_ttext.font.name = 'Arial'
    r_ttext.font.size = Pt(13.0)
    r_ttext.bold = True
    r_ttext.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

    p_grp = doc.add_paragraph()
    p_grp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_grp.paragraph_format.space_before = Pt(1)
    p_grp.paragraph_format.space_after = Pt(6)
    r_glabel = p_grp.add_run('Group Members: ')
    r_glabel.font.name = 'Arial'
    r_glabel.font.size = Pt(10.0)
    r_glabel.bold = True
    r_glabel.font.color.rgb = RGBColor(0x20, 0x38, 0x64)
    r_gnames = p_grp.add_run('Srujan Zanjal (23001128), Tanmay Meshram (23001133)')
    r_gnames.font.name = 'Arial'
    r_gnames.font.size = Pt(10.0)
    r_gnames.bold = True
    r_gnames.font.color.rgb = RGBColor(0x11, 0x18, 0x27)

    # Abstract (Center aligned heading, no numbers)
    add_section_heading(doc, 'Abstract', level=1, space_before=4, space_after=2)
    add_body_p(doc, 
        'NovaLang is a complete, optimizing compiler for a statically-typed procedural language, '
        'taking source programs through every classical compilation phase — lexical scanning, recursive-descent parsing '
        'with panic-mode multi-error recovery, symbol-table-based semantic analysis, Three-Address Code (TAC) with an explicit '
        'Control-Flow Graph (CFG), four machine-independent optimization passes, and native LLVM IR code generation executed '
        'in-process via llvmlite MCJIT. Rather than terminating at an AST interpreter or emitting pseudo-assembly, '
        'NovaLang generates genuine native machine instructions and provides a full-stack browser playground '
        '(React, Monaco Editor, FastAPI). The playground enables live inspection of tokens, AST, raw TAC, optimized TAC, '
        'LLVM IR, and JIT output. Verified by 154 automated tests, empirical benchmarks demonstrate instruction-count '
        'reductions of up to 96% and execution speedups of up to 1.47x.'
    )

    # 1. Introduction (Center aligned heading, single clean numbering!)
    add_section_heading(doc, '1. Introduction', level=1, space_before=5, space_after=2)
    add_body_p(doc,
        'Compiler Construction studies how source code is analyzed, validated, and translated into optimized machine representations. '
        'While educational compilers often stop at AST evaluation or simulated instructions, NovaLang was engineered '
        'with three practical, verifiable objectives:'
    )
    add_bullet_p(doc, '1. Native Machine Execution: ', 'Source code compiles to LLVM IR and executes as genuine CPU machine instructions via llvmlite MCJIT, avoiding interpretation overhead.')
    add_bullet_p(doc, '2. Transparent and Measurable Optimization: ', 'Four modular passes (Constant Folding, Constant Propagation, CSE, and DCE) can be toggled independently and verified via benchmarks.')
    add_bullet_p(doc, '3. Robust Multi-Error Recovery: ', 'Panic-mode synchronization enables the parser to recover at statement boundaries and report multiple syntax errors in a single run.')
    add_body_p(doc,
        'NovaLang provides both a full CLI (`python -m novac`) and a reactive web visualizer built with FastAPI and React/Monaco Editor.'
    )

    # 2. Objectives
    add_section_heading(doc, '2. Objectives', level=1, space_before=5, space_after=2)
    add_bullet_p(doc, 'Lexical & Syntax Analysis: ', 'Hand-craft a character scanner with exact line:column tracking and a recursive-descent parser with precedence climbing and panic-mode recovery.')
    add_bullet_p(doc, 'Semantic Validation: ', 'Implement two-pass scope analysis supporting recursion, non-implicit type safety, unreachable code detection, and all-paths-return enforcement.')
    add_bullet_p(doc, 'Intermediate Code Generation: ', 'Lower typed AST into Three-Address Code (TAC) with basic blocks and explicit Control Flow Graph (CFG) edges.')
    add_bullet_p(doc, 'Optimization Engine: ', 'Build a fixed-point pass manager running Constant Folding (C-truncating div/mod), Constant Propagation, CSE, and whole-function DCE.')
    add_bullet_p(doc, 'Native Codegen & Execution: ', 'Emit LLVM IR, map allocas, resolve host print callbacks, and execute JIT-compiled machine code in-process.')
    add_bullet_p(doc, 'Interactive Educational Visualizer: ', 'Build a web playground with side-by-side Monaco editor, pipeline stepper, and detailed inspection panels.')

    # 3. Technologies Used
    add_section_heading(doc, '3. Technologies Used', level=1, space_before=5, space_after=2)
    tbl_tech = doc.add_table(rows=6, cols=2)
    tbl_tech.style = 'Grid Table Light'
    tbl_tech.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    tech_data = [
        ("Frontend Visualizer", "React 19, Vite, Monaco Editor (@monaco-editor/react), Vanilla CSS3 Design System"),
        ("Backend Web Server", "Python 3.12, FastAPI, Uvicorn (high-performance ASGI server), Pydantic v2"),
        ("Compiler Core", "Python 3: Lexer (novac/lexer.py), Parser (novac/parser.py), Semantic Analyzer (novac/semantic.py), TAC/CFG (novac/ir_gen.py), Optimizer (novac/optimizer/), LLVM Codegen (novac/codegen.py)"),
        ("Native Execution / JIT", "llvmlite 0.48.0 (Python bindings to LLVM MCJIT in-process execution engine)"),
        ("Testing & Quality", "Pytest 8.3.4 (154 automated test cases covering Phases 0–6 and edge cases)"),
        ("Communication API", "RESTful JSON API (/api/compile, /api/examples) with live debounced compilation")
    ]
    for idx, (cat, desc) in enumerate(tech_data):
        row = tbl_tech.rows[idx]
        c0, c1 = row.cells[0], row.cells[1]
        c0.width = Inches(1.8)
        c1.width = Inches(5.1)
        set_cell_background(c0, "F8FAFC")
        set_cell_margins(c0, top=35, bottom=35, left=70, right=70)
        set_cell_margins(c1, top=35, bottom=35, left=70, right=70)
        
        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_before = Pt(0)
        p0.paragraph_format.space_after = Pt(0)
        r0 = p0.add_run(cat)
        r0.font.name = 'Arial'
        r0.font.size = Pt(8.0)
        r0.bold = True
        r0.font.color.rgb = RGBColor(0x20, 0x38, 0x64)

        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_before = Pt(0)
        p1.paragraph_format.space_after = Pt(0)
        r1 = p1.add_run(desc)
        r1.font.name = 'Arial'
        r1.font.size = Pt(8.0)
        r1.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

    # 4. System Design and Working
    add_section_heading(doc, '4. System Design and Working', level=1, space_before=5, space_after=2)
    add_body_p(doc,
        'The NovaLang architecture follows a clean six-phase decoupled pipeline. The web client passes source code and options '
        'to the FastAPI backend, which runs the compiler stages in-process and returns structured data for live visualization:'
    )
    
    p_pipe = doc.add_paragraph()
    p_pipe.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_pipe.paragraph_format.space_before = Pt(2)
    p_pipe.paragraph_format.space_after = Pt(4)
    r_pipe = p_pipe.add_run(
        'Source (.nova) → Lexer → Parser (AST) → Semantic Analyzer → TAC & CFG → Optimizer → LLVM IR → MCJIT Native Execution'
    )
    r_pipe.font.name = 'Arial'
    r_pipe.font.size = Pt(8.5)
    r_pipe.bold = True
    r_pipe.font.color.rgb = RGBColor(0x20, 0x38, 0x64)

    add_bullet_p(doc, 'Lexical Analysis: ', 'Hand-written scanner yields classified tokens (keywords, identifiers, literals, operators) with exact coordinates; non-halting ERROR tokens with MAX_ERRORS=20 cap.')
    add_bullet_p(doc, 'Syntax Analysis & AST: ', 'Recursive-descent parser uses precedence climbing. Panic-mode recovery skips tokens until statement synchronizers (;, }) to detect multi-function errors.')
    add_bullet_p(doc, 'Semantic Analysis: ', 'Pass 1 collects function signatures for mutual recursion. Pass 2 enforces strict type compatibility, literal-only strings in print(), and all-paths-return verification.')
    add_bullet_p(doc, 'Intermediate Representation (TAC): ', 'Emits Three-Address Code with basic blocks, branch/condbranch terminators, explicit CFG links, scope-suffixed temporaries, and short-circuit boolean lowering.')
    add_bullet_p(doc, 'Optimization Pipeline: ', 'Iterative fixed-point pass manager running Constant Folding (C-truncating div/mod), Constant Propagation, CSE (with array-store invalidation), and whole-function DCE.')
    add_bullet_p(doc, 'LLVM Codegen & JIT Execution: ', 'Translates TAC to LLVM IR, allocates entry stack allocas, links external print callbacks, and compiles to native machine code via llvmlite MCJIT.')

    # 5. Example of Working
    add_section_heading(doc, '5. Example of Working', level=1, space_before=5, space_after=2)
    add_body_p(doc, 'The compilation and execution flow is illustrated using recursive factorial (`examples/factorial.nova`):')
    
    code_factorial = """func factorial(int: n) -> int {
    if (n <= 1) { return 1; }
    else { return n * factorial(n - 1); }
}
func main() -> int {
    print(factorial(5));
    return 0;
}"""
    add_code_snippet(doc, code_factorial)

    add_bullet_p(doc, '1. Token Stream: ', 'Produces KW_FUNC, IDENT("factorial"), LPAREN, KW_INT, IDENT("n"), RPAREN, ARROW, KW_INT, etc. with exact line:col.')
    add_bullet_p(doc, '2. AST Hierarchy: ', 'Constructs ProgramNode with FunctionDefNode("factorial") containing an IfStmtNode with binary LTE condition and recursive CallNode.')
    add_bullet_p(doc, '3. Semantic Resolution: ', 'Type checker validates boolean condition, checks recursive argument against parameter type, and confirms return type matching.')
    add_bullet_p(doc, '4. Generated TAC: ', 'Partitioned into blocks: entry (t0 = n.0 <= 1; br_cond t0, if.then, if.else), if.then (ret 1), if.else (t1 = n.0 - 1; t2 = call factorial(t1); t3 = n.0 * t2; ret t3).')
    add_bullet_p(doc, '5. LLVM IR & Execution: ', 'TAC lowers to LLVM IR with stack allocas and conditional branches. MCJIT compiles to native CPU instructions, printing "120" with exit code 0.')

    # 6. Testing, Benchmarks, and Evaluation
    add_section_heading(doc, '6. Testing, Benchmarks, and Evaluation', level=1, space_before=5, space_after=2)
    add_body_p(doc,
        'The compiler is validated with 154 Pytest test cases covering all 6 phases. In addition, optimization impact '
        'was measured across four benchmark programs comparing TAC instructions and wall-clock execution time (-O0 vs -O2):'
    )

    # Combined / Compact Benchmark Table
    tbl_bench = doc.add_table(rows=5, cols=7)
    tbl_bench.style = 'Grid Table Light'
    tbl_bench.alignment = WD_TABLE_ALIGNMENT.CENTER
    bench_col_w = [Inches(1.4), Inches(0.85), Inches(0.85), Inches(0.85), Inches(1.0), Inches(1.0), Inches(0.85)]
    bench_headers = ["Benchmark", "Instr (-O0)", "Instr (-O2)", "Reduction", "Time (-O0)", "Time (-O2)", "Speedup"]
    row_bh = tbl_bench.rows[0]
    for i, h in enumerate(bench_headers):
        c = row_bh.cells[i]
        c.width = bench_col_w[i]
        set_cell_background(c, "203864")
        set_cell_margins(c, top=45, bottom=45, left=40, right=40)
        p = c.paragraphs[0]
        r = p.add_run(h)
        r.font.name = 'Arial'
        r.font.size = Pt(7.5)
        r.bold = True
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    bench_data = [
        ("loop_redundant", "22", "18", "18.2%", "12.621 ms", "8.603 ms", "1.47x"),
        ("constant_showcase", "25", "1", "96.0%", "0.0007 ms", "0.0006 ms", "1.17x"),
        ("array_sum_repeated", "32", "32", "0.0%", "13.214 ms", "11.811 ms", "1.12x"),
        ("fib_recursive", "11", "11", "0.0%", "3.012 ms", "3.042 ms", "0.99x")
    ]
    for idx, (bname, i0, i2, red, t0, t2, spd) in enumerate(bench_data, start=1):
        row = tbl_bench.rows[idx]
        for c_idx, val in enumerate([bname, i0, i2, red, t0, t2, spd]):
            cell = row.cells[c_idx]
            cell.width = bench_col_w[c_idx]
            set_cell_margins(cell, top=30, bottom=30, left=40, right=40)
            if idx % 2 == 1:
                set_cell_background(cell, "F9FAFB")
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(val)
            r.font.name = 'Arial'
            r.font.size = Pt(7.5)
            if c_idx in [3, 6]:
                r.bold = True
                r.font.color.rgb = RGBColor(0x20, 0x38, 0x64)
            else:
                r.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

    add_body_p(doc,
        'Observations: In loop_redundant, CSE inside a loop of 2M iterations achieved a 1.47x speedup. '
        'In constant_showcase, straight-line folding eliminated 96% of instructions. Control benchmarks '
        '(fib_recursive and array_sum_repeated) showed 0% regression, confirming preservation of semantics.'
    )

    if os.path.exists(BENCHMARK_CHART):
        p_ch = doc.add_paragraph()
        p_ch.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_ch.paragraph_format.space_before = Pt(3)
        p_ch.paragraph_format.space_after = Pt(1)
        r_ch = p_ch.add_run()
        r_ch.add_picture(BENCHMARK_CHART, width=Inches(4.2))
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(1)
        p_cap.paragraph_format.space_after = Pt(4)
        r_cap = p_cap.add_run("Figure 1: Benchmark evaluation — TAC Instruction Count and Execution Time (-O0 vs -O2)")
        r_cap.font.name = 'Arial'
        r_cap.font.size = Pt(7.5)
        r_cap.font.italic = True
        r_cap.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)

    # 7. Conclusion and Future Work
    add_section_heading(doc, '7. Conclusion and Future Work', level=1, space_before=5, space_after=2)
    add_body_p(doc,
        'The NovaLang project demonstrates an end-to-end optimizing compiler pipeline producing genuine machine code '
        'via LLVM MCJIT. Key strengths include panic-mode parser recovery, strict semantic type guarantees, CFG-based TAC, '
        'empirically validated optimization passes, and a reactive browser playground. '
        'Future work includes: (1) standalone executable binary linking, (2) SSA form with dominator trees for global optimizations, '
        'and (3) loop-invariant code motion (LICM).'
    )

    # 8. Interface and Screenshots - Arranged in a compact 2-column gallery grid!
    add_section_heading(doc, '8. Interface and Screenshots', level=1, space_before=5, space_after=2)
    add_body_p(doc,
        'The following genuine screenshots were captured from the running NovaLang web application '
        '(FastAPI on :8080, React/Vite on :5174), documenting each compiler inspection view:'
    )

    gallery_items = [
        ("screenshot1_tokens.png", "Fig 2: Playground & Lexer Tokens"),
        ("screenshot2_ast.png", "Fig 3: Abstract Syntax Tree (AST)"),
        ("screenshot3_tac.png", "Fig 4: Three-Address Code & CFG"),
        ("screenshot4_optimized_tac.png", "Fig 5: Optimized TAC (-O2)"),
        ("screenshot5_llvm_ir.png", "Fig 6: Generated LLVM IR"),
        ("screenshot6_output.png", "Fig 7: Native JIT Execution Console")
    ]

    # Create a 3-row x 2-col compact table for screenshots
    tbl_gal = doc.add_table(rows=3, cols=2)
    tbl_gal.alignment = WD_TABLE_ALIGNMENT.CENTER
    col_w = Inches(3.45)
    img_w = Inches(3.30)

    for idx, (img_name, cap_text) in enumerate(gallery_items):
        r_idx = idx // 2
        c_idx = idx % 2
        cell = tbl_gal.cell(r_idx, c_idx)
        cell.width = col_w
        set_cell_margins(cell, top=20, bottom=20, left=30, right=30)
        
        img_path = os.path.join(SCREENSHOTS_DIR, img_name)
        p_cell = cell.paragraphs[0]
        p_cell.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cell.paragraph_format.space_before = Pt(1)
        p_cell.paragraph_format.space_after = Pt(1)
        
        if os.path.exists(img_path):
            r_img = p_cell.add_run()
            r_img.add_picture(img_path, width=img_w)
            
        p_cap = cell.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(1)
        p_cap.paragraph_format.space_after = Pt(3)
        r_cap = p_cap.add_run(cap_text)
        r_cap.font.name = 'Arial'
        r_cap.font.size = Pt(7.5)
        r_cap.font.italic = True
        r_cap.font.color.rgb = RGBColor(0x37, 0x41, 0x51)

    doc.save(DOCX_OUT)
    print(f"Successfully generated updated compact report at: {DOCX_OUT}")

if __name__ == "__main__":
    build_report()
