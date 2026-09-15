import unittest
from importlib.resources import files

from openhands.sdk import AgentContext
from openhands.sdk.agent import ACPAgent
from openhands.sdk.context import Skill

from openhands_traceability import with_recovery, with_traceability


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
        reference = (
            files("versioned_traceability")
            .joinpath("skills/versioned-traceability/references/requirements.md")
            .read_text(encoding="utf-8")
        )
        self.assertIn(reference, text)
        self.assertEqual(len(original.skills), 1)
        self.assertEqual(len(with_traceability(context).skills), 2)

    def test_recovery_guidance_survives_acp_serialization_and_fresh_repair(self):
        original = AgentContext(
            skills=[Skill(name="task", content="Recover the session capability.")]
        )
        initial = with_recovery(original)
        for context in (initial, with_recovery(initial)):
            agent = ACPAgent(acp_command=["codex-acp"], agent_context=context)
            restored = ACPAgent.model_validate_json(agent.model_dump_json())
            prompt = restored.agent_context.to_acp_prompt_context()
            self.assertIn("Recover the session capability.", prompt)
            self.assertEqual(len(context.skills), 2)
            procedure = next(s.content for s in context.skills if s.name == "recover-baseline")
            self.assertIn(procedure, prompt)
            reference = (
                files("versioned_traceability") / "skills/recover-baseline/references/recovery.md"
            ).read_text(encoding="utf-8")
            self.assertIn(reference, prompt)
        self.assertEqual(len(original.skills), 1)


if __name__ == "__main__":
    unittest.main()
