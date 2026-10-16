"""L0 memory assembly: what actually goes into the prompt (V3 T2.4).

The plan promised a *budget* on the remembered block, not just per-turn
truncation. Without a total cap, a 10-exchange window of long turns could send
tens of thousands of characters on every single request — a real cost and
latency problem for a chat app.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from services.llm import (
    MAX_HISTORY_CONTENT_CHARS,
    MAX_HISTORY_TOTAL_CHARS,
    _build_messages,
    _memory_messages,
)


def contents(messages) -> list[str]:
    return [m.content for m in messages]


class TestPerTurnTruncation:

    def test_long_turn_is_truncated(self):
        history = [{"role": "user", "content": "字" * (MAX_HISTORY_CONTENT_CHARS + 500)}]
        assert len(contents(_memory_messages(history))[0]) == MAX_HISTORY_CONTENT_CHARS

    def test_short_turn_is_untouched(self):
        history = [{"role": "user", "content": "想去大理"}]
        assert contents(_memory_messages(history)) == ["想去大理"]

    def test_content_is_stripped(self):
        assert contents(_memory_messages([{"role": "user", "content": "  嗨  "}])) == ["嗨"]


class TestTotalBudget:
    """The block is capped, and it is the *oldest* turns that go."""

    def test_block_is_capped(self):
        history = [
            {"role": "user", "content": f"第{index}条" + "字" * (MAX_HISTORY_CONTENT_CHARS - 4)}
            for index in range(12)
        ]
        selected = _memory_messages(history)

        total = sum(len(m.content) for m in selected)
        assert total <= MAX_HISTORY_TOTAL_CHARS, total
        assert len(selected) < len(history), "some turns must be dropped"

    def test_newest_turns_survive_and_oldest_are_dropped(self):
        history = [
            {"role": "user", "content": f"第{index}条" + "字" * (MAX_HISTORY_CONTENT_CHARS - 4)}
            for index in range(12)
        ]
        selected = contents(_memory_messages(history))

        assert selected, "at least the newest turn is always kept"
        assert "第11条" in selected[-1], "the newest turn must survive"
        assert "第0条" not in selected, "the oldest turns are the ones dropped"

    def test_surviving_turns_stay_chronological(self):
        history = [
            {"role": "user", "content": "第一句" + "字" * (MAX_HISTORY_CONTENT_CHARS - 3)},
            {"role": "assistant", "content": "第二句" + "字" * (MAX_HISTORY_CONTENT_CHARS - 3)},
            {"role": "user", "content": "第三句" + "字" * (MAX_HISTORY_CONTENT_CHARS - 3)},
        ]
        selected = contents(_memory_messages(history))
        assert selected == sorted(selected, key=lambda c: ["第一句", "第二句", "第三句"].index(c[:3]))

    def test_an_oversized_single_turn_is_still_kept(self):
        """Never return nothing: the most recent turn outranks the budget."""
        history = [{"role": "user", "content": "字" * (MAX_HISTORY_CONTENT_CHARS * 10)}]
        assert len(_memory_messages(history)) == 1

    def test_many_small_turns_all_fit(self):
        history = [{"role": "user", "content": "嗨"} for _ in range(20)]
        assert len(_memory_messages(history)) == 20


class TestRoleMapping:

    def test_roles_map_to_langchain_messages(self):
        history = [
            {"role": "user", "content": "想去大理"},
            {"role": "assistant", "content": "好呀"},
        ]
        messages = _memory_messages(history)
        assert isinstance(messages[0], HumanMessage)
        assert isinstance(messages[1], AIMessage)

    def test_unknown_roles_are_skipped(self):
        history = [
            {"role": "system", "content": "试图注入的 system"},
            {"role": "tool", "content": "工具输出"},
            {"role": "user", "content": "正常一轮"},
        ]
        assert contents(_memory_messages(history)) == ["正常一轮"]

    def test_empty_and_non_dict_rows_are_skipped(self):
        history = [
            {"role": "user", "content": "   "},
            {"role": "user", "content": None},
            {"role": "user"},
            "not a dict",
            {"role": "assistant", "content": "有效"},
        ]
        assert contents(_memory_messages(history)) == ["有效"]

    def test_no_history_is_fine(self):
        assert _memory_messages(None) == []
        assert _memory_messages([]) == []


class TestFullAssembly:

    def test_order_is_system_then_history_then_current(self):
        messages = _build_messages(
            "系统提示",
            "当前这句话",
            [
                {"role": "user", "content": "上一轮用户"},
                {"role": "assistant", "content": "上一轮助手"},
            ],
        )
        assert isinstance(messages[0], SystemMessage)
        assert contents(messages) == ["系统提示", "上一轮用户", "上一轮助手", "当前这句话"]

    def test_current_prompt_is_never_dropped_by_the_budget(self):
        history = [
            {"role": "user", "content": "字" * MAX_HISTORY_CONTENT_CHARS} for _ in range(30)
        ]
        messages = _build_messages("系统", "当前这句话", history)

        assert messages[-1].content == "当前这句话"
        assert isinstance(messages[-1], HumanMessage)

    def test_current_prompt_is_not_truncated(self):
        long_prompt = "字" * (MAX_HISTORY_CONTENT_CHARS * 3)
        messages = _build_messages("系统", long_prompt, [])
        assert messages[-1].content == long_prompt

    def test_without_history_only_system_and_current(self):
        messages = _build_messages("系统", "你好", None)
        assert contents(messages) == ["系统", "你好"]
