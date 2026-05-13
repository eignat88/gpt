"""Dataclass models for X++ source analysis."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Operation:
    type: str
    line: int
    snippet: str


@dataclass
class MethodVariable:
    type: str
    name: str


@dataclass
class MethodParameter:
    name: str
    type: str | None
    default: str | None


@dataclass
class MethodSignature:
    access: str | None
    static: bool
    return_type: str | None
    name: str
    parameters: list[MethodParameter]


@dataclass
class MethodSource:
    name: str
    start: int
    end: int
    start_line: int
    end_line: int
    source: str
    clean_source: str
    signature: MethodSignature | None = None
    variables: list[MethodVariable] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    operations: list[Operation] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    internal_calls: list[str] = field(default_factory=list)
    external_calls: list[str] = field(default_factory=list)
