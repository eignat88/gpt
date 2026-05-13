"""Typed models returned by the X++ analyzer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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


@dataclass
class AnalysisResult:
    class_info: dict[str, Any]
    methods: list[MethodSource]
    call_graph: dict[str, list[str]]
    call_tree: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass
class ProjectInfo:
    name: str | None = None
    module: str | None = None
    owner: str | None = None
    summary: str | None = None


@dataclass
class BusinessRequirement:
    id: str | None
    text: str
    priority: str | None = None
    source_line: int | None = None


@dataclass
class TechnicalObjects:
    classes: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    forms: list[str] = field(default_factory=list)
    enums: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)


@dataclass
class CodeMatch:
    object_name: str
    object_type: str | None = None
    match_type: str | None = None
    confidence: str | None = None


@dataclass
class DocumentAnalysisResult:
    document_type: str
    source_file: str | None = None
    project: ProjectInfo = field(default_factory=ProjectInfo)
    business_requirements: list[BusinessRequirement] = field(default_factory=list)
    technical_objects: TechnicalObjects = field(default_factory=TechnicalObjects)
    algorithms: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    matches_with_code: list[CodeMatch] = field(default_factory=list)
    xpp_analysis: dict[str, Any] | None = None
