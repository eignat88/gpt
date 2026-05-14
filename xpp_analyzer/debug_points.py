"""Recommended breakpoint discovery for analyzed X++ methods."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import re

from .models import DebugPoint, DebugRouteStep, MethodSource, Operation

ENTRY_POINT_METHODS = {"main", "construct", "initfromargs", "run"}
RUNBASEBATCH_ENTRY_POINT_METHODS = {"main", "construct", "initfromargs", "run"}
ROUTE_METHOD_PRIORITY = (
    "main",
    "construct",
    "initfromargs",
    "checkwavestatus",
    "run",
    "initsalesidset",
    "validate",
    "checksalesidrange",
    "processbeforebatch",
    "fillpickingwaveitems",
    "updatesortinglocation",
    "runreservationstep",
    "runpickstep",
    "runupdsortstatstep",
    "runfinishstep",
    "setresulttofile",
)
ROUTE_METHOD_PRIORITY_INDEX = {name: index for index, name in enumerate(ROUTE_METHOD_PRIORITY)}
ROUTE_ENTRY_METHODS = set(ROUTE_METHOD_PRIORITY) | {"new", "init"}
TECHNICAL_METHOD_NAMES = {"pack", "unpack", "caption", "construct", "initbatchinfo", "initformletter"}
TECHNICAL_ROUTE_METHOD_NAMES = {
    "pack",
    "unpack",
    "caption",
    "batchinfo",
    "super",
    "value",
    "enabled",
    "control",
    "dialog",
    "dialogpostrun",
    "getfromdialog",
}
TECHNICAL_METHOD_PREFIXES = ("parm",)
TECHNICAL_ROUTE_METHOD_PREFIXES = ("parm", "dialog")
BUSINESS_METHOD_PREFIXES = (
    "run",
    "process",
    "update",
    "fill",
    "check",
    "validate",
    "finish",
    "sort",
    "pick",
    "reserve",
)
BUSINESS_METHOD_NAMES = {"initsalesidset"}
BATCH_MULTITHREAD_CONTEXT_RE = re.compile(r"\b(batch|multithread|multiThread|thread|task)\w*", re.IGNORECASE)
LOW_PRIORITY_METHODS = {"caption", "pack", "unpack"}
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
ALLOWED_RECOMMENDED_KINDS = {
    "method_entry",
    "transaction_start",
    "transaction_commit",
    "data_read",
    "data_change",
    "error_point",
    "business_call",
    "decision_point",
}


@dataclass(frozen=True)
class DebugPointOptions:
    include_low_priority: bool = False
    include_external_calls: bool = False
    max_breakpoints_per_method: int = 10
    max_total_recommended_breakpoints: int = 50
    max_debug_route_steps: int = 25
    language: str = "ru"


@dataclass
class DebugPointAnalysis:
    recommended_breakpoints: list[DebugPoint]
    debug_route: list[DebugRouteStep]
    summary: dict[str, object] = field(default_factory=dict)


DEFAULT_OPTIONS = DebugPointOptions()

OPERATION_KIND_PRIORITY = {
    "ttsBegin": ("transaction_start", "critical"),
    "ttsCommit": ("transaction_commit", "critical"),
    "select": ("data_read", "medium"),
    "while_select": ("data_read", "high"),
    "update": ("data_change", "critical"),
    "insert": ("data_change", "critical"),
    "delete": ("data_change", "critical"),
    "doUpdate": ("data_change", "critical"),
    "update_recordset": ("data_change", "critical"),
    "insert_recordset": ("data_change", "critical"),
    "delete_from": ("data_change", "critical"),
    "throw": ("error_point", "critical"),
    "error": ("error_point", "critical"),
    "warning": ("error_point", "medium"),
    "checkFailed": ("error_point", "high"),
}


METHOD_HINTS = {
    "checkwavestatus": {
        "error_point": {
            "reason": "Проверка статуса волны может остановить сценарий до резервирования и подбора.",
            "what_to_check": [
                "Проверить текущий статус волны и допустимые переходы статусов.",
                "Проверить идентификатор волны и данные, по которым определяется её готовность.",
                "Проверить, что сообщение об ошибке соответствует бизнес-причине остановки.",
            ],
        },
        "data_read": {
            "reason": "Чтение данных волны используется для проверки её текущего статуса.",
            "what_to_check": [
                "Проверить фильтр по идентификатору волны.",
                "Проверить прочитанный статус и признаки блокировки волны.",
                "Проверить, как найденная запись влияет на дальнейший сценарий batch-обработки.",
            ],
        },
    },
    "processbeforebatch": {
        "transaction_start": {
            "reason": "Перед batch-обработкой начинается транзакция подготовки волны и активной сессии.",
            "what_to_check": [
                "Проверить исходный статус волны перед изменениями.",
                "Проверить данные активной batch-сессии и пользователя.",
                "Проверить, какие подготовительные изменения попадут в одну транзакцию.",
            ],
        },
        "data_change": {
            "reason": "Изменяется статус волны и данные активной сессии перед запуском batch-обработки.",
            "what_to_check": [
                "Проверить новый статус волны и условия его установки.",
                "Проверить значения полей активной сессии перед сохранением.",
                "Проверить, что изменение выполняется в корректной транзакции подготовки batch.",
            ],
        },
        "transaction_commit": {
            "reason": "Фиксируются подготовленные изменения статуса волны и активной сессии.",
            "what_to_check": [
                "Проверить, что перед commit нет ошибок в подготовительных данных.",
                "Проверить согласованность статуса волны и активной сессии.",
                "Проверить, что последующие batch-шаги увидят зафиксированное состояние.",
            ],
        },
    },
    "checksalesidrange": {
        "data_read": {
            "reason": "Чтение строки волны используется для проверки принадлежности заказа к обрабатываемой волне.",
            "what_to_check": [
                "Проверить фильтр по PickingWaveId и SalesId.",
                "Проверить, что найденная строка волны соответствует проверяемому заказу.",
                "Проверить поведение при отсутствии строки или при дублирующих строках волны.",
            ],
        },
        "error_point": {
            "reason": "Проверка диапазона заказов может остановить обработку заказа вне текущей волны.",
            "what_to_check": [
                "Проверить SalesId, который не прошёл проверку принадлежности волне.",
                "Проверить текст сообщения для пользователя или batch-журнала.",
                "Проверить, должен ли сценарий продолжаться для остальных заказов.",
            ],
        },
    },
    "fillpickingwaveitems": {
        "data_read": {
            "reason": "Чтение исходных строк определяет набор позиций для заполнения волны подбора.",
            "what_to_check": [
                "Проверить фильтры отбора строк заказов и складских измерений.",
                "Проверить количество выбранных строк для добавления в волну.",
                "Проверить, не пропускаются ли строки из-за статусов или резервов.",
            ],
        },
        "data_change": {
            "reason": "Формируются или обновляются позиции волны подбора для дальнейших шагов обработки.",
            "what_to_check": [
                "Проверить создаваемые позиции волны и их связи с заказами.",
                "Проверить количества, номенклатуры и складские измерения перед сохранением.",
                "Проверить защиту от повторного добавления тех же строк в волну.",
            ],
        },
    },
    "updatesortinglocation": {
        "data_read": {
            "reason": "Чтение складских данных определяет локацию сортировки для волны.",
            "what_to_check": [
                "Проверить выбранные настройки склада и сортировочной зоны.",
                "Проверить фильтры по волне, складу и локации.",
                "Проверить fallback-сценарий, если сортировочная локация не найдена.",
            ],
        },
        "data_change": {
            "reason": "Обновляется сортировочная локация, от которой зависит дальнейший подбор и сортировка.",
            "what_to_check": [
                "Проверить рассчитанную сортировочную локацию перед записью.",
                "Проверить строки волны, которым назначается новая локация.",
                "Проверить влияние изменения на последующие шаги подбора.",
            ],
        },
    },
    "runreservationstep": {
        "data_read": {
            "reason": "Чтение строк волны готовит данные для шага резервирования.",
            "what_to_check": [
                "Проверить строки, выбранные для резервирования.",
                "Проверить доступные остатки и складские измерения.",
                "Проверить порядок обработки строк при частичном резервировании.",
            ],
        },
        "data_change": {
            "reason": "Шаг резервирования изменяет резервы и состояние строк волны.",
            "what_to_check": [
                "Проверить резервируемое количество по каждой строке.",
                "Проверить изменения складских резервов и статусов строк.",
                "Проверить откат или обработку частичного резервирования при ошибках.",
            ],
        },
        "error_point": {
            "reason": "Ошибка резервирования определяет, можно ли продолжать обработку волны.",
            "what_to_check": [
                "Проверить строку и остаток, на которых возникла ошибка.",
                "Проверить допустимость частичного резервирования.",
                "Проверить сообщение в batch-журнале для последующей диагностики.",
            ],
        },
    },
    "runpickstep": {
        "data_read": {
            "reason": "Чтение зарезервированных строк определяет задания для шага подбора.",
            "what_to_check": [
                "Проверить строки, готовые к подбору после резервирования.",
                "Проверить складские локации, партии и серийные номера.",
                "Проверить, что исключены строки без достаточного резерва.",
            ],
        },
        "data_change": {
            "reason": "Шаг подбора изменяет состояние строк и складских операций волны.",
            "what_to_check": [
                "Проверить создаваемые или обновляемые задания подбора.",
                "Проверить количества подбора и складские измерения перед сохранением.",
                "Проверить переход статусов после успешного подбора.",
            ],
        },
        "error_point": {
            "reason": "Ошибка подбора останавливает или ограничивает выполнение складского шага.",
            "what_to_check": [
                "Проверить строку волны и локацию, на которых возникла ошибка.",
                "Проверить доступность зарезервированного остатка для подбора.",
                "Проверить корректность сообщения для оператора склада.",
            ],
        },
    },
    "runfinishstep": {
        "data_read": {
            "reason": "Чтение итоговых данных волны нужно для проверки готовности к завершению.",
            "what_to_check": [
                "Проверить строки волны после резервирования и подбора.",
                "Проверить наличие незавершённых или ошибочных строк.",
                "Проверить итоговые количества перед закрытием волны.",
            ],
        },
        "data_change": {
            "reason": "Финальный шаг закрывает волну и фиксирует итоговые статусы обработки.",
            "what_to_check": [
                "Проверить финальный статус волны перед сохранением.",
                "Проверить итоговые статусы строк и связанных складских операций.",
                "Проверить, что завершение не скрывает незавершённые ошибки предыдущих шагов.",
            ],
        },
        "transaction_commit": {
            "reason": "Фиксируется финальное состояние волны после всех складских шагов.",
            "what_to_check": [
                "Проверить, что все обязательные шаги успешно выполнены до commit.",
                "Проверить итоговую согласованность заголовка и строк волны.",
                "Проверить, что повторный запуск не создаст дубли или неверные статусы.",
            ],
        },
    },
}

CHECKS_BY_KIND = {
    "method_entry": [
        "Проверить входные параметры метода.",
        "Проверить начальное состояние объекта и ключевых переменных.",
        "Проверить первый выбранный сценарий выполнения.",
    ],
    "transaction_start": [
        "Проверить состояние ключевых переменных перед транзакцией.",
        "Проверить, какие методы выполняются внутри транзакции.",
        "Проверить, что все изменения закрываются корректным ttsCommit.",
    ],
    "transaction_commit": [
        "Проверить, что данные были валидированы перед фиксацией.",
        "Проверить отсутствие незавершённых побочных изменений.",
        "Проверить, что исключения не оставят данные в частично изменённом состоянии.",
    ],
    "data_read": [
        "Проверить фильтры, join-условия и ожидаемое количество записей.",
        "Проверить необходимость forUpdate и блокировок.",
        "Проверить, как прочитанные данные влияют на ветвления и изменения.",
    ],
    "data_change": [
        "Проверить значения полей перед изменением.",
        "Проверить корректность выбранной записи.",
        "Проверить, что изменение выполняется в нужной транзакции.",
    ],
    "error_point": [
        "Проверить условия возникновения ошибки.",
        "Проверить значения переменных перед ошибкой.",
        "Проверить, не нарушается ли целостность данных.",
    ],
    "business_call": [
        "Проверить входные данные перед вызовом метода.",
        "Проверить, какие таблицы и поля изменяет вызываемый метод.",
        "При необходимости перейти внутрь метода пошагово.",
    ],
    "internal_call": [
        "Проверить, влияет ли вызов на текущий сценарий.",
        "При необходимости перейти внутрь метода пошагово.",
    ],
    "external_call": [
        "Проверить параметры внешнего вызова.",
        "Проверить ожидаемые побочные эффекты внешнего класса.",
    ],
    "decision_point": [
        "Проверить условие ветвления.",
        "Проверить значения переменных, влияющих на выбор ветки.",
    ],
}


def _is_comment_or_blank(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*")


def _entry_location(method: MethodSource) -> tuple[int, str]:
    for offset, line in enumerate(method.source.splitlines(), start=0):
        stripped = line.strip()
        lower = stripped.lower()
        if _is_comment_or_blank(line) or lower.startswith("source #") or lower == "{":
            continue
        if method.signature and re.search(rf"\b{re.escape(method.signature.name)}\s*\(", stripped, re.IGNORECASE):
            return method.start_line + offset, stripped
    for offset, line in enumerate(method.source.splitlines(), start=0):
        stripped = line.strip()
        if _is_comment_or_blank(line) or stripped == "{" or stripped == "}":
            continue
        if stripped.lower().startswith("source #"):
            continue
        return method.start_line + offset, stripped
    return method.start_line, method.name


def _normalized_kind(kind: str) -> str:
    return "method_entry" if kind == "entry_point" else kind


def _method_hint(method: str, kind: str) -> dict[str, object]:
    return METHOD_HINTS.get(method.lower(), {}).get(kind, {})


def _what_to_check(kind: str, method: str | None = None) -> list[str]:
    if method is not None:
        hint = _method_hint(method, kind)
        checks = hint.get("what_to_check")
        if isinstance(checks, list):
            return list(checks)
    return list(CHECKS_BY_KIND.get(kind, CHECKS_BY_KIND["decision_point"]))


def _point(*, method: str, line: int, kind: str, priority: str, reason: str, snippet: str) -> DebugPoint:
    normalized_kind = _normalized_kind(kind)
    hint = _method_hint(method, normalized_kind)
    hinted_reason = hint.get("reason")
    return DebugPoint(
        id="",
        method=method,
        line=line,
        kind=normalized_kind,
        priority=priority,
        reason=hinted_reason if isinstance(hinted_reason, str) else reason,
        snippet=snippet,
        what_to_check=_what_to_check(normalized_kind, method),
    )


def _operation_reason(kind: str, operation: Operation) -> str:
    if kind == "transaction_start":
        return "Начало транзакционного блока."
    if kind == "transaction_commit":
        return "Фиксация изменений транзакции."
    if kind == "data_read":
        if operation.type == "while_select":
            return "Чтение данных в цикле, которое может влиять на дальнейшее выполнение алгоритма."
        return "Чтение данных, которое может влиять на дальнейшее выполнение алгоритма."
    if kind == "data_change":
        return "Изменение сохранённых данных."
    if kind == "error_point":
        snippet = operation.snippet.lower()
        if "throw" in snippet:
            return "Исключение прерывает выполнение метода."
        if "checkfailed" in snippet:
            return "Проверка может прервать выполнение или изменить дальнейший сценарий."
        return "Сообщение об ошибке или предупреждении может изменить сценарий выполнения."
    return "Важная точка выполнения метода."


def _is_check_or_validate_method(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith("check") or lowered.startswith("validate")


def _has_for_update(snippet: str) -> bool:
    return bool(re.search(r"\bforupdate\b", snippet, re.IGNORECASE))


def _operation_point(method: MethodSource, operation: Operation) -> DebugPoint | None:
    mapping = OPERATION_KIND_PRIORITY.get(operation.type)
    if mapping is None:
        return None

    kind, priority = mapping
    if kind == "data_read" and _has_for_update(operation.snippet):
        priority = "high"
    elif kind == "data_read" and _is_check_or_validate_method(method.name):
        priority = "medium"

    if kind == "error_point":
        lower = operation.snippet.lower()
        if "throw" in lower:
            priority = "critical"
        elif "checkfailed" in lower:
            priority = "high"
    return _point(
        method=method.name,
        line=operation.line,
        kind=kind,
        priority=priority,
        reason=_operation_reason(kind, operation),
        snippet=operation.snippet,
    )


def _is_technical_method(name: str) -> bool:
    lowered = name.lower()
    return lowered in TECHNICAL_METHOD_NAMES or any(lowered.startswith(prefix) for prefix in TECHNICAL_METHOD_PREFIXES)


def _is_technical_route_method(name: str) -> bool:
    lowered = name.lower()
    return lowered in TECHNICAL_ROUTE_METHOD_NAMES or any(
        lowered.startswith(prefix) for prefix in TECHNICAL_ROUTE_METHOD_PREFIXES
    )


def _is_route_method(name: str) -> bool:
    lowered = name.lower()
    return lowered in ROUTE_ENTRY_METHODS or _is_business_method(lowered)


def _is_business_method(name: str) -> bool:
    lowered = name.lower()
    if _is_technical_method(lowered):
        return False
    return lowered in BUSINESS_METHOD_NAMES or any(lowered.startswith(prefix) for prefix in BUSINESS_METHOD_PREFIXES)


def _is_low_priority_method(name: str) -> bool:
    lowered = name.lower()
    return _is_technical_method(lowered) or lowered in LOW_PRIORITY_METHODS


def _has_batch_multithread_context(method: MethodSource, class_info: dict | None = None) -> bool:
    return _is_runbasebatch_class(class_info) or bool(BATCH_MULTITHREAD_CONTEXT_RE.search(method.clean_source))


def _line_for_offset(method: MethodSource, offset: int) -> tuple[int, str]:
    line = method.start_line + method.clean_source.count("\n", 0, offset)
    line_start = method.source.rfind("\n", 0, offset) + 1
    line_end = method.source.find("\n", offset)
    if line_end == -1:
        line_end = len(method.source)
    return line, method.source[line_start:line_end].strip()


def _internal_call_points(method: MethodSource, method_names: set[str], class_info: dict | None = None) -> list[DebugPoint]:
    points: list[DebugPoint] = []
    for call in method.internal_calls:
        call_lower = call.lower()
        patterns = [re.compile(rf"\bthis\s*\.\s*{re.escape(call)}\s*\(", re.IGNORECASE)]
        if call_lower in method_names:
            patterns.append(re.compile(rf"(?<!::)\b{re.escape(call)}\s*\(", re.IGNORECASE))
        seen_offsets: set[int] = set()
        for pattern in patterns:
            for match in pattern.finditer(method.clean_source):
                if match.start() in seen_offsets:
                    continue
                seen_offsets.add(match.start())
                line, snippet = _line_for_offset(method, match.start())
                if call_lower == "createnextchildtasks":
                    if not _has_batch_multithread_context(method, class_info):
                        continue
                    kind = "business_call"
                    priority = "medium"
                    reason = f"Вызов batch/multithread-метода {call}."
                elif _is_business_method(call):
                    kind = "business_call"
                    priority = "high"
                    reason = f"Вызов ключевого бизнес-метода {call}."
                else:
                    kind = "internal_call"
                    priority = "low" if _is_low_priority_method(call) else "low"
                    reason = f"Вызов внутреннего метода класса {call}."
                points.append(_point(method=method.name, line=line, kind=kind, priority=priority, reason=reason, snippet=snippet))
    return points


def _external_call_points(method: MethodSource) -> list[DebugPoint]:
    points: list[DebugPoint] = []
    pattern = re.compile(r"\b(?P<class>[A-Za-z_]\w*)\s*::\s*(?P<method>[A-Za-z_]\w*)\s*\(", re.IGNORECASE)
    for match in pattern.finditer(method.clean_source):
        line, snippet = _line_for_offset(method, match.start())
        external_method = match.group("method")
        priority = "medium" if _is_business_method(external_method) and external_method.lower() != "construct" else "low"
        points.append(
            _point(
                method=method.name,
                line=line,
                kind="external_call",
                priority=priority,
                reason=f"Вызов внешнего метода {match.group('class')}::{external_method}.",
                snippet=snippet,
            )
        )
    return points


def _deduplicate(points: list[DebugPoint]) -> tuple[list[DebugPoint], int]:
    seen: set[tuple[str, int, str, str]] = set()
    result: list[DebugPoint] = []
    for point in sorted(points, key=lambda item: (item.line, PRIORITY_ORDER.get(item.priority, 99), item.kind)):
        key = (point.method, point.line, point.kind, point.snippet.strip())
        if key in seen:
            continue
        seen.add(key)
        result.append(point)
    return result, len(points) - len(result)


def _should_recommend(point: DebugPoint, options: DebugPointOptions) -> bool:
    if point.kind == "external_call" and not options.include_external_calls:
        return False
    if point.priority == "low" and not options.include_low_priority:
        return False
    return point.kind in ALLOWED_RECOMMENDED_KINDS or (point.kind == "external_call" and options.include_external_calls)


def _is_while_select_point(point: DebugPoint) -> bool:
    return bool(re.search(r"\bwhile\s+select\b", point.snippet, re.IGNORECASE))


def _important_data_read_points(points: list[DebugPoint]) -> list[DebugPoint]:
    important = [
        point
        for point in points
        if point.kind == "data_read"
        and (
            _is_while_select_point(point)
            or _has_for_update(point.snippet)
            or _is_check_or_validate_method(point.method)
        )
    ]
    return sorted(important, key=lambda point: (PRIORITY_ORDER.get(point.priority, 99), point.line, point.method))


def _point_identity(point: DebugPoint) -> tuple[str, int, str, str]:
    return point.method, point.line, point.kind, point.snippet.strip()


def _limit_recommended(points: list[DebugPoint], options: DebugPointOptions) -> list[DebugPoint]:
    by_method: dict[str, list[DebugPoint]] = defaultdict(list)
    ordered = sorted(points, key=lambda point: (PRIORITY_ORDER.get(point.priority, 99), point.line, point.kind))
    for point in ordered:
        bucket = by_method[point.method]
        if len(bucket) < options.max_breakpoints_per_method:
            bucket.append(point)

    data_read_candidates = _important_data_read_points(points) or [point for point in ordered if point.kind == "data_read"]
    reserved_data_read = data_read_candidates[0] if data_read_candidates else None

    limited = [point for bucket in by_method.values() for point in bucket]
    if reserved_data_read is not None and _point_identity(reserved_data_read) not in {_point_identity(point) for point in limited}:
        limited.append(reserved_data_read)

    limited.sort(key=lambda point: (PRIORITY_ORDER.get(point.priority, 99), point.line, point.kind))
    limited = limited[: options.max_total_recommended_breakpoints]

    if reserved_data_read is not None and _point_identity(reserved_data_read) not in {_point_identity(point) for point in limited}:
        if limited:
            limited[-1] = reserved_data_read
        else:
            limited = [reserved_data_read]

    seen: set[tuple[str, int, str, str]] = set()
    deduped_limited: list[DebugPoint] = []
    for point in limited:
        key = _point_identity(point)
        if key in seen:
            continue
        seen.add(key)
        deduped_limited.append(point)

    deduped_limited.sort(key=lambda point: (point.line, PRIORITY_ORDER.get(point.priority, 99), point.kind))
    return deduped_limited


def _route_reason(point: DebugPoint) -> str:
    if point.kind == "method_entry":
        if point.method.lower() == "main":
            return "Точка запуска класса."
        if point.method.lower() == "run":
            return "Основной сценарий выполнения."
        if point.method.lower() == "construct":
            return "Создание экземпляра класса."
        return "Вход в метод класса."
    if point.kind == "business_call":
        return point.reason
    if point.kind == "internal_call":
        return point.reason
    if point.kind == "transaction_start":
        return "Начало транзакции."
    if point.kind == "data_change":
        return "Изменение данных."
    if point.kind == "error_point":
        return "Обработка ошибки или исключения."
    return point.reason


def _route_sort_key(method: MethodSource) -> tuple[int, int, int]:
    method_priority = ROUTE_METHOD_PRIORITY_INDEX.get(method.name.lower())
    if method_priority is not None:
        return 0, method_priority, method.start_line
    return 1, method.start_line, 0


def _build_route(methods: list[MethodSource], options: DebugPointOptions) -> tuple[list[DebugRouteStep], int]:
    route_methods: list[MethodSource] = []
    filtered_technical_count = 0

    for method in methods:
        if _is_technical_route_method(method.name):
            filtered_technical_count += 1
            continue
        if _is_route_method(method.name):
            route_methods.append(method)

    route_methods.sort(key=_route_sort_key)

    route: list[DebugRouteStep] = []
    seen: set[str] = set()
    for method in route_methods:
        if len(route) >= options.max_debug_route_steps:
            break
        method_key = method.name.lower()
        if method_key in seen:
            continue
        seen.add(method_key)
        line, snippet = _entry_location(method)
        point = _point(
            method=method.name,
            line=line,
            kind="method_entry",
            priority="high",
            reason="Верхнеуровневая точка маршрута отладки.",
            snippet=snippet,
        )
        route.append(
            DebugRouteStep(
                step=len(route) + 1,
                method=method.name,
                line=line,
                kind="method_entry",
                reason=_route_reason(point),
            )
        )
    return route, filtered_technical_count


def _is_runbasebatch_class(class_info: dict | None) -> bool:
    extends = class_info.get("extends") if class_info else None
    return isinstance(extends, str) and extends.lower() == "runbasebatch"


def build_debug_point_analysis(
    methods: list[MethodSource],
    options: DebugPointOptions = DEFAULT_OPTIONS,
    class_info: dict | None = None,
) -> DebugPointAnalysis:
    """Build recommended breakpoints, debug route and breakpoint statistics."""
    method_names = {method.name.lower() for method in methods}
    entry_point_methods = set(ENTRY_POINT_METHODS)
    if _is_runbasebatch_class(class_info):
        entry_point_methods.update(RUNBASEBATCH_ENTRY_POINT_METHODS)
    candidates: list[DebugPoint] = []

    for method in methods:
        method_name_lower = method.name.lower()
        if method_name_lower in entry_point_methods:
            line, snippet = _entry_location(method)
            reason = {
                "main": "Основная точка запуска класса.",
                "run": "Основной сценарий выполнения класса.",
                "construct": "Создание экземпляра текущего класса.",
                "initfromargs": "Инициализация класса из аргументов запуска.",
            }.get(method_name_lower, "Вход в метод класса.")
            candidates.append(
                _point(method=method.name, line=line, kind="method_entry", priority="high", reason=reason, snippet=snippet)
            )

        for operation in method.operations:
            point = _operation_point(method, operation)
            if point is not None:
                candidates.append(point)

        candidates.extend(_internal_call_points(method, method_names, class_info))
        candidates.extend(_external_call_points(method))

    deduped, deduplicated_count = _deduplicate(candidates)
    filtered_low_priority_count = sum(1 for point in deduped if point.priority == "low" and not options.include_low_priority)
    recommended_candidates = [point for point in deduped if _should_recommend(point, options)]
    recommended = _limit_recommended(recommended_candidates, options)
    for index, point in enumerate(recommended, start=1):
        point.id = f"BP{index:03d}"

    route, route_filtered_technical_count = _build_route(methods, options)
    priority_counts = Counter(point.priority for point in recommended)
    kind_counts = Counter(point.kind for point in recommended)
    summary = {
        "total_recommended": len(recommended),
        "total_route_steps": len(route),
        "by_priority": dict(priority_counts),
        "by_kind": dict(kind_counts),
        "filtered_low_priority_count": filtered_low_priority_count,
        "route_filtered_technical_count": route_filtered_technical_count,
        "deduplicated_count": deduplicated_count,
    }
    return DebugPointAnalysis(recommended_breakpoints=recommended, debug_route=route, summary=summary)


def find_debug_points(methods: list[MethodSource], class_info: dict | None = None) -> list[DebugPoint]:
    """Build sorted recommended breakpoint points from analyzed methods."""
    return build_debug_point_analysis(methods, class_info=class_info).recommended_breakpoints
