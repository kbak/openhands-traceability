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
        setup = (
            files("versioned_traceability")
            .joinpath("skills/versioned-traceability/references/setup.md")
            .read_text(encoding="utf-8")
        )
        self.assertIn(setup, text)
        semantics = (
            files("versioned_traceability")
            .joinpath("skills/versioned-traceability/references/semantics.md")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(text.count(semantics), 1)
        self.assertEqual(len(original.skills), 1)
        self.assertEqual(len(with_traceability(context).skills), 2)

    def test_provisioned_context_omits_only_setup_across_initial_and_repair_sessions(self):
        original = AgentContext(skills=[Skill(name="task", content="Approved task and scope.")])
        complete = with_traceability(original)
        initial = with_traceability(original, provisioned=True)
        directory = files("versioned_traceability") / "skills/versioned-traceability"
        setup = (directory / "references/setup.md").read_text(encoding="utf-8")
        for context in (initial, with_traceability(initial, provisioned=True)):
            serialized = ACPAgent(
                acp_command=["codex-acp"], agent_context=context
            ).model_dump_json()
            prompt = ACPAgent.model_validate_json(serialized).agent_context.to_acp_prompt_context()
            self.assertIn("Approved task and scope.", prompt)
            self.assertEqual(len(context.skills), 2)
            self.assertNotIn(setup, prompt)
            for reference in ("requirements.md", "semantics.md"):
                content = (directory / "references" / reference).read_text(encoding="utf-8")
                self.assertEqual(prompt.count(content), 1)
            self.assertIn(Skill.load(directory / "SKILL.md").content, prompt)
            self.assertLess(len(prompt), len(complete.to_acp_prompt_context()) - len(setup))
        self.assertEqual(original.skills, [Skill(name="task", content="Approved task and scope.")])

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
            semantics = (
                files("versioned_traceability")
                .joinpath("skills/versioned-traceability/references/semantics.md")
                .read_text(encoding="utf-8")
            )
            self.assertEqual(prompt.count(semantics), 1)
        self.assertEqual(len(original.skills), 1)


if __name__ == "__main__":
    unittest.main()
