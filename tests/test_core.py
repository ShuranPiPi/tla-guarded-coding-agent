from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from agent.llm import LLMUnavailableError, fallback_provider, select_provider
from agent.nodes import route_after_code_test, route_after_spec_check
from agent.specs import SpecBundleError, parse_spec_bundle
from agent.tlc import run_tlc


GOOD_BUNDLE = """```tla
---- MODULE Tiny ----
EXTENDS Naturals
VARIABLE x
Init == x = 0
Next == x' = 1
Spec == Init /\\ [][Next]_x
TypeOK == x \\in 0..1
====
```
```cfg
SPECIFICATION Spec
INVARIANTS TypeOK
CHECK_DEADLOCK FALSE
```
```json
{"spec_tests": ["assert add(1, 2) == 3"]}
```"""


class ProviderSelectionTests(unittest.TestCase):
    def test_auto_without_keys_fails_clearly(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(LLMUnavailableError, "No LLM provider"):
                select_provider("auto")

    def test_auto_prefers_openai_and_fallback_is_gemini(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "x", "GEMINI_API_KEY": "y"}, clear=True):
            self.assertEqual(select_provider("auto"), "openai")
            self.assertEqual(fallback_provider("openai"), "gemini")

    def test_gemini_only(self) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "y"}, clear=True):
            self.assertEqual(select_provider("auto"), "gemini")


class SpecParserTests(unittest.TestCase):
    def test_parse_good_bundle(self) -> None:
        bundle = parse_spec_bundle(GOOD_BUNDLE)
        self.assertEqual(bundle.module, "Tiny")
        self.assertEqual(bundle.spec_tests, ["assert add(1, 2) == 3"])

    def test_missing_blocks_fail(self) -> None:
        with self.assertRaises(SpecBundleError):
            parse_spec_bundle("```tla\n---- MODULE Missing ----\n====\n```")


class TLCRunnerTests(unittest.TestCase):
    def test_tlc_success(self) -> None:
        bundle = parse_spec_bundle(GOOD_BUNDLE)
        result = run_tlc(bundle.module, bundle.tla, bundle.cfg)
        self.assertTrue(result.passed, result.error)
        self.assertEqual(result.returncode, 0)

    def test_tlc_failure(self) -> None:
        result = run_tlc(
            "Broken",
            "---- MODULE Broken ----\nVARIABLE x\nInit == x = 0\nNext == x' = y\nSpec == Init /\\ [][Next]_x\n====",
            "SPECIFICATION Spec\nCHECK_DEADLOCK FALSE\n",
        )
        self.assertFalse(result.passed)
        self.assertTrue(result.error)


class WorkflowRoutingTests(unittest.TestCase):
    def test_spec_success_routes_to_tests(self) -> None:
        self.assertEqual(route_after_spec_check({"spec_result": {"passed": True}}), "derive_tests")

    def test_spec_failure_routes_to_repair_until_budget(self) -> None:
        state = {"spec_result": {"passed": False}, "spec_retries": 1, "max_spec_retries": 2}
        self.assertEqual(route_after_spec_check(state), "repair_spec")
        state["spec_retries"] = 2
        self.assertEqual(route_after_spec_check(state), "spec_fail")

    def test_code_failure_routes_to_codefail_after_budget(self) -> None:
        state = {"last_result": {"passed": False}, "code_retries": 3, "max_code_retries": 3}
        self.assertEqual(route_after_code_test(state), "code_fail")

    def test_code_success_routes_done(self) -> None:
        self.assertEqual(route_after_code_test({"last_result": {"passed": True}}), "done")


if __name__ == "__main__":
    unittest.main()
