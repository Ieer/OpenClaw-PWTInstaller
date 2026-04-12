from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


VoiceCommandKind = Literal[
    "create_task",
    "add_comment",
    "set_status",
    "handoff_task",
    "control_agent",
]

VoiceCommandParseOutcome = Literal["ignored", "parsed", "rejected"]

_TASK_REF_RE = r"[A-Za-z0-9][A-Za-z0-9-]{5,}"

_COMMAND_HEAD_PREFIXES = (
    "创建任务",
    "新增任务",
    "添加任务",
    "comment task",
    "评论任务",
    "留言任务",
    "给任务",
    "任务",
    "完成任务",
    "关闭任务",
    "转交任务",
    "移交任务",
    "handoff task",
    "start agent",
    "stop agent",
    "restart agent",
    "启动 agent",
    "停止 agent",
    "重启 agent",
)

_LABEL_ALIASES = {
    "assignee": {"assignee", "owner", "负责人", "指派给", "给", "to"},
    "title": {"title", "标题"},
    "tags": {"tags", "tag", "标签"},
    "status": {"status", "状态"},
    "problem": {"problem", "问题"},
    "context": {"context", "上下文"},
    "expected_output": {"expected", "output", "expected_output", "交付", "输出"},
    "artifact_refs": {"artifacts", "artifact_refs", "artifact", "附件", "引用"},
    "review_gate": {"review", "review_gate", "审核", "审阅"},
}

_STATUS_ALIASES = {
    "INBOX": {"INBOX", "inbox", "收件箱", "待收"},
    "ASSIGNED": {"ASSIGNED", "assigned", "已分配", "分配", "指派"},
    "IN PROGRESS": {"IN PROGRESS", "in progress", "进行中", "处理中", "执行中", "处理中"},
    "REVIEW": {"REVIEW", "review", "待审核", "审阅", "复核", "审核中"},
    "DONE": {"DONE", "done", "完成", "已完成", "结束", "关闭"},
}

_BOOL_TRUE = {"1", "true", "yes", "on", "是", "要", "开启", "需要", "需要审核"}
_BOOL_FALSE = {"0", "false", "no", "off", "否", "不要", "关闭", "无需", "无需审核"}


@dataclass
class VoiceCommand:
    kind: VoiceCommandKind
    normalized_text: str
    prefix_used: str | None = None
    task_ref: str | None = None
    title: str | None = None
    assignee: str | None = None
    tags: list[str] = field(default_factory=list)
    status: str | None = None
    comment_body: str | None = None
    to_agent: str | None = None
    problem: str | None = None
    context: str | None = None
    expected_output: str | None = None
    artifact_refs: list[str] = field(default_factory=list)
    review_gate: bool = True
    control_action: str | None = None
    control_agent: str | None = None


@dataclass
class VoiceCommandParseResult:
    outcome: VoiceCommandParseOutcome
    normalized_text: str
    prefix_used: str | None = None
    command: VoiceCommand | None = None
    reason: str | None = None


def parse_voice_command(
    text: str,
    *,
    prefixes: list[str],
    require_prefix: bool,
) -> VoiceCommandParseResult:
    normalized = _compact_whitespace(text)
    if not normalized:
        return VoiceCommandParseResult(outcome="ignored", normalized_text="")

    prefix_used, command_text = _strip_prefix(normalized, prefixes)
    if prefix_used:
        command_text = _trim_leading_command_separator(command_text)
    elif require_prefix:
        return VoiceCommandParseResult(outcome="ignored", normalized_text=normalized)
    else:
        command_text = normalized

    if not command_text:
        if prefix_used:
            return VoiceCommandParseResult(
                outcome="rejected",
                normalized_text=normalized,
                prefix_used=prefix_used,
                reason="empty command after prefix",
            )
        return VoiceCommandParseResult(outcome="ignored", normalized_text=normalized)

    for parser in (
        _parse_create_task,
        _parse_comment,
        _parse_status_change,
        _parse_handoff,
        _parse_agent_control,
    ):
        command = parser(command_text, prefix_used)
        if command is not None:
            return VoiceCommandParseResult(
                outcome="parsed",
                normalized_text=normalized,
                prefix_used=prefix_used,
                command=command,
            )

    if prefix_used or _looks_like_command(command_text):
        return VoiceCommandParseResult(
            outcome="rejected",
            normalized_text=normalized,
            prefix_used=prefix_used,
            reason="unsupported or malformed voice command",
        )

    return VoiceCommandParseResult(outcome="ignored", normalized_text=normalized)


def summarize_voice_command(command: VoiceCommand) -> str:
    if command.kind == "create_task":
        assignee = f" for {command.assignee}" if command.assignee else ""
        title = str(command.title or "untitled task")
        return f"create task{assignee}: {title}"
    if command.kind == "add_comment":
        return f"comment on task {command.task_ref}"
    if command.kind == "set_status":
        return f"move task {command.task_ref} to {command.status}"
    if command.kind == "handoff_task":
        return f"handoff task {command.task_ref} to {command.to_agent}"
    if command.kind == "control_agent":
        return f"{command.control_action} agent {command.control_agent}"
    return command.kind


