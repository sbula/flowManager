import os
import re
import sys
import json

def calculate_approx_cc(code_lines):
    complexity = 1
    # Naive CC: Count branching keywords
    keywords = ['if', 'else', 'when', 'for', 'while', 'catch', '&&', '||', '?']
    for line in code_lines:
        for kw in keywords:
            if kw in line:
                complexity += 1
    return complexity

def scan_kotlin_files(root_dir):
    results = {}
    
    for dirpath, _, filenames in os.walk(root_dir):
        # Exclude build/target directories
        if "target" in dirpath.split(os.sep) or "build" in dirpath.split(os.sep) or ".git" in dirpath:
            continue
            
        for filename in filenames:
            if filename.endswith(".kt"):
                filepath = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(filepath, root_dir)
                results[rel_path] = []
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    for i, line in enumerate(lines):
                        stripped = line.strip()
                        # Regex to capture function name: fun followed by name, potentially with backticks
                        match = re.search(r'fun\s+(`?[a-zA-Z0-9_]+`?)', line)
                        if match:
                            func_name = match.group(1)
                            
                            # Count Lines & Complexity
                            body_lines = []
                            open_braces = 0
                            found_brace = False
                            
                            # Scan forward to find body
                            for j in range(i, len(lines)):
                                l = lines[j]
                                body_lines.append(l)
                                open_braces += l.count('{')
                                open_braces -= l.count('}')
                                
                                if '{' in l: found_brace = True
                                
                                # End of function?
                                if found_brace and open_braces == 0:
                                    break
                                    
                            line_count = len(body_lines)
                            complexity = calculate_approx_cc(body_lines)
                            
                            # FILTER: Ignore if Complexity < 3 AND Lines < 80
                            if complexity >= 3 or line_count >= 80:
                                results[rel_path].append({
                                    "name": func_name,
                                    "complexity": complexity,
                                    "lineno": i + 1,
                                    "lines": line_count,
                                    "type": "method"
                                })
                                
                    # Naive Linting (File Level)
                    file_lints = []
                    for k, l in enumerate(lines):
                        if len(l) > 120:
                            file_lints.append(f"Line {k+1}: Exceeds 120 chars")
                    
                    if file_lints:
                        if "LINT_ISSUES" not in results: results["LINT_ISSUES"] = {}
                        results["LINT_ISSUES"][rel_path] = file_lints
                        
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    return results

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 fallback_complexity.py <source_dir> <output_complexity_json> [output_lint_json]")
        sys.exit(1)
        
    root = sys.argv[1]
    out_comp = sys.argv[2]
    out_lint = sys.argv[3] if len(sys.argv) > 3 else None
    
    data = scan_kotlin_files(root)
    
    # Split Data
    lint_data = data.pop("LINT_ISSUES", {})
    
    with open(out_comp, "w") as f:
        json.dump(data, f, indent=2)
        
    if out_lint:
        with open(out_lint, "w") as f:
            json.dump(lint_data, f, indent=2)

if __name__ == "__main__":
    main()
