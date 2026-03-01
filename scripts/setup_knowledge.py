import sys


def check_knowledge_env():
    print("Checking Knowledge System Environment...")

    issues = []

    # 1. Check Tree-sitter
    try:
        import tree_sitter

        print("[OK] tree-sitter installed")
    except ImportError:
        issues.append("tree-sitter not installed")

    try:
        import tree_sitter_python

        print("[OK] tree-sitter-python installed")
    except ImportError:
        issues.append("tree-sitter-python not installed")

    try:
        import tree_sitter_javascript

        print("[OK] tree-sitter-javascript installed")
    except ImportError:
        issues.append("tree-sitter-javascript not installed")

    # 2. Check Vector DB
    try:
        import chromadb

        print(f"[OK] chromadb installed: {chromadb.__version__}")
    except ImportError:
        issues.append("chromadb not installed")

    # Summary
    if issues:
        print("\nERRORS Found:")
        for issue in issues:
            print(f" - {issue}")
        sys.exit(1)
    else:
        print("\nEnvironment Verified. Knowledge System Ready.")


if __name__ == "__main__":
    check_knowledge_env()
