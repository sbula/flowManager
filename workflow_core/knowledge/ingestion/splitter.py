from typing import List, Dict, Any, Optional
import tree_sitter_python
import tree_sitter_javascript
from tree_sitter import Language, Parser, Node

class CodeSplitter:
    def __init__(self):
        self.parsers = {}
        self.languages = {}
        
        # Initialize Python
        try:
            py_lang = Language(tree_sitter_python.language())
            parser = Parser(py_lang)
            self.parsers['python'] = parser
            self.languages['python'] = py_lang
        except Exception as e:
            print(f"Warning: Failed to load Python grammar: {e}")

        # Initialize JS
        try:
            js_lang = Language(tree_sitter_javascript.language())
            parser = Parser(js_lang)
            self.parsers['javascript'] = parser
            self.languages['javascript'] = js_lang
        except Exception as e:
            print(f"Warning: Failed to load JavaScript grammar: {e}")

    def split_text(self, text: str, language: str) -> List[str]:
        """
        Splits code into semantic chunks (functions, classes).
        Fallback to naive splitting if language not supported.
        """
        if language not in self.parsers:
            # Fallback: Return whole text or split by lines?
            # For now, return whole text as one chunk if small, or split large files?
            # Simple fallback: return whole text
            return [text]

        parser = self.parsers[language]
        tree = parser.parse(bytes(text, "utf8"))
        root_node = tree.root_node
        
        chunks = []
        
        # Traverse top-level nodes
        # We want to capture ClassDefinition and FunctionDefinition
        # This is language-specific logic. 
        # Using a generic approach for now based on node type names common conventions
        
        # Querying is better but requires defining queries per language.
        # Let's try simple node traversal first.
        
        cursor = tree.walk()
        
        # We can also use queries.
        # Python query: "fast" approach
        
        if language == 'python':
            chunks = self._chunk_python(root_node, text)
        elif language == 'javascript':
            chunks = self._chunk_javascript(root_node, text)
        else:
             chunks = [text]
             
        # If no chunks found (e.g. script file with no functions), return whole text
        if not chunks:
            chunks = [text]
            
        return chunks

    def _get_node_text(self, node: Node, text: str) -> str:
        return text[node.start_byte:node.end_byte]

    def _chunk_python(self, node: Node, text: str) -> List[str]:
        chunks = []
        for child in node.children:
            if child.type in ['class_definition', 'function_definition']:
                chunks.append(self._get_node_text(child, text))
            # Handle decorators? They are usually part of the definition node in latest grammar?
            # In tree-sitter-python, 'decorated_definition' wraps the function/class.
            elif child.type == 'decorated_definition':
                chunks.append(self._get_node_text(child, text))
        return chunks

    def _chunk_javascript(self, node: Node, text: str) -> List[str]:
        chunks = []
        for child in node.children:
             # JS is complex (export, default, const assignment)
             if child.type in ['class_declaration', 'function_declaration']:
                 chunks.append(self._get_node_text(child, text))
             elif child.type == 'export_statement':
                 # export const foo = ... or export class ...
                 chunks.append(self._get_node_text(child, text))
        return chunks
