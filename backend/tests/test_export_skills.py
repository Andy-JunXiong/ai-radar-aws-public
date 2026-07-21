import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.prompts import export_skills  # noqa: E402


class ExportSkillsTests(unittest.TestCase):
    def test_discovery_returns_wave_one_skills(self):
        discovered = export_skills._discover_skills()
        names = sorted(meta.name for _, _, meta in discovered)
        self.assertEqual(len(names), 7)
        self.assertIn("radar-agent-repo-profile", names)
        self.assertIn("radar-friction-to-opportunity", names)

    def test_export_creates_wave_one_skill_files_and_references(self):
        with TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            for func_name, func, meta in export_skills._discover_skills():
                export_skills._export_skill(target, func_name=func_name, func=func, meta=meta)

            skill_dir = target / "radar-agent-repo-profile"
            self.assertTrue((skill_dir / "SKILL.md").exists())
            self.assertTrue((skill_dir / ".skill-hash").exists())
            self.assertTrue((skill_dir / "references").exists())
            self.assertTrue((skill_dir / "references" / "quality-notes.md").exists())
            self.assertTrue((skill_dir / "references" / "golden-examples" / "README.md").exists())

    def test_check_detects_skill_hash_drift(self):
        with TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            discovered = export_skills._discover_skills()
            for func_name, func, meta in discovered:
                export_skills._export_skill(target, func_name=func_name, func=func, meta=meta)

            func_name, func, meta = discovered[0]
            hash_path = target / meta.name / ".skill-hash"
            hash_path.write_text("out-of-sync\n", encoding="utf-8")

            message = export_skills._check_skill(target, func_name=func_name, func=func, meta=meta)
            self.assertIsNotNone(message)
            self.assertIn("drift", message)

    def test_re_export_preserves_manual_reference_files(self):
        with TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            func_name, func, meta = export_skills._discover_skills()[0]
            export_skills._export_skill(target, func_name=func_name, func=func, meta=meta)

            notes_path = target / meta.name / "references" / "quality-notes.md"
            notes_path.write_text("manual-content\n", encoding="utf-8")

            export_skills._export_skill(target, func_name=func_name, func=func, meta=meta)
            self.assertEqual(notes_path.read_text(encoding="utf-8"), "manual-content\n")


if __name__ == "__main__":
    unittest.main()
