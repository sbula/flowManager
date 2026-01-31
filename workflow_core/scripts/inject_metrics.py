import sys
import os
import re
import json

def format_complexity_table(data):
    """
    Format JSON data list into Markdown Table.
    Input: { filename: [ {name, complexity, lineno, lines, type} ] }
    """
    rows = []
    
    # Sort by complexity desc? Or file/line?
    # Let's flatten first.
    items = []
    for filename, blocks in data.items():
        fname = filename.replace("\\", "/").split("/")[-1]
        for block in blocks:
            items.append({
                "file": fname,
                "method": block.get("name"),
                "score": block.get("complexity"),
                "line": block.get("lineno")
            })
            
    # Sort by score desc
    items.sort(key=lambda x: x["score"], reverse=True)
    
    if not items:
        return "No methods found (or below threshold)."
        
    table = ["| Method | Score | Line |", "|---|---|---|"]
    for i in items:
        table.append(f"| {i['file']}::{i['method']} | {i['score']} | {i['line']} |")
        
    return "\n".join(table)

def format_lint_table(data):
    """
    Format Lint JSON into Markdown Table.
    Input: { filename: ["issue1", "issue2"] }
    """
    rows = ["| File | Issue |", "|---|---|"]
    count = 0
    
    for filename, issues in data.items():
        fname = filename.replace("\\", "/").split("/")[-1]
        for issue in issues:
            rows.append(f"| {fname} | {issue} |")
            count += 1
            
    if count == 0:
        return "No linting issues detected."
        
    return "\n".join(rows)

def inject_content(report_path, language, content):
    if not os.path.exists(report_path):
        print(f"Report not found: {report_path}")
        return False
        
    with open(report_path, 'r', encoding='utf-8') as f:
        full_text = f.read()
        
    # Determine Header
    if language == "lint":
        header = "### Linting Issues (Detected)"
    elif language.lower() == "kotlin":
        header = "### Complexity Data (Kotlin)"
    elif language.lower() == "python":
        header = "### Complexity Data (Python)"
    else:
        header = f"### Data ({language})"
        
    # Regex: Find section
    pattern = re.compile(r"(" + re.escape(header) + r")\n.*?(?=(\n### |\n## |\Z))", re.DOTALL)
    
    new_section = f"{header}\n\n{content}\n"
    
    if pattern.search(full_text):
        print(f"Overwriting {language} section in {report_path}")
        new_text = pattern.sub(new_section, full_text)
    else:
        print(f"Appending {language} section to {report_path}")
        if "## 3. Findings & Decision Record" in full_text:
             new_text = full_text.replace("## 3. Findings & Decision Record", f"## 3. Findings & Decision Record\n\n{new_section}")
        else:
             new_text = full_text + f"\n\n{new_section}"
             
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(new_text)
        
    return True

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: inject_metrics.py <report_path> <type> <data_file>")
        sys.exit(1)
        
    report = sys.argv[1]
    lang = sys.argv[2]
    data_file = sys.argv[3]
    
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if lang == "lint":
            content = format_lint_table(data)
        else:
            # Assume complexity json
            content = format_complexity_table(data)
            
        inject_content(report, lang, content)
        print(f"[SUCCESS] Injected {lang} metrics.")
        
    except Exception as e:
        print(f"[ERROR] Failed to inject: {e}")
        sys.exit(1)
