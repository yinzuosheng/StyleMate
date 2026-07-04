from typing import Callable
from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call, before_model
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from utils.logger_handler import logger


@wrap_tool_call
def monitor_tool(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    logger.info(f"[tool monitor] {request.tool_call['name']}")
    logger.info(f"[tool monitor] args: {request.tool_call['args']}")

    try:
        result = handler(request)
        logger.info(f"[tool monitor] ok: {request.tool_call['name']}")

        return result
    except Exception as e:
        logger.error(f"[tool monitor] failed: {request.tool_call['name']} - {str(e)}")
        raise e


@before_model
def log_before_model(state: AgentState, runtime: Runtime):
    logger.info(f"[log_before_model] messages: {len(state['messages'])}")
    logger.debug(
        f"[log_before_model]{type(state['messages'][-1]).__name__} | {state['messages'][-1].content.strip()}"
    )
    return None


