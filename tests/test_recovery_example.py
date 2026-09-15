"""Exercise example storage with real local commands and no model invocation."""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from versioned_traceability.common import read_json
from versioned_traceability.recovery import active_recovery, initialize, recovery_storage

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/recover_local.py"


class RecoveryExampleTests(unittest.TestCase):
    def test_original_snapshot_and_failed_check_use_durable_or_explicit_storage(self):
        spec = importlib.util.spec_from_file_location("recovery_example", EXAMPLE)
        example = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(example)
        for explicit in (False, True):
            with self.subTest(explicit=explicit), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                repo = root / "project"
                repo.mkdir()
                (repo / "README.md").write_text("Existing project documentation.\n")
                initialize(repo, "Original project")
                argv = [str(EXAMPLE), "--repo", str(repo), "--focus", "Documented behavior"]
                out = root / "experiment"
                if explicit:
                    argv += ["--out", str(out)]
                conversation = Mock()
                conversation.state.execution_status.value = "finished"
                with (
                    patch("sys.argv", argv),
                    patch.object(example, "ACPAgent"),
                    patch.object(example, "Conversation", return_value=conversation),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    # The stub authors nothing. A real failed check must still
                    # retain its result and original source in the right place.
                    self.assertEqual(example.main(), 2)
                bundle = active_recovery(repo)
                if explicit:
                    self.assertEqual(bundle, out / "recovery")
                    result = out / "result/recovery-result.json"
                else:
                    self.assertTrue(bundle.is_relative_to(recovery_storage(repo) / "runs"))
                    results = list(
                        (recovery_storage(repo) / "checks").glob("*/recovery-result.json")
                    )
                    self.assertEqual(len(results), 1)
                    result = results[0]
                self.assertEqual(
                    (bundle / "source/README.md").read_text(), "Existing project documentation.\n"
                )
                self.assertEqual(read_json(result)["status"], "error")
                self.assertEqual(read_json(result)["workspace"], str(repo))
                conversation.close.assert_called_once()
