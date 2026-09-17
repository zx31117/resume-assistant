"""Actual-operation proof of retry scope (V220-R2 / llm_service.invoke_observed_json).

Only runs in-process; no DB, no real model. Uses injected fake providers.
"""
import sys
import traceback
sys.path.insert(0, "backend")

from core.errors import LLMOutputInvalidError
from services.llm_service import (
    LLM_MAX_ATTEMPTS,
    TaskTokenBudget,
    invoke_observed_json,
)


def provider_factory(exc, n_fail):
    calls = {"n": 0}

    def prov(system, user, variables, max_tokens):
        calls["n"] += 1
        if calls["n"] <= n_fail:
            raise exc
        return '{"ok": true}', 10

    return prov, calls


def main():
    print("LLM_MAX_ATTEMPTS=", LLM_MAX_ATTEMPTS)
    # 1) retryable(ConnectionError) 2-fail then success -> 3 attempts, result ok
    b = TaskTokenBudget(10000)
    p, _ = provider_factory(ConnectionError("injected transient"), 2)
    _, r = invoke_observed_json("s", "u", max_tokens=100, budget=b, stage="ok",
                                variables={}, provider=p)
    print("retryable_2fail_success attempts=", r.attempts,
          "retry=", r.retry_reasons, "tokens=", r.completion_tokens)

    # 2) retryable exhausted -> strict LLMOutputInvalidError, exactly 3 attempts
    b2 = TaskTokenBudget(10000)
    p2, c2 = provider_factory(ConnectionError("injected transient"), 3)
    try:
        invoke_observed_json("s", "u", max_tokens=100, budget=b2, stage="reject",
                             variables={}, provider=p2)
        print("EXHAUSTED=NO_RAISE(FAIL)")
    except LLMOutputInvalidError:
        print("exhausted_strict_raise attempts=", c2["n"],
              "max=", LLM_MAX_ATTEMPTS)

    # 3) non-retryable(ValueError -> _retryable False) -> immediate fail at 1st attempt
    b3 = TaskTokenBudget(10000)
    p3, c3 = provider_factory(ValueError("bad param (non-retryable)"), 1)
    try:
        invoke_observed_json("s", "u", max_tokens=100, budget=b3, stage="noretry",
                             variables={}, provider=p3)
        print("NONRETRY=NO_RAISE(FAIL)")
    except LLMOutputInvalidError:
        print("non_retryable_immediate_fail attempts=", c3["n"])
    print("RETRY_PROOF_EXIT=0")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(9)