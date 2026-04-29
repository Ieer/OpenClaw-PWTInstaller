from __future__ import annotations

import unittest

from mission_control_api.app.voice_commands import parse_voice_command, summarize_voice_feedback


class VoiceCommandParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prefixes = ["指挥", "mission control", "control"]

    def test_create_task_command(self) -> None:
        result = parse_voice_command(
            "指挥 创建任务 给 metrics：统计过去 7 天各 Agent 活跃度；标签：reporting,panopticon",
            prefixes=self.prefixes,
            require_prefix=True,
        )
        self.assertEqual(result.outcome, "parsed")
        self.assertIsNotNone(result.command)
        self.assertEqual(result.command.kind, "create_task")
        self.assertEqual(result.command.assignee, "metrics")
        self.assertEqual(result.command.title, "统计过去 7 天各 Agent 活跃度")
        self.assertEqual(result.command.tags, ["reporting", "panopticon"])

    def test_create_task_colloquial_command(self) -> None:
        result = parse_voice_command(
            "指挥 帮我建个任务给 health：检查今晚备份状态",
            prefixes=self.prefixes,
            require_prefix=True,
        )
        self.assertEqual(result.outcome, "parsed")
        self.assertIsNotNone(result.command)
        self.assertEqual(result.command.kind, "create_task")
        self.assertEqual(result.command.assignee, "health")
        self.assertEqual(result.command.title, "检查今晚备份状态")

    def test_comment_command(self) -> None:
        result = parse_voice_command(
            "指挥 评论任务 3fa2c1d0：请先给结论，再给依据",
            prefixes=self.prefixes,
            require_prefix=True,
        )
        self.assertEqual(result.outcome, "parsed")
        self.assertEqual(result.command.kind, "add_comment")
        self.assertEqual(result.command.task_ref, "3fa2c1d0")

    def test_comment_colloquial_command(self) -> None:
        result = parse_voice_command(
            "指挥 给任务 3fa2c1d0 补一句 请记录日志路径",
            prefixes=self.prefixes,
            require_prefix=True,
        )
        self.assertEqual(result.outcome, "parsed")
        self.assertEqual(result.command.kind, "add_comment")
        self.assertEqual(result.command.task_ref, "3fa2c1d0")
        self.assertEqual(result.command.comment_body, "请记录日志路径")

    def test_status_command(self) -> None:
        result = parse_voice_command(
            "指挥 任务 3fa2c1d0 状态设为 REVIEW",
            prefixes=self.prefixes,
            require_prefix=True,
        )
        self.assertEqual(result.outcome, "parsed")
        self.assertEqual(result.command.kind, "set_status")
        self.assertEqual(result.command.status, "REVIEW")

    def test_status_colloquial_command(self) -> None:
        result = parse_voice_command(
            "指挥 把任务 3fa2c1d0 推进到审核了",
            prefixes=self.prefixes,
            require_prefix=True,
        )
        self.assertEqual(result.outcome, "parsed")
        self.assertEqual(result.command.kind, "set_status")
        self.assertEqual(result.command.status, "REVIEW")

    def test_done_colloquial_command(self) -> None:
        result = parse_voice_command(
            "指挥 任务 3fa2c1d0 搞定了",
            prefixes=self.prefixes,
            require_prefix=True,
        )
        self.assertEqual(result.outcome, "parsed")
        self.assertEqual(result.command.kind, "set_status")
        self.assertEqual(result.command.status, "DONE")

    def test_handoff_command(self) -> None:
        result = parse_voice_command(
            "指挥 转交任务 3fa2c1d0 给 writing；问题：整理成可发布周报；上下文：metrics 已完成基础数据；交付：一页摘要；附件：artifact://weekly-review",
            prefixes=self.prefixes,
            require_prefix=True,
        )
        self.assertEqual(result.outcome, "parsed")
        self.assertEqual(result.command.kind, "handoff_task")
        self.assertEqual(result.command.to_agent, "writing")
        self.assertEqual(result.command.artifact_refs, ["artifact://weekly-review"])
        self.assertTrue(result.command.review_gate)

    def test_agent_control_command(self) -> None:
        result = parse_voice_command(
            "指挥 重启 agent nox",
            prefixes=self.prefixes,
            require_prefix=True,
        )
        self.assertEqual(result.outcome, "parsed")
        self.assertEqual(result.command.kind, "control_agent")
        self.assertEqual(result.command.control_action, "restart")
        self.assertEqual(result.command.control_agent, "nox")

    def test_rejects_empty_prefixed_command(self) -> None:
        result = parse_voice_command(
            "指挥",
            prefixes=self.prefixes,
            require_prefix=True,
        )
        self.assertEqual(result.outcome, "rejected")

    def test_rejects_create_task_without_title_with_specific_reason(self) -> None:
        result = parse_voice_command(
            "指挥 帮我建个任务",
            prefixes=self.prefixes,
            require_prefix=True,
        )
        self.assertEqual(result.outcome, "rejected")
        self.assertEqual(result.reason, "create task command requires a title")

    def test_rejects_status_command_with_specific_reason(self) -> None:
        result = parse_voice_command(
            "指挥 把任务 3fa2c1d0 推进到未知阶段",
            prefixes=self.prefixes,
            require_prefix=True,
        )
        self.assertEqual(result.outcome, "rejected")
        self.assertEqual(result.reason, "status command requires task reference and target status")

    def test_voice_feedback_for_executed_create_task(self) -> None:
        result = parse_voice_command(
            "指挥 帮我建个任务给 health：检查今晚备份状态",
            prefixes=self.prefixes,
            require_prefix=True,
        )
        self.assertEqual(result.outcome, "parsed")
        self.assertEqual(
            summarize_voice_feedback(result.command, outcome="executed"),
            "已创建任务：检查今晚备份状态。",
        )

    def test_voice_feedback_for_rejected_task_reference(self) -> None:
        self.assertEqual(
            summarize_voice_feedback(None, outcome="rejected", reason="task reference is ambiguous: 3fa2c1d0"),
            "语音命令未执行：任务编号不唯一，请说更完整的任务编号。",
        )

    def test_ignores_non_prefixed_text_when_prefix_required(self) -> None:
        result = parse_voice_command(
            "今天天气怎么样",
            prefixes=self.prefixes,
            require_prefix=True,
        )
        self.assertEqual(result.outcome, "ignored")


if __name__ == "__main__":
    unittest.main()