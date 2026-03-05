from typing import Any, Dict

from .base import Atom, AtomConfig, AtomResult, AtomStatus


class TransformAtomConfig(AtomConfig):
    source_key: str
    target_key: str


class TransformAtom(Atom):
    """
    TransformAtom (Data Mapping).
    Adapting data between steps without needing an LLM.
    Acts as glue between standard Atoms.
    """

    def _parse_config(self, config: Dict[str, Any]) -> TransformAtomConfig:
        return TransformAtomConfig(**config)

    def _resolve_dot_path(self, source_key: str, context: Dict[str, Any]) -> Any:
        """Resolve dot-notation path (e.g. data.users.0.name) against context."""
        from typing import cast
        parts = source_key.split(".")
        current = context
        for part in parts:
            if isinstance(current, dict):
                current = cast(Any, current.get(part))
            elif isinstance(current, list) and part.isdigit():
                current = cast(Any, current[int(part)])
            else:
                raise KeyError(
                    f"Cannot resolve path segment '{part}' in '{source_key}'"
                )
        return current

    def run(self, context: Dict[str, Any]) -> AtomResult:
        from typing import cast

        config = cast(TransformAtomConfig, self.config)

        source_key = config.source_key
        target_key = config.target_key
        transform_code = getattr(config, "code", None)

        if not source_key or not target_key:
            return AtomResult(
                AtomStatus.FAILED, "Missing 'source_key' or 'target_key' in config"
            )

        if not transform_code:
            try:
                value = self._resolve_dot_path(source_key, context)
                exp_dict: Dict[str, Any] = {target_key: value}
                return AtomResult(
                    AtomStatus.SUCCESS,
                    f"Transformed {source_key} -> {target_key}",
                    exports=exp_dict,
                )
            except Exception as e:
                return AtomResult(
                    AtomStatus.FAILED, f"Transform evaluation error: {str(e)}"
                )

        # If transform_code is provided, execute it
        namespace: Dict[str, Any] = {
            "context": context,
            "source_key": source_key,
            "target_key": target_key,
        }

        try:
            exec(transform_code, {}, namespace)
        except Exception as e:
            return AtomResult(
                status=AtomStatus.FAILED, message=f"Transform code failed: {e}"
            )

        exports: Dict[str, Any] = {}
        target_val = namespace.get(target_key)
        if target_val is not None:
            exports[target_key] = target_val

        return AtomResult(
            status=AtomStatus.SUCCESS, message="Transform successful", exports=exports
        )
