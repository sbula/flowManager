import sys
import os
import re
import json
import ast

def analyze_complexity(source_code):
    """
    Calculates Cyclomatic Complexity using AST.
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []
        
    functions = []
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            complexity = 1
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.With, ast.AsyncWith)):
                    complexity += 1
                elif isinstance(child, ast.BoolOp):
                    complexity += len(child.values) - 1
            
            # Line Count
            lines = node.end_lineno - node.lineno + 1 if hasattr(node, "end_lineno") else 0
            
            functions.append({
                "name": node.name,
                "complexity": complexity,
                "lineno": node.lineno,
                "lines": lines,
                "type": "method"
            })
            
    return functions

def lint_file(source_code, filepath):
    """
    Basic Linging: Line Length, TODOs, Print Statements.
    """
    issues = []
    lines = source_code.splitlines()
    for i, line in enumerate(lines):
        if len(line) > 120:
            issues.append(f"Line {i+1}: Exceeds 120 chars ({len(line)})")
        if "# TODO" in line:
            issues.append(f"Line {i+1}: Found TODO")
        if "print(" in line:
             issues.append(f"Line {i+1}: Found print()")
             
    return issues

def scan_python_files(root_dir):
    complexity_results = {}
    lint_results = {}
    
    root_path = os.path.abspath(root_dir)
    passtest = 0
    
    for dirpath, _, filenames in os.walk(root_path):
        # Skip virtualenvs or hidden dirs
        parts = dirpath.split(os.sep)
        if "venv" in parts or "__pycache__" in parts or ".git" in parts or "target" in parts or "build" in parts: 
            continue
        
        for filename in filenames:
            if filename.endswith(".py"):
                filepath = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(filepath, root_path)
                
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        code = f.read()
                        
                    # Complexity
                    funcs = analyze_complexity(code)
                    # Filter: CC < 3 AND Lines < 80
                    filtered_funcs = [f for f in funcs if not (f['complexity'] < 3 and f['lines'] < 80)]
                    
                    if filtered_funcs:
                        complexity_results[rel_path] = filtered_funcs
                        
                    # Lint
                    issues = lint_file(code, filepath)
                    if issues:
                        lint_results[rel_path] = issues
                        
                except Exception as e:
                    print(f"Error analyzing {filepath}: {e}")
                    
    return complexity_results, lint_results

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 fallback_python.py <source_dir> <output_json_complexity> <output_json_lint>")
        sys.exit(1)
        
    source_dir = sys.argv[1]
    out_complex = sys.argv[2]
    out_lint = sys.argv[3] if len(sys.argv) > 3 else None
    
    c_res, l_res = scan_python_files(source_dir)
    
    os.makedirs(os.path.dirname(os.path.abspath(out_complex)), exist_ok=True)
    with open(out_complex, "w") as f:
        json.dump(c_res, f, indent=2)
        
    if out_lint:
        os.makedirs(os.path.dirname(os.path.abspath(out_lint)), exist_ok=True)
        with open(out_lint, "w") as f:
            json.dump(l_res, f, indent=2)
            
    print("[SUCCESS] Python Analysis Complete.")
