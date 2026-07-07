"""A tiny registry for config-selected implementations (topology.md §3.5, rule 5).

Implementations self-register by key; callers resolve the key from ``canopy.toml``. This is the
seam that lets ``[gateway] default_provider`` flip from ``"mock"`` to ``"anthropic"``, or a future
``bus.backend`` from ``"sqlite"`` to ``"redis"``, without any caller change — the acceptance test
for every abstraction in the actuation design.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, kind: str):
        self._kind = kind
        self._factories: dict[str, Callable[..., T]] = {}

    def register(self, key: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
        def deco(factory: Callable[..., T]) -> Callable[..., T]:
            self._factories[key] = factory
            return factory

        return deco

    def create(self, key: str, *args: object, **kwargs: object) -> T:
        if key not in self._factories:
            raise KeyError(
                f"no {self._kind} registered for {key!r}; "
                f"known: {', '.join(self.keys()) or '(none)'}"
            )
        return self._factories[key](*args, **kwargs)

    def has(self, key: str) -> bool:
        return key in self._factories

    def keys(self) -> list[str]:
        return sorted(self._factories)
