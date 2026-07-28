"""Compatibility coverage for the pinned LangChain/LangGraph stack."""

import unittest
from importlib.util import find_spec
from importlib import reload
from unittest.mock import patch

from langchain_core.messages import AIMessage


class ReactAgentCompatibilityTest(unittest.TestCase):
    def test_obsolete_middleware_module_is_not_importable(self):
        """Prevent the incompatible middleware implementation from returning."""
        self.assertIsNone(find_spec("agent.tools.middleware"))

    def test_imports_and_constructs_without_model_invocation(self):
        """Catch regressions that reintroduce APIs unavailable in pinned versions."""
        from agent.react_agent import ReactAgent

        agent = ReactAgent()

        self.assertIsNotNone(agent.agent)

    def test_tool_module_defers_rag_store_initialization_until_tool_use(self):
        """Catch import-time creation of the RAG store during agent construction."""
        import agent.tools.agent_tools as agent_tools

        with patch("rag.rag_service.VectorStoreService") as vector_store:
            reload(agent_tools)

        vector_store.assert_not_called()

    def test_execute_stream_uses_pinned_graph_stream_signature(self):
        """Catch unsupported stream keyword arguments on the pinned LangGraph graph."""
        from agent.react_agent import ReactAgent

        class PinnedGraph:
            def stream(self, input_dict, stream_mode):
                self.input_dict = input_dict
                self.stream_mode = stream_mode
                yield {"messages": [AIMessage(content="compatible response")]}

        agent = ReactAgent()
        agent.agent = PinnedGraph()
        with patch.object(agent, "_build_plan", return_value=""), patch.object(
            agent, "_self_reflect", return_value=""
        ):
            output = list(agent.execute_stream("hello"))

        self.assertEqual(output, ["compatible response\n"])
