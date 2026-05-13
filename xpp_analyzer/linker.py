"""Link analyzer results into a project-level method-call index."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class MethodRef:
    """Stable reference to a method inside an analyzed class."""

    class_name: str | None
    method_name: str

    @property
    def qualified_name(self) -> str:
        return f"{self.class_name}.{self.method_name}" if self.class_name else self.method_name


@dataclass
class LinkResult:
    """Project-level links between internal and external method calls."""

    methods: dict[str, MethodRef] = field(default_factory=dict)
    calls: dict[str, list[str]] = field(default_factory=dict)
    unresolved_calls: dict[str, list[str]] = field(default_factory=dict)


def link_analysis_results(results: Iterable[dict[str, Any]]) -> LinkResult:
    """Build a simple cross-document method-call index from analyzer dictionaries."""
    linked = LinkResult()
    method_name_index: dict[str, list[str]] = {}

    for result in results:
        class_name = result.get("class_info", {}).get("name")
        for method in result.get("methods", []):
            ref = MethodRef(class_name=class_name, method_name=method["name"])
            qualified_name = ref.qualified_name
            linked.methods[qualified_name] = ref
            method_name_index.setdefault(method["name"].lower(), []).append(qualified_name)

    for result in results:
        class_name = result.get("class_info", {}).get("name")
        for method in result.get("methods", []):
            caller = MethodRef(class_name=class_name, method_name=method["name"]).qualified_name
            linked.calls[caller] = []
            linked.unresolved_calls[caller] = []
            for call in method.get("calls", []):
                matches = method_name_index.get(call.lower(), [])
                if matches:
                    linked.calls[caller].extend(matches)
                else:
                    linked.unresolved_calls[caller].append(call)
    return linked


__all__ = ["LinkResult", "MethodRef", "link_analysis_results"]
