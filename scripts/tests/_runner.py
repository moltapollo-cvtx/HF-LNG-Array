"""Tiny test runner — no pytest dependency."""
from __future__ import annotations
import traceback
from typing import Callable


def run_tests(tests: dict[str, Callable[[], None]]) -> int:
    passed = 0
    failed: list[tuple[str, str]] = []
    for name, fn in tests.items():
        try:
            fn()
        except Exception:
            failed.append((name, traceback.format_exc()))
        else:
            passed += 1
    print(f"\n{'='*60}")
    print(f"  PASS: {passed}/{len(tests)}")
    for name, tb in failed:
        print(f"  FAIL: {name}")
        print(tb)
    print('='*60)
    return 0 if not failed else 1
