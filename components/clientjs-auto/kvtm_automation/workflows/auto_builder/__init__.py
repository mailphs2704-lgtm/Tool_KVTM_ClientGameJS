from __future__ import annotations

from .catalog import FUNCTION_SPECS, FunctionSpec, get_function_spec

__all__ = [
    "FUNCTION_SPECS",
    "FunctionSpec",
    "get_function_spec",
    "AutoBuilderResult",
    "AutoBuilderRunner",
    "validate_plan",
]


# Keep package import side-effect free. Recovery imports only auto_builder.catalog
# to resolve Function sale metadata. Eagerly importing runner here creates a
# circular chain:
# recovery -> auto_builder.__init__ -> runner -> FunctionOne -> recipes -> recovery.
# Builder runtime objects are therefore loaded only when a caller explicitly asks
# for them (for example the isolated worker in --mode builder).
def __getattr__(name: str):
    if name not in {"AutoBuilderResult", "AutoBuilderRunner", "validate_plan"}:
        raise AttributeError(name)

    from .runner import AutoBuilderResult, AutoBuilderRunner, validate_plan
    from .loop_delay_patch import install_function_loop_delay

    install_function_loop_delay(AutoBuilderRunner)
    exported = {
        "AutoBuilderResult": AutoBuilderResult,
        "AutoBuilderRunner": AutoBuilderRunner,
        "validate_plan": validate_plan,
    }
    globals().update(exported)
    return exported[name]
