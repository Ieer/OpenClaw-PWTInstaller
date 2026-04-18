#!/usr/bin/env python3
"""Shared chart capability matrix for planning and PPTX export stages."""

from __future__ import annotations

from dataclasses import dataclass


PLANNING_DEFAULT = "default"
EXPORT_NATIVE_CHART = "native_chart"
EXPORT_NATIVE_GROUP = "native_group"


@dataclass(frozen=True)
class ChartCapability:
    chart_type: str
    planning_status: str
    export_mode: str
    summary: str


CHART_CAPABILITIES: dict[str, ChartCapability] = {
    "comparison_bar": ChartCapability(
        chart_type="comparison_bar",
        planning_status=PLANNING_DEFAULT,
        export_mode=EXPORT_NATIVE_CHART,
        summary="两项差异，导出为真实 PPT 柱状图。",
    ),
    "progress_bar": ChartCapability(
        chart_type="progress_bar",
        planning_status=PLANNING_DEFAULT,
        export_mode=EXPORT_NATIVE_CHART,
        summary="完成度，导出为真实 PPT 条形图。",
    ),
    "stacked_bar": ChartCapability(
        chart_type="stacked_bar",
        planning_status=PLANNING_DEFAULT,
        export_mode=EXPORT_NATIVE_CHART,
        summary="构成占比，导出为真实 PPT 堆叠图。",
    ),
    "sparkline": ChartCapability(
        chart_type="sparkline",
        planning_status=PLANNING_DEFAULT,
        export_mode=EXPORT_NATIVE_GROUP,
        summary="小趋势，导出为命名原生 group。",
    ),
    "rating": ChartCapability(
        chart_type="rating",
        planning_status=PLANNING_DEFAULT,
        export_mode=EXPORT_NATIVE_GROUP,
        summary="评分/等级，导出为命名原生 group。",
    ),
    "kpi": ChartCapability(
        chart_type="kpi",
        planning_status=PLANNING_DEFAULT,
        export_mode=EXPORT_NATIVE_GROUP,
        summary="单核心指标，导出为命名原生 group。",
    ),
    "ring": ChartCapability(
        chart_type="ring",
        planning_status=PLANNING_DEFAULT,
        export_mode=EXPORT_NATIVE_GROUP,
        summary="占比圆环，导出为命名原生 group。",
    ),
    "metric_row": ChartCapability(
        chart_type="metric_row",
        planning_status=PLANNING_DEFAULT,
        export_mode=EXPORT_NATIVE_GROUP,
        summary="多指标横向扫读，导出为命名原生 group。",
    ),
    "timeline": ChartCapability(
        chart_type="timeline",
        planning_status=PLANNING_DEFAULT,
        export_mode=EXPORT_NATIVE_GROUP,
        summary="里程碑/阶段变化，导出为命名原生 group。",
    ),
    "funnel": ChartCapability(
        chart_type="funnel",
        planning_status=PLANNING_DEFAULT,
        export_mode=EXPORT_NATIVE_GROUP,
        summary="转化漏斗，导出为命名原生 group。",
    ),
    "radar": ChartCapability(
        chart_type="radar",
        planning_status=PLANNING_DEFAULT,
        export_mode=EXPORT_NATIVE_GROUP,
        summary="多维度对照，导出为命名原生 group。",
    ),
    "treemap": ChartCapability(
        chart_type="treemap",
        planning_status=PLANNING_DEFAULT,
        export_mode=EXPORT_NATIVE_GROUP,
        summary="层级占比，导出为命名原生 group。",
    ),
    "waffle": ChartCapability(
        chart_type="waffle",
        planning_status=PLANNING_DEFAULT,
        export_mode=EXPORT_NATIVE_GROUP,
        summary="占比格块，导出为命名原生 group。",
    ),
}

VALID_CHART_TYPES = frozenset(CHART_CAPABILITIES)
DEFAULT_PLANNABLE_CHART_TYPES = frozenset(
    chart_type
    for chart_type, capability in CHART_CAPABILITIES.items()
    if capability.planning_status == PLANNING_DEFAULT
)
NATIVE_CHART_EXPORT_TYPES = frozenset(
    chart_type
    for chart_type, capability in CHART_CAPABILITIES.items()
    if capability.export_mode == EXPORT_NATIVE_CHART
)
NATIVE_GROUP_EXPORT_TYPES = frozenset(
    chart_type
    for chart_type, capability in CHART_CAPABILITIES.items()
    if capability.export_mode == EXPORT_NATIVE_GROUP
)
EXPORT_MODE_LABELS = {
    EXPORT_NATIVE_CHART: "真实 PPT chart",
    EXPORT_NATIVE_GROUP: "命名原生 / 原生化 group",
}


def get_chart_capability(chart_type: str | None) -> ChartCapability | None:
    if not chart_type:
        return None
    return CHART_CAPABILITIES.get(str(chart_type).strip())


def export_mode_label(chart_type: str | None) -> str | None:
    capability = get_chart_capability(chart_type)
    if capability is None:
        return None
    return EXPORT_MODE_LABELS[capability.export_mode]
