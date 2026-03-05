import ast
from typing import Any, Dict

# pydantic used by AtomConfig base

from .base import Atom, AtomConfig, AtomResult, AtomStatus


class AssertionAtomConfig(AtomConfig):
    condition: str


class AssertionAtom(Atom):
    """
    AssertionAtom (Deterministic Quality Gate).
    Evaluates a strict rule against the context without unsafe eval().
    """

    _OP_MAP = {
        ast.Eq: lambda a, b: a == b,
        ast.NotEq: lambda a, b: a != b,
        ast.Lt: lambda a, b: a < b,
        ast.LtE: lambda a, b: a <= b,
        ast.Gt: lambda a, b: a > b,
        ast.GtE: lambda a, b: a >= b,
        ast.In: lambda a, b: a in b,
        ast.NotIn: lambda a, b: a not in b,
    }

    def _eval_compare(self, node: ast.Compare, context: Dict[str, Any]) -> bool:
        left = self._safe_eval(node.left, context)
        for op, comparator in zip(node.ops, node.comparators):
            right = self._safe_eval(comparator, context)
            op_func = self._OP_MAP.get(type(op))
            if not op_func:
                raise ValueError(f"Unsupported operator: {type(op)}")
            if not op_func(left, right):
                return False
            left = right
        return True

    def _eval_expression(self, node: ast.Expression, context: Dict[str, Any]) -> Any:
        return self._safe_eval(node.body, context)

    def _eval_name(self, node: ast.Name, context: Dict[str, Any]) -> Any:
        if node.id in context:
            return context[node.id]
        raise NameError(f"Name '{node.id}' not found in context")

    def _eval_constant(self, node: ast.Constant, context: Dict[str, Any]) -> Any:
        return node.value

    def _eval_boolop(self, node: ast.BoolOp, context: Dict[str, Any]) -> Any:
        if isinstance(node.op, ast.And):
            return all(self._safe_eval(val, context) for val in node.values)
        if isinstance(node.op, ast.Or):
            return any(self._safe_eval(val, context) for val in node.values)
        raise ValueError(f"Unsupported BoolOp: {type(node.op)}")

    def _eval_attribute(self, node: ast.Attribute, context: Dict[str, Any]) -> Any:
        obj = self._safe_eval(node.value, context)
        if hasattr(obj, node.attr):
            return getattr(obj, node.attr)
        if isinstance(obj, dict) and node.attr in obj:
            return obj[node.attr]
        raise AttributeError(f"Attribute '{node.attr}' not found")

    _EVAL_DISPATCH = {
        ast.Expression: _eval_expression,
        ast.Name: _eval_name,
        ast.Constant: _eval_constant,
        ast.Compare: lambda self, node, ctx: self._eval_compare(node, ctx),
        ast.BoolOp: _eval_boolop,
        ast.Attribute: _eval_attribute,
    }

    def _safe_eval(self, node: ast.AST, context: Dict[str, Any]) -> Any:
        handler = self._EVAL_DISPATCH.get(type(node))
        if handler is None:
            raise ValueError(f"Unsupported AST node: {type(node)}")
        return handler(self, node, context)

    def run(self, context: Dict[str, Any]) -> AtomResult:
        cfg: AssertionAtomConfig = self.config  # type: ignore
        condition = cfg.condition
        if not condition:
            return AtomResult(
                status=AtomStatus.FAILED, message="Missing 'condition' in config"
            )

        try:
            tree = ast.parse(condition, mode="eval")
            result = self._safe_eval(tree, context)
            if result:
                return AtomResult(AtomStatus.SUCCESS, "Assertion passed")
            else:
                return AtomResult(AtomStatus.FAILED, f"Assertion failed: {condition}")
        except Exception as e:
            return AtomResult(
                AtomStatus.FAILED, f"Assertion evaluation error: {str(e)}"
            )
