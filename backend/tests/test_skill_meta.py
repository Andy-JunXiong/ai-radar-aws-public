import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.prompts.registry import agent_repo_profile_prompts  # noqa: E402
from app.prompts.skill_meta import SkillMeta, skill_prompt  # noqa: E402


class SkillMetaTests(unittest.TestCase):
    def test_decorated_function_executes_normally(self):
        system_prompt, user_prompt = agent_repo_profile_prompts(
            repo_candidate_payload={"title": "Demo Repo"}
        )

        self.assertIn("AI Radar repo intelligence analyst", system_prompt)
        self.assertIn('"title": "Demo Repo"', user_prompt)

    def test_decorated_function_exposes_skill_meta(self):
        meta = getattr(agent_repo_profile_prompts, "_skill_meta", None)
        self.assertIsInstance(meta, SkillMeta)
        self.assertEqual(meta.name, "radar-agent-repo-profile")
        self.assertEqual(meta.version, "v2")

    def test_missing_required_fields_raise_type_error(self):
        def sample_prompt():
            return "ok"

        decorated = skill_prompt(name="missing-fields")
        with self.assertRaises(TypeError):
            decorated(sample_prompt)


if __name__ == "__main__":
    unittest.main()
