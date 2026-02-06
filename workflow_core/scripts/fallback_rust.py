# Copyright 2026 Steve Bula @ pitBula
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import re
import subprocess
import sys


def calculate_complexity(content):
    complexity = 1
    # Keywords that increase complexity
    keywords = ["if ", "match ", "loop", "for ", "while ", "&&", "||", "?"]
    for kw in keywords:
        complexity += content.count(kw)
    return complexity


def scan_file_structure(content):
    """
    Scans Rust file for functions, tracking 'impl' blocks to assign 'Class' (Struct) names.
    """
    items = []
    lines = content.splitlines()

    # Regexes
    # impl Foo { ... or impl Foo for Bar { ... (Approximate)
    # We want "Foo" or "Bar".
    # capturing the type name before the brace.
    # strict generic parsing is hard with regex, assuming simple case for now.
    rx_impl = re.compile(
        r"impl\s+(?:<.*?>\s*)?([a-zA-Z0-9_:]+)(?:\s+for\s+([a-zA-Z0-9_:]+))?"
    )
    rx_fn = re.compile(r"fn\s+([a-zA-Z0-9_]+)\s*[<(]")

    context_stack = []  # Stack of { "type": "impl|mod", "name": "Name", "indent": 0 }

    for i, line in enumerate(lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        # Check for Impl start
        impl_match = rx_impl.search(stripped)
        if impl_match and stripped.endswith("{"):
            # It's an impl block opening
            # If "impl Foo" -> Foo
            # If "impl Trait for Foo" -> Foo (Group 2)
            name = impl_match.group(2) if impl_match.group(2) else impl_match.group(1)
            context_stack.append({"type": "impl", "name": name, "start_indent": indent})
            continue

        # Check for Fn start
        fn_match = rx_fn.search(stripped)
        if fn_match:
            # Check if it's a closure or decl? "fn name(" usually definition.
            func_name = fn_match.group(1)

            # Determine Class Name from Stack
            class_name = "(Module)"
            # Look for last 'impl' in stack
            for ctx in reversed(context_stack):
                if ctx["type"] == "impl":
                    class_name = ctx["name"]
                    break

            # Calculate Body Complexity
            # Extract body by brace counting
            body_lines = []
            open_braces = 0
            found_start = False

            # Scan forward from this line
            for j in range(i, len(lines)):
                l = lines[j]
                body_lines.append(l)
                open_braces += l.count("{")
                open_braces -= l.count("}")

                if "{" in l:
                    found_start = True
                if found_start and open_braces == 0:
                    break

            comp = calculate_complexity("\n".join(body_lines))

            items.append(
                {
                    "name": func_name,
                    "complexity": comp,
                    "lineno": i + 1,
                    "lines": len(body_lines),
                    "classname": class_name,
                }
            )

        # Check for Block End (closing brace of impl)
        # This is tricky with inconsistent indentation, but let's assume standard rustfmt
        if stripped == "}" and context_stack:
            # Check if this brace closes the last context
            # Heuristic: indentation matches start
            if indent == context_stack[-1]["start_indent"]:
                context_stack.pop()

    return items


def scan_rust_files(root_dir):
    cc_results = {}

    for dirpath, _, filenames in os.walk(root_dir):
        if (
            "target" in dirpath.split(os.sep)
            or ".git" in dirpath
            or "legacy" in dirpath.split(os.sep)
        ):
            continue

        for filename in filenames:
            if filename.endswith(".rs"):
                filepath = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(filepath, root_dir)

                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()

                    funcs = scan_file_structure(content)

                    if funcs:
                        cc_results[rel_path] = funcs
                    else:
                        # Fallback
                        comp = calculate_complexity(content)
                        if comp > 1:
                            cc_results[rel_path] = [
                                {
                                    "name": "(File Scope)",
                                    "complexity": comp,
                                    "lineno": 1,
                                    "lines": len(content.splitlines()),
                                    "classname": "(Module)",
                                }
                            ]

                except Exception as e:
                    print(f"Error scanning {filepath}: {e}")

    return cc_results


def run_clippy(root_dir):
    lint_results = {}
    try:
        cmd = ["cargo", "clippy", "--message-format=json", "--quiet", "--no-deps"]
        result = subprocess.run(cmd, cwd=root_dir, capture_output=True, text=True)

        for line in result.stdout.splitlines():
            try:
                msg = json.loads(line)
                if msg.get("reason") == "compiler-message":
                    message = msg.get("message", {})
                    level = message.get("level")
                    if level in ["error", "warning"]:
                        text = message.get("message")
                        spans = message.get("spans", [])
                        if spans:
                            primary = [s for s in spans if s.get("is_primary")][0]
                            file_name = primary.get("file_name")
                            if file_name:
                                if file_name not in lint_results:
                                    lint_results[file_name] = []
                                lint_results[file_name].append(
                                    f"[{level.upper()}] {text}"
                                )
            except:
                pass
    except Exception as e:
        lint_results["(System)"] = [f"Clippy execution failed: {e}"]

    return lint_results


def main():
    if len(sys.argv) < 4:
        sys.exit(1)

    root = sys.argv[1]
    out_cc = sys.argv[2]
    out_lint = sys.argv[3]

    print(f"Scanning Rust in {root}...")
    cc_data = scan_rust_files(root)
    lint_data = run_clippy(root)

    with open(out_cc, "w") as f:
        json.dump(cc_data, f, indent=2)

    with open(out_lint, "w") as f:
        json.dump(lint_data, f, indent=2)


if __name__ == "__main__":
    main()