def _parse_create_task(text: str, prefix_used: str | None) -> VoiceCommand | None:
    sections = _split_sections(text)
    if not sections:
        return None
    header, labels = sections[0], _parse_labeled_sections(sections[1:])

    patterns = (
        r"^(?:创建|新增|添加)(?:一个)?任务(?:\s*(?:给|指派给)\s*(?P<assignee>[A-Za-z0-9_-]+))?(?:(?:\s*[:：]\s*)|\s+)(?P<title>.+)$",
        r"^(?:create|add)\s+task(?:\s+(?:for|to)\s+(?P<assignee>[A-Za-z0-9_-]+))?(?:(?:\s*[:：]\s*)|\s+)(?P<title>.+)$",
        r"^(?:创建|新增|添加)(?:一个)?任务$",
        r"^(?:create|add)\s+task$",
    )
    assignee = _get_labeled_value(labels, "assignee")
    title = _get_labeled_value(labels, "title")
    for pattern in patterns:
        match = re.match(pattern, header, flags=re.IGNORECASE)
        if not match:
            continue
        assignee = assignee or _clean_value(match.groupdict().get("assignee"))
        title = title or _clean_value(match.groupdict().get("title"))
        break
    else:
        return None

    if not title:
        return None

    status = _normalize_status(_get_labeled_value(labels, "status")) or "INBOX"
    tags = _split_csv_like(_get_labeled_value(labels, "tags"))
    return VoiceCommand(
        kind="create_task",
        normalized_text=text,
        prefix_used=prefix_used,
        title=title,
        assignee=assignee,
        status=status,
        tags=tags,
    )


