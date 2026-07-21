import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.prompts.registry import workspace_reflection_polish_prompts  # noqa: E402


class ReflectionPolishPromptContractTests(unittest.TestCase):
    def _payload(self, text=None):
        return SimpleNamespace(
            signal_title="Agent infrastructure signal",
            signal_summary="A signal about production agent infrastructure.",
            why_it_matters="Agent infrastructure is becoming more operational.",
            relevance_to_projects="Relevant to AI Radar review loops.",
            relevance_to_career="Relevant to AI systems builder positioning.",
            synthesized_insight="Agent workflows need reviewable boundaries.",
            text=text or "This signal makes me more careful about agent workflow boundaries.",
        )

    def test_prompt_contract_is_copy_edit_only(self):
        system_prompt, user_prompt = workspace_reflection_polish_prompts(
            self._payload(),
            policy={"citation_required": True, "verification_required": True},
        )
        combined = f"{system_prompt}\n{user_prompt}"

        self.assertIn("copy-edit", combined)
        self.assertIn("keep the original meaning, judgment, stance, and uncertainty exactly intact", combined)
        self.assertIn("do not add new claims", combined)
        self.assertIn("do not add citations, evidence labels", combined)
        self.assertIn("do not add uncertainty labels or prefixes", combined)
        self.assertIn("never invent new [Evidence: ...] labels", combined)
        self.assertIn('do not add "Uncertain:" or similar qualifiers', combined)
        self.assertIn("not analysis, synthesis, verification, or strategic writing", combined)
        self.assertIn("without adding claims, evidence labels, or new strategic conclusions", combined)

    def test_prompt_contract_does_not_ask_for_stronger_strategic_rewrite(self):
        system_prompt, user_prompt = workspace_reflection_polish_prompts(self._payload())
        combined = f"{system_prompt}\n{user_prompt}".lower()

        self.assertNotIn("stronger version", combined)
        self.assertNotIn("more strategic", combined)
        self.assertNotIn("more persuasive", combined)

    def test_prompt_allows_preserving_existing_draft_evidence_labels_only(self):
        system_prompt, user_prompt = workspace_reflection_polish_prompts(
            self._payload("This matters to me because it affects review loops [Evidence: my note].")
        )
        combined = f"{system_prompt}\n{user_prompt}"

        self.assertIn("preserve only labels already present in the draft", combined)
        self.assertIn("never invent new [Evidence: ...] labels", combined)
        self.assertIn("[Evidence: my note]", combined)


if __name__ == "__main__":
    unittest.main()
