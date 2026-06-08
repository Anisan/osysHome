"""Thread-local reactive property chain tracking for loop detection."""
import threading
from dataclasses import dataclass, field
from typing import Optional, Set, Tuple

from app.configuration import Config
from app.logging_config import getLogger

_logger = getLogger("reactive_chain")

_local = threading.local()

_EDGE = Tuple[str, str]


@dataclass
class _ReactiveChainState:
    depth: int = 0
    stack: list = field(default_factory=list)
    visited: Set[_EDGE] = field(default_factory=set)
    block_reason: Optional[str] = None


def _get_state() -> Optional[_ReactiveChainState]:
    return getattr(_local, "chain", None)


def _ensure_state() -> _ReactiveChainState:
    state = _get_state()
    if state is None:
        state = _ReactiveChainState()
        _local.chain = state
    return state


def chain_enter(object_name: str, property_name: str) -> bool:
    """Register property change in the reactive chain. Returns False if blocked."""
    state = _ensure_state()
    edge = (object_name, property_name)
    label = f"{object_name}.{property_name}"

    max_depth = Config.REACTIVE_MAX_DEPTH if Config.REACTIVE_MAX_DEPTH is not None else 20

    if edge in state.visited:
        state.block_reason = "loop"
        _logger.error(
            "Reactive loop detected at %s (chain: %s)",
            label,
            " -> ".join(state.stack + [label]),
        )
        return False

    if state.depth >= max_depth:
        state.block_reason = "depth"
        _logger.error(
            "Reactive chain max depth (%s) exceeded at %s (chain: %s)",
            max_depth,
            label,
            " -> ".join(state.stack + [label]),
        )
        return False

    state.visited.add(edge)
    state.stack.append(label)
    state.depth += 1
    state.block_reason = None
    return True


def chain_exit() -> None:
    """Leave the current reactive chain frame."""
    state = _get_state()
    if state is None or state.depth <= 0:
        return
    if state.stack:
        label = state.stack[-1]
        state.stack.pop()
        parts = label.split(".", 1)
        if len(parts) == 2:
            state.visited.discard((parts[0], parts[1]))
    state.depth -= 1
    if state.depth <= 0:
        _local.chain = None


def chain_format() -> str:
    """Human-readable chain for logs and notifications."""
    state = _get_state()
    if not state or not state.stack:
        return ""
    return " -> ".join(state.stack)


def get_block_reason() -> Optional[str]:
    state = _get_state()
    if state is None:
        return None
    return state.block_reason