def _parse_comment(text: str, prefix_used: str | None) -> VoiceCommand | None:
    patterns = (
        rf"^(?:评论|留言)(?:任务)?\s*(?P<task>{_TASK_REF_RE})(?:(?:\s*[:：]\s*)|\s+)(?P<body>.+)$",
        rf"^(?:给任务)\s*(?P<task>{_TASK_REF_RE})\s*(?:评论|留言)(?:(?:\s*[:：]\s*)|\s+)(?P<body>.+)$",
        rf"^(?:comment)\s+task\s*(?P<task>{_TASK_REF_RE})(?:(?:\s*[:：]\s*)|\s+)(?P<body>.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        body = _clean_value(match.groupdict().get("body"))
        if not body:
            return None
        return VoiceCommand(
            kind="add_comment",
            normalized_text=text,
            prefix_used=prefix_used,
            task_ref=_clean_value(match.groupdict().get("task")),
            comment_body=body,
        )
    return None


def _parse_status_change(text: str, prefix_used: str | None) -> VoiceCommand | None:
    shorthand_patterns = (
        rf"^(?:完成|关闭)任务\s*(?P<task>{_TASK_REF_RE})$",
        rf"^(?:finish|close)\s+task\s*(?P<task>{_TASK_REF_RE})$",
    )
    for pattern in shorthand_patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if match:
            return VoiceCommand(
                kind="set_status",
                normalized_text=text,
                prefix_used=prefix_used,
                task_ref=_clean_value(match.groupdict().get("task")),
                status="DONE",
            )

    patterns = (
        rf"^(?:把|将)?任务\s*(?P<task>{_TASK_REF_RE})\s*(?:状态)?(?:设为|改为|标记为|切换到)\s*(?P<status>.+)$",
        rf"^(?:set|move)\s+task\s*(?P<task>{_TASK_REF_RE})\s+(?:status\s+)?(?:to)\s*(?P<status>.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        status = _normalize_status(match.groupdict().get("status"))
        if not status:
            return None
        return VoiceCommand(
            kind="set_status",
            normalized_text=text,
            prefix_used=prefix_used,
            task_ref=_clean_value(match.groupdict().get("task")),
            status=status,
        )
    return None


def _parse_handoff(text: str, prefix_used: str | None) -> VoiceCommand | None:
    sections = _split_sections(text)
    if not sections:
        return None
    header, labels = sections[0], _parse_labeled_sections(sections[1:])
    patterns = (
        rf"^(?:转交|移交)(?:任务)?\s*(?P<task>{_TASK_REF_RE})\s*(?:给)\s*(?P<to>[A-Za-z0-9_-]+)$",
        rf"^(?:handoff)\s+task\s*(?P<task>{_TASK_REF_RE})\s+(?:to)\s*(?P<to>[A-Za-z0-9_-]+)$",
    )

    task_ref = None
    to_agent = _get_labeled_value(labels, "assignee")
    for pattern in patterns:
        match = re.match(pattern, header, flags=re.IGNORECASE)
        if not match:
            continue
        task_ref = _clean_value(match.groupdict().get("task"))
        to_agent = to_agent or _clean_value(match.groupdict().get("to"))
        break
    else:
        return None

    problem = _get_labeled_value(labels, "problem")
    context = _get_labeled_value(labels, "context")
    expected_output = _get_labeled_value(labels, "expected_output")
    artifact_refs = _split_csv_like(_get_labeled_value(labels, "artifact_refs"))
    review_gate = _parse_bool(_get_labeled_value(labels, "review_gate"), default=True)
    if not all([task_ref, to_agent, problem, context, expected_output]) or not artifact_refs:
        return None

    return VoiceCommand(
        kind="handoff_task",
        normalized_text=text,
        prefix_used=prefix_used,
        task_ref=task_ref,
        to_agent=to_agent,
        problem=problem,
        context=context,
        expected_output=expected_output,
        artifact_refs=artifact_refs,
        review_gate=review_gate,
    )


def _parse_agent_control(text: str, prefix_used: str | None) -> VoiceCommand | None:
    patterns = (
        r"^(?P<action>启动|停止|重启)\s*(?:agent|容器)?\s*(?P<agent>[A-Za-z0-9_-]+)$",
        r"^(?P<action>start|stop|restart)\s+agent\s*(?P<agent>[A-Za-z0-9_-]+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        action = _normalize_control_action(match.groupdict().get("action"))
        agent = _clean_value(match.groupdict().get("agent"))
        if not action or not agent:
            return None
        return VoiceCommand(
            kind="control_agent",
            normalized_text=text,
            prefix_used=prefix_used,
            control_action=action,
            control_agent=agent,
        )
    return None


def _strip_prefix(text: str, prefixes: list[str]) -> tuple[str | None, str]:
    lowered = text.casefold()
    for prefix in prefixes:
        normalized_prefix = _compact_whitespace(prefix)
        if not normalized_prefix:
            continue
        prefix_casefold = normalized_prefix.casefold()
        if lowered.startswith(prefix_casefold):
            return normalized_prefix, text[len(normalized_prefix):].strip()
    return None, text


def _trim_leading_command_separator(text: str) -> str:
    return re.sub(r"^[\s,，。.!！:?：-]+", "", text or "").strip()


def _split_sections(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[;；]", text) if part and part.strip()]


def _parse_labeled_sections(sections: list[str]) -> dict[str, str]:
    labeled: dict[str, str] = {}
    for section in sections:
        match = re.match(r"^(?P<label>[^:：]{1,32})\s*[:：]\s*(?P<value>.+)$", section)
        if not match:
            continue
        label = _normalize_label(match.group("label"))
        value = _clean_value(match.group("value"))
        if label and value:
            labeled[label] = value
    return labeled


def _normalize_label(label: str | None) -> str | None:
    raw = _clean_value(label)
    if not raw:
        return None
    lowered = raw.casefold()
    for canonical, aliases in _LABEL_ALIASES.items():
        if lowered in {alias.casefold() for alias in aliases}:
            return canonical
    return None


def _get_labeled_value(labels: dict[str, str], key: str) -> str | None:
    value = labels.get(key)
    return _clean_value(value)


def _split_csv_like(raw: str | None) -> list[str]:
    value = _clean_value(raw)
    if not value:
        return []
    items = []
    seen: set[str] = set()
    for item in re.split(r"[,，、|]", value):
        cleaned = _clean_value(item)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        items.append(cleaned)
    return items


def _normalize_status(raw: str | None) -> str | None:
    value = _clean_value(raw)
    if not value:
        return None
    lowered = value.casefold()
    for canonical, aliases in _STATUS_ALIASES.items():
        if lowered in {alias.casefold() for alias in aliases}:
            return canonical
    return None


def _normalize_control_action(raw: str | None) -> str | None:
    value = _clean_value(raw)
    if not value:
        return None
    lowered = value.casefold()
    if lowered in {"启动", "start"}:
        return "start"
    if lowered in {"停止", "stop"}:
        return "stop"
    if lowered in {"重启", "restart"}:
        return "restart"
    return None


def _parse_bool(raw: str | None, *, default: bool) -> bool:
    value = _clean_value(raw)
    if not value:
        return default
    lowered = value.casefold()
    if lowered in {item.casefold() for item in _BOOL_TRUE}:
        return True
    if lowered in {item.casefold() for item in _BOOL_FALSE}:
        return False
    return default


def _looks_like_command(text: str) -> bool:
    lowered = _compact_whitespace(text).casefold()
    return any(lowered.startswith(prefix.casefold()) for prefix in _COMMAND_HEAD_PREFIXES)


def _compact_whitespace(text: str | None) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _clean_value(value: str | None) -> str | None:
    text = _compact_whitespace(value)
    if not text:
        return None
    return text.strip(" \t\r\n\"'“”‘’")