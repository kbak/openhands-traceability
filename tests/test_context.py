import unittest

from openhands.sdk import AgentContext
from openhands.sdk.agent import ACPAgent
from openhands.sdk.context import Skill

from openhands_traceability import with_traceability


class ContextTests(unittest.TestCase):
    def test_native_serialization_preserves_existing_and_traceability_instructions(self):
        original = AgentContext(skills=[Skill(name="task", content="Implement the selected task.")])
        context = with_traceability(original)
        agent = ACPAgent(acp_command=["codex-acp"], agent_context=context)
        restored = ACPAgent.model_validate_json(agent.model_dump_json())
        text = restored.agent_context.to_acp_prompt_context()
        self.assertIn("Implement the selected task.", text)
        procedure = next(s.content for s in context.skills if s.name == "versioned-traceability")
        self.assertTrue(procedure.strip())
        self.assertIn(procedure, text)
        self.assertEqual(len(original.skills), 1)
        self.assertEqual(len(with_traceability(context).skills), 2)


if __name__ == "__main__":
    unittest.main()
