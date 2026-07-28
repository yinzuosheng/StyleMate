from langgraph.prebuilt import create_react_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from utils.logger_handler import logger
from agent.tools.agent_tools import (
    rag_summarize,
    get_weather,
    get_user_location,
    recommend_size,
    recommend_outfit,
    care_guide,
    wardrobe_gap_check,
    item_style_analysis,
)


class ReactAgent:
    def __init__(self):
        self.agent = create_react_agent(
            model=chat_model,
            tools=[
                rag_summarize,
                get_weather,
                get_user_location,
                recommend_size,
                recommend_outfit,
                care_guide,
                wardrobe_gap_check,
                item_style_analysis,
            ],
            state_modifier=load_system_prompts(),
        )

    def _call_model(self, prompt: str) -> str:
        try:
            result = chat_model.invoke(prompt)
        except Exception as exc:
            logger.error(f"[plan/self-check] model invoke failed: {str(exc)}")
            return ""

        if hasattr(result, "content"):
            return str(result.content or "").strip()
        return str(result).strip()

    def _messages_brief(self, messages: list[dict], max_items: int = 6, max_len: int = 240) -> str:
        brief = []
        for msg in messages[-max_items:]:
            role = msg.get("role", "user")
            content = str(msg.get("content", "")).strip().replace("\n", " ")
            if len(content) > max_len:
                content = content[:max_len] + "..."
            brief.append(f"{role}: {content}")
        return "\n".join(brief)

    def _build_plan(self, messages: list[dict]) -> str:
        summary = self._messages_brief(messages)
        if not summary:
            return ""

        prompt = (
            "你是衣橱助理的执行规划器。请基于对话内容给出3-5步的执行计划，"
            "每步保持简短、可执行，不要输出答案与解释。\n"
            "对话摘要：\n"
            f"{summary}\n"
            "输出格式示例：\n"
            "1. ...\n2. ...\n3. ..."
        )
        return self._call_model(prompt)

    def _self_reflect(self, messages: list[dict], answer: str) -> str:
        if not answer:
            return ""

        summary = self._messages_brief(messages)
        prompt = (
            "你是衣橱助理的回答自检器。检查回答是否遗漏用户诉求、是否与画像/场景冲突、"
            "是否需要补充更具体的建议。若无需修改，输出 PASS。"
            "若需要补充，请只输出需要追加的内容，不要解释原因，不要重复原回答。\n"
            "对话摘要：\n"
            f"{summary}\n"
            "回答：\n"
            f"{answer}\n"
            "输出："
        )
        return self._call_model(prompt)

    def execute_stream(self, query_or_messages):
        if isinstance(query_or_messages, list):
            input_dict = {"messages": query_or_messages}
        else:
            input_dict = {"messages": [{"role": "user", "content": query_or_messages}]}

        messages = input_dict["messages"]
        original_messages = list(messages)
        plan_text = self._build_plan(original_messages)
        if plan_text:
            logger.info("[plan] generated execution plan")
            plan_message = {
                "role": "system",
                "content": (
                    "执行计划（内部使用，请勿在回答中展示）：\n"
                    f"{plan_text}\n"
                    "请严格按照计划调用工具并组织回复。"
                ),
            }
            insert_at = 0
            for msg in messages:
                if msg.get("role") == "system":
                    insert_at += 1
                else:
                    break
            messages = messages[:insert_at] + [plan_message] + messages[insert_at:]

        input_dict = {"messages": messages}

        collected = []
        for chunk in self.agent.stream(input_dict, stream_mode="values"):
            latest_message = chunk["messages"][-1]
            for tool_call in getattr(latest_message, "tool_calls", []):
                logger.info(f"[tool monitor] {tool_call.get('name', 'unknown')}")
            if getattr(latest_message, "type", "") == "tool":
                logger.info(f"[tool monitor] ok: {getattr(latest_message, 'name', 'unknown')}")
            elif getattr(latest_message, "content", None):
                logger.info("[model] response received")
            if latest_message.content:
                content = latest_message.content.strip() + "\n"
                collected.append(content)
                yield content

        answer_text = "".join(collected).strip()
        reflection = self._self_reflect(original_messages, answer_text)
        if reflection and reflection.strip().upper() != "PASS":
            logger.info("[self-check] appended reflection")
            yield "\n补充：" + reflection.strip() + "\n"


if __name__ == "__main__":
    agent = ReactAgent()
    for chunk in agent.execute_stream("给我一份本月衣橱报告"):
        print(chunk, end="", flush=True)
