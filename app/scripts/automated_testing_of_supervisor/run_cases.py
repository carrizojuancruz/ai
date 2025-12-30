"""Run supervisor SSE test cases and export question/answer JSON.

Defaults:
- Input cases file: `cases.json` next to this script
- Output file: `results.json` next to this script

Usage (server running):
    poetry run python -m app.scripts.automated_testing_of_supervisor.run_cases
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import requests

from app.utils.welcome import call_llm

DEFAULT_BASE_URL: str = "http://localhost:8000"
DEFAULT_TIMEOUT_SECONDS: float = 300.0
DEFAULT_SSE_CONNECT_DELAY_SECONDS: float = 0.15
DEFAULT_CASES_FILENAME: str = "cases.json"
DEFAULT_RESULTS_FILENAME: str = "results.json"
MESSAGE_COMPLETED_EVENT: str = "message.completed"
RESPONSE_PATH_EVENT: str = "response.path"
RESPONSE_PATH_SOURCE_KEY: str = "source"
RESPONSE_PATH_TYPE_KEY: str = "type"
PARALLELISM_CONFIG_KEY: str = "SUPERVISOR_TEST_PARALLELISM"
DEFAULT_PARALLELISM: int = 1
DEFAULT_JUDGE_PASS_SCORE: int = 70
DEFAULT_SHOW_PROGRESS: bool = True
STATUS_PENDING: str = "pending"
STATUS_COMPLETED: str = "completed"
STATUS_ERROR: str = "error"
STATUS_JUDGED: str = "judged"
STATUS_JUDGE_SKIPPED: str = "judge_skipped"
STATUS_CONFIRM_REQUESTED: str = "confirm_requested"
ROUTE_WEALTH: str = "wealth_agent"
ROUTE_GOAL: str = "goal_agent"
ROUTE_FINANCE: str = "finance_agent"
ROUTE_FINANCE_CAPTURE: str = "finance_capture_agent"

TRANSFER_TOOL_TO_ROUTE: dict[str, str] = {
    "transfer_to_wealth_agent": ROUTE_WEALTH,
    "transfer_to_goal_agent": ROUTE_GOAL,
    "transfer_to_finance_agent": ROUTE_FINANCE,
    "transfer_to_finance_capture_agent": ROUTE_FINANCE_CAPTURE,
}


@dataclass(frozen=True)
class CaseInput:
    id: str
    question: str
    voice: bool
    expected: dict[str, Any] | None
    expected_route: str | None
    expected_path: dict[str, str] | None


@dataclass(frozen=True)
class CaseOutput:
    id: str
    question: str
    answer: str
    thread_id: str
    expected: dict[str, Any] | None
    expected_route: str | None
    expected_path: dict[str, str] | None
    routing: dict[str, Any]
    confirm: dict[str, Any] | None


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Input JSON must be an object")
    return data


def _try_load_existing_results(path: Path) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, list):
        return None
    return [r for r in raw if isinstance(r, dict)]


def _parse_cases(raw: Any) -> list[CaseInput]:
    if not isinstance(raw, list):
        raise ValueError("'cases' must be an array")

    cases: list[CaseInput] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"cases[{idx}] must be an object")
        case_id = item.get("id")
        question = item.get("question")
        voice = item.get("voice", False)
        expected = item.get("expected")
        expected_output = item.get("expected_output")
        expected_route = item.get("expected_route")
        expected_path = item.get("expected_path")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"cases[{idx}].id must be a non-empty string")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"cases[{idx}].question must be a non-empty string")
        if not isinstance(voice, bool):
            raise ValueError(f"cases[{idx}].voice must be a boolean")
        if expected_route is not None:
            if not isinstance(expected_route, str) or not expected_route.strip():
                raise ValueError(f"cases[{idx}].expected_route must be a non-empty string when provided")
            expected_route = expected_route.strip()
        if expected_path is not None:
            if not isinstance(expected_path, dict):
                raise ValueError(f"cases[{idx}].expected_path must be an object when provided")
            raw_source = expected_path.get(RESPONSE_PATH_SOURCE_KEY)
            raw_type = expected_path.get(RESPONSE_PATH_TYPE_KEY)
            if not isinstance(raw_source, str) or not raw_source.strip():
                raise ValueError(f"cases[{idx}].expected_path.source must be a non-empty string when provided")
            if not isinstance(raw_type, str) or not raw_type.strip():
                raise ValueError(f"cases[{idx}].expected_path.type must be a non-empty string when provided")
            expected_path = {RESPONSE_PATH_SOURCE_KEY: raw_source.strip(), RESPONSE_PATH_TYPE_KEY: raw_type.strip()}
        if expected is None and isinstance(expected_output, str) and expected_output.strip():
            expected = {"notes": expected_output.strip()}
        if expected is not None and not isinstance(expected, dict):
            raise ValueError(f"cases[{idx}].expected must be an object when provided")
        cases.append(
            CaseInput(
                id=case_id.strip(),
                question=question.strip(),
                voice=voice,
                expected=expected,
                expected_route=expected_route,
                expected_path=expected_path,
            )
        )
    return cases


def _build_headers(token: Optional[str]) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _parse_parallelism(payload: dict[str, Any]) -> int:
    raw = payload.get(PARALLELISM_CONFIG_KEY)
    if raw is None:
        env_raw = os.environ.get(PARALLELISM_CONFIG_KEY)
        raw = env_raw
    if raw is None:
        return DEFAULT_PARALLELISM
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{PARALLELISM_CONFIG_KEY} must be an integer >= 1") from exc
    if value < 1:
        raise ValueError(f"{PARALLELISM_CONFIG_KEY} must be an integer >= 1")
    return value


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def _print_progress(line: str, *, show: bool) -> None:
    if not show:
        return
    print(line, flush=True)


def _count_statuses(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in results:
        status = r.get("status")
        key = status if isinstance(status, str) and status.strip() else "missing"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _summarize_mismatches(results: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    route_mismatches: list[str] = []
    path_mismatches: list[str] = []
    for r in results:
        cid = r.get("id")
        case_id = cid if isinstance(cid, str) else ""
        expected_route = r.get("expected_route")
        expected_path = r.get("expected_path")
        routing = r.get("routing") if isinstance(r.get("routing"), dict) else {}
        observed_final = routing.get("final") if isinstance(routing, dict) else None
        observed_path = routing.get("response_path") if isinstance(routing, dict) else None

        if (
            isinstance(expected_route, str)
            and expected_route.strip()
            and observed_final != expected_route
        ):
            route_mismatches.append(case_id)
        if (
            isinstance(expected_path, dict)
            and expected_path
            and observed_path != expected_path
        ):
            path_mismatches.append(case_id)

    return route_mismatches, path_mismatches


def _summarize_failures(results: list[dict[str, Any]]) -> list[tuple[str, int | None, str | None]]:
    failures: list[tuple[str, int | None, str | None]] = []
    for r in results:
        cid = r.get("id")
        case_id = cid if isinstance(cid, str) else ""
        judge = r.get("judge")
        if not isinstance(judge, dict):
            continue
        passed = judge.get("pass")
        if passed is not False:
            continue
        score = judge.get("score")
        score_int: int | None
        try:
            score_int = int(score) if score is not None else None
        except (TypeError, ValueError):
            score_int = None
        reasons = judge.get("reasons")
        first_reason: str | None = None
        if isinstance(reasons, list) and reasons and isinstance(reasons[0], str):
            first_reason = reasons[0]
        failures.append((case_id, score_int, first_reason))
    return failures


def _select_case_ids_from_only_arg(raw: str, all_case_ids: list[str]) -> set[str]:
    value = raw.strip()
    if not value:
        raise ValueError("--only must not be empty")

    # Regex form: /.../ or re:...
    if (len(value) >= 2 and value.startswith("/") and value.endswith("/")) or value.startswith("re:"):
        pattern = value[3:] if value.startswith("re:") else value[1:-1]
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid regex for --only: {exc}") from exc
        return {cid for cid in all_case_ids if compiled.search(cid)}

    # ID list form: id1,id2,id3
    if "," in value:
        items = [x.strip() for x in value.split(",") if x.strip()]
        if not items:
            raise ValueError("--only must contain at least one id")
        return set(items)

    # Single id
    return {value}


def _select_failed_case_ids(existing_results: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for r in existing_results:
        cid = r.get("id")
        if not isinstance(cid, str) or not cid.strip():
            continue
        status = r.get("status")
        if status == STATUS_ERROR:
            ids.add(cid.strip())
            continue
        judge = r.get("judge")
        if not isinstance(judge, dict):
            continue
        score = judge.get("score")
        try:
            score_int = int(score) if score is not None else None
        except (TypeError, ValueError):
            score_int = None
        if score_int == 0:
            ids.add(cid.strip())
    return ids


def _extract_first_json_object(text: str) -> dict[str, Any] | None:
    if not isinstance(text, str) or not text.strip():
        return None
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _build_judge_prompt(
    *,
    case_id: str,
    question: str,
    answer: str,
    expected: dict[str, Any],
    expected_route: str | None,
) -> tuple[str, str]:
    """Build a domain-aware judge prompt.

    Key policy:
    - Routing is evaluated deterministically elsewhere (never by the LLM judge).
    - For finance/goal (user-stateful) domains, do NOT penalize precise numbers or claims that depend on user data.
      Judge primarily on relevance (did it answer the question) and obvious product capability hallucinations.
    - For wealth (system/product) domain, be strict about product truth (e.g., NO AUTOMATION).
    """
    system = (
        "You are a strict evaluator for an AI assistant response.\n"
        "You must output ONLY valid JSON (no markdown, no extra text).\n"
        "Return fields:\n"
        '- "id": string\n'
        '- "score": integer 0-100\n'
        f'- "pass": boolean (true if score >= {DEFAULT_JUDGE_PASS_SCORE})\n'
        '- "reasons": array of short strings\n'
        "- Be consistent and conservative. If unsure, score lower.\n"
    )

    notes = expected.get("notes") if isinstance(expected, dict) else None

    route = expected_route or "unknown"
    if route in (ROUTE_FINANCE, ROUTE_GOAL):
        judging_mode = "user_stateful"
        rubric = {
            "relevance": "Does the answer address the user's question directly (even if it includes numbers)?",
            "clarity": "Clear, concise, and appropriately structured for the question.",
            "product_truth": (
                "Penalize ONLY clear hallucinations about product/system capabilities (e.g., claiming Vera supports "
                "fully automated transfers when it does not). Do NOT try to fact-check user data."
            ),
            "no_fact_checking_rule": (
                "IMPORTANT: This question depends on user data (accounts/transactions/goals). You cannot verify facts. "
                "Do NOT penalize precise amounts/metrics just because they are precise."
            ),
        }
        scoring_100 = "Directly answers the question with clear reasoning; no product capability hallucinations."
        scoring_threshold = "Mostly answers the question; minor clarity issues; no product capability hallucinations."
        scoring_0 = (
            "Does not answer the question at all, or contains major product/system capability hallucinations "
            "(e.g., claims of automation that are disallowed)."
        )
    elif route == ROUTE_WEALTH:
        judging_mode = "product_strict"
        rubric = {
            "alignment": "Does the answer satisfy the intent described by expected_notes?",
            "product_truth": (
                "Be strict: penalize invented app capabilities or UI navigation that is not supported. "
                "In particular, Vera does NOT support fully automated recurring/scheduled transfers; reminders are not automation."
            ),
            "clarity": "Step-by-step when asked 'how do I', and clear yes/no when asked about capabilities.",
            "safety": "Avoid overclaiming. Prefer honest limitations and correct disclaimers.",
        }
        scoring_100 = "Meets expected_notes with high clarity and no product capability hallucinations."
        scoring_threshold = "Mostly correct and helpful; minor issues but acceptable."
        scoring_0 = "Incorrect, misleading, or hallucinates product/app capabilities."
    else:
        judging_mode = "generic"
        rubric = {
            "alignment": "Does the answer satisfy the intent described by expected_notes?",
            "clarity": "Clear and direct; step-by-step when appropriate.",
            "safety": "Avoid overclaiming; prefer honest limitations.",
        }
        scoring_100 = "Meets expected_notes with high clarity and no major issues."
        scoring_threshold = "Mostly correct and helpful; minor issues but acceptable."
        scoring_0 = "Incorrect or misleading."

    prompt = {
        "id": case_id,
        "judging_mode": judging_mode,
        "expected_route": expected_route,
        "question": question,
        "answer": answer,
        "expected_notes": notes,
        "rubric": rubric,
        "scoring": {
            "100": scoring_100,
            f"{DEFAULT_JUDGE_PASS_SCORE}": scoring_threshold,
            "0": scoring_0,
        },
        "output_format": {
            "id": case_id,
            "score": 0,
            "pass": False,
            "reasons": ["..."],
        },
    }
    return system, json.dumps(prompt, ensure_ascii=False)


def _build_judge_prompt_with_routing(
    *,
    case_id: str,
    question: str,
    answer: str,
    expected: dict[str, Any],
    expected_route: str | None,
    routing: dict[str, Any],
) -> tuple[str, str]:
    system, _ = _build_judge_prompt(
        case_id=case_id,
        question=question,
        answer=answer,
        expected=expected,
        expected_route=expected_route,
    )
    notes = expected.get("notes") if isinstance(expected, dict) else None
    prompt = {
        "id": case_id,
        "question": question,
        "answer": answer,
        "expected_notes": notes,
        "expected_route": expected_route,
        "observed_routing": routing,
        "routing_guidance": {
            "primary": "observed_routing.primary is the first specialized agent transfer seen in SSE.",
            "final": "observed_routing.final is the last specialized agent transfer seen in SSE.",
            "handoff": "If expected_route matches final but not primary, that can still be acceptable if the first agent rejected and it was handed off correctly.",
        },
        "rubric": {
            "routing": "If expected_route is provided, prefer correct final routing. Penalize wrong routing that leads to hallucinated UI/capability claims.",
            "alignment": "Does the answer satisfy expected_notes?",
            "factuality": "Penalize hallucinations; reward honest limitations and KB-grounded statements.",
            "clarity": "Step-by-step for navigation; clear yes/no for capabilities.",
        },
        "scoring": {
            "100": "Correct routing (or correct recovery via handoff), and answer meets expected_notes with no hallucinations.",
            f"{DEFAULT_JUDGE_PASS_SCORE}": "Mostly correct routing and content; minor issues but acceptable.",
            "0": "Wrong routing and/or misleading/hallucinatory answer.",
        },
        "output_format": {
            "id": case_id,
            "score": 0,
            "pass": False,
            "reasons": ["..."],
        },
    }
    return system, json.dumps(prompt, ensure_ascii=False)


async def _judge_one(
    *,
    case_output: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    case_id = str(case_output.get("id", ""))
    expected_route = case_output.get("expected_route")
    expected_route_str = expected_route if isinstance(expected_route, str) else None
    expected_path = case_output.get("expected_path")
    expected_path_dict = expected_path if isinstance(expected_path, dict) else None
    routing = case_output.get("routing")
    routing_dict = routing if isinstance(routing, dict) else {}
    confirm = case_output.get("confirm")
    confirm_dict = confirm if isinstance(confirm, dict) else None

    # Deterministic judgment for response.path (fast vs full routing).
    if expected_path_dict is not None:
        observed_path = routing_dict.get("response_path")
        observed_path_dict = observed_path if isinstance(observed_path, dict) else None
        ok = (
            observed_path_dict is not None
            and observed_path_dict.get(RESPONSE_PATH_SOURCE_KEY) == expected_path_dict.get(RESPONSE_PATH_SOURCE_KEY)
            and observed_path_dict.get(RESPONSE_PATH_TYPE_KEY) == expected_path_dict.get(RESPONSE_PATH_TYPE_KEY)
        )
        if not ok:
            return {
                "id": case_id,
                "score": 0,
                "pass": False,
                "reasons": [
                    "response.path did not match expected (fast vs full).",
                    f"expected={expected_path_dict} observed={observed_path_dict}",
                ],
            }

    # Deterministic judgment for expected_route: do not let the LLM judge "decide" routing.
    if expected_route_str is not None:
        observed_final = routing_dict.get("final")
        observed_final_str = observed_final if isinstance(observed_final, str) else None
        if observed_final_str != expected_route_str:
            return {
                "id": case_id,
                "score": 0,
                "pass": False,
                "reasons": [
                    "Routing mismatch (deterministic check).",
                    f"expected_route={expected_route_str} observed_final={observed_final_str}",
                ],
            }

    # Deterministic judgment for finance_capture_agent cases: the "correct" terminal is confirm.request.
    if expected_route_str == ROUTE_FINANCE_CAPTURE:
        ok = confirm_dict is not None
        return {
            "id": case_id,
            "score": 100 if ok else 0,
            "pass": bool(ok),
            "reasons": (
                ["Received confirm.request from finance_capture_agent (HITL) and routing matched expected."]
                if ok
                else ["Expected finance_capture_agent confirm.request, but it was missing and/or routing did not match."]
            ),
        }

    system, prompt = _build_judge_prompt(
        case_id=case_id,
        question=str(case_output.get("question", "")),
        answer=str(case_output.get("answer", "")),
        expected=expected,
        expected_route=expected_route_str,
    )
    raw = await call_llm(system, prompt)
    obj = _extract_first_json_object(raw)
    if obj is None:
        return {
            "id": case_output.get("id", ""),
            "score": 0,
            "pass": False,
            "reasons": ["Judge returned invalid JSON"],
            "raw": raw,
        }

    score = obj.get("score")
    try:
        score_int = int(score)
    except (TypeError, ValueError):
        score_int = 0
    score_int = max(0, min(100, score_int))
    passed = bool(obj.get("pass")) if isinstance(obj.get("pass"), bool) else score_int >= DEFAULT_JUDGE_PASS_SCORE
    reasons = obj.get("reasons")
    if not isinstance(reasons, list) or not all(isinstance(x, str) for x in reasons):
        reasons = ["No reasons provided"]
    return {
        "id": case_output.get("id", ""),
        "score": score_int,
        "pass": passed,
        "reasons": reasons,
    }


async def _judge_all(
    *,
    results: list[dict[str, Any]],
    parallelism: int,
) -> list[dict[str, Any]]:
    sem = asyncio.Semaphore(parallelism)

    async def _guarded(case_output: dict[str, Any]) -> dict[str, Any]:
        expected = case_output.get("expected")
        expected_path = case_output.get("expected_path")
        expected_route = case_output.get("expected_route")
        if not isinstance(expected, dict) and not isinstance(expected_path, dict) and not isinstance(expected_route, str):
            return {
                "id": case_output.get("id", ""),
                "score": None,
                "pass": None,
                "reasons": ["No expected criteria provided (expected / expected_path); judge skipped"],
            }
        async with sem:
            expected_dict = expected if isinstance(expected, dict) else {}
            return await _judge_one(case_output=case_output, expected=expected_dict)

    tasks = [asyncio.create_task(_guarded(r)) for r in results]
    return await asyncio.gather(*tasks)


async def _judge_all_incremental(
    *,
    results: list[dict[str, Any]],
    parallelism: int,
    out_path: Path,
    show_progress: bool,
    only_ids: set[str] | None = None,
) -> None:
    id_to_index: dict[str, int] = {}
    for i, r in enumerate(results):
        cid = r.get("id")
        if isinstance(cid, str) and cid.strip():
            id_to_index[cid.strip()] = i

    sem = asyncio.Semaphore(parallelism)

    async def _guarded(case_output: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        expected = case_output.get("expected")
        cid = str(case_output.get("id", ""))
        status = case_output.get("status")
        if status == STATUS_ERROR:
            return (
                cid,
                {
                    "id": cid,
                    "score": None,
                    "pass": None,
                    "reasons": ["Case execution failed (status=error); judge skipped to avoid LLM noise/spend"],
                },
            )
        expected_path = case_output.get("expected_path")
        expected_route = case_output.get("expected_route")
        if not isinstance(expected, dict) and not isinstance(expected_path, dict) and not isinstance(expected_route, str):
            return (
                cid,
                {
                    "id": cid,
                    "score": None,
                    "pass": None,
                    "reasons": ["No expected criteria provided (expected / expected_path); judge skipped"],
                },
            )
        async with sem:
            expected_dict = expected if isinstance(expected, dict) else {}
            judged = await _judge_one(case_output=case_output, expected=expected_dict)
            return cid, judged

    targets: list[dict[str, Any]] = []
    for r in results:
        cid = r.get("id")
        if not isinstance(cid, str) or not cid.strip():
            continue
        if only_ids is not None and cid.strip() not in only_ids:
            continue
        targets.append(r)

    tasks = [asyncio.create_task(_guarded(r)) for r in targets]
    total = len(tasks)
    completed = 0
    for task in asyncio.as_completed(tasks):
        cid, judged = await task
        idx = id_to_index.get(cid)
        if idx is None:
            continue
        results[idx]["judge"] = judged
        if isinstance(results[idx].get("judge"), dict):
            if results[idx].get("status") == STATUS_ERROR or judged.get("score") is None and judged.get("pass") is None:
                results[idx]["status"] = STATUS_JUDGE_SKIPPED
            else:
                results[idx]["status"] = STATUS_JUDGED
        _atomic_write_json(out_path, results)
        completed += 1
        _print_progress(
            f"[judge] {completed}/{total} done (last_id={cid})",
            show=show_progress,
        )


def _post_json(
    session: requests.Session,
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout_seconds: float,
) -> dict[str, Any]:
    resp = session.post(url, json=payload, headers=headers, timeout=timeout_seconds)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object from {url}")
    return data


def _iter_sse_lines(resp: requests.Response) -> Any:
    for line in resp.iter_lines(decode_unicode=True):
        if line is None:
            continue
        yield line


def _listen_for_message_completed(
    *,
    session: requests.Session,
    sse_url: str,
    headers: dict[str, str],
    timeout_seconds: float,
    done: threading.Event,
    answer_holder: dict[str, str],
    routing_holder: dict[str, Any],
    confirm_holder: dict[str, Any],
) -> None:
    event_name: Optional[str] = None
    data_lines: list[str] = []

    try:
        with session.get(sse_url, headers=headers, stream=True, timeout=timeout_seconds) as resp:
            resp.raise_for_status()
            for line in _iter_sse_lines(resp):
                if done.is_set():
                    return

                line_str = str(line).rstrip("\r\n")

                if line_str == "":
                    if data_lines:
                        data_str = "\n".join(data_lines)
                        try:
                            payload = json.loads(data_str)
                        except json.JSONDecodeError:
                            payload = {}

                        if event_name == "source.search.start":
                            tool = payload.get("tool")
                            if isinstance(tool, str) and tool.strip():
                                routing_holder.setdefault("transfers", []).append(tool.strip())

                        if (
                            event_name == RESPONSE_PATH_EVENT
                            and isinstance(payload, dict)
                            and payload
                            and "response_path" not in routing_holder
                        ):
                            raw_source = payload.get(RESPONSE_PATH_SOURCE_KEY)
                            raw_type = payload.get(RESPONSE_PATH_TYPE_KEY)
                            if (
                                isinstance(raw_source, str)
                                and raw_source.strip()
                                and isinstance(raw_type, str)
                                and raw_type.strip()
                            ):
                                routing_holder["response_path"] = {
                                    RESPONSE_PATH_SOURCE_KEY: raw_source.strip(),
                                    RESPONSE_PATH_TYPE_KEY: raw_type.strip(),
                                }

                        if event_name == "confirm.request" and isinstance(payload, dict) and payload:
                            confirm_holder["confirm"] = payload
                            done.set()
                            return

                        if event_name == MESSAGE_COMPLETED_EVENT:
                            # /supervisor/initialize emits a welcome as {"text": ...}. We MUST ignore that and wait for
                            # the actual /supervisor/message completion, which is emitted as {"content": ...}.
                            content = payload.get("content")
                            if isinstance(content, str) and content.strip():
                                answer_holder["answer"] = content.strip()
                                done.set()
                                return
                    event_name = None
                    data_lines = []
                    continue

                if line_str.startswith("event:"):
                    event_name = line_str[len("event:") :].strip()
                    continue

                if line_str.startswith("data:"):
                    data_lines.append(line_str[len("data:") :].strip())
                    continue
    except requests.RequestException as exc:
        answer_holder["answer"] = f"[SSE_ERROR] {type(exc).__name__}: {exc}"
        done.set()


def _resolve_sse_url(base_url: str, sse_url_from_init: Optional[str], thread_id: str) -> str:
    base_url = base_url.rstrip("/") + "/"
    if isinstance(sse_url_from_init, str) and sse_url_from_init.strip():
        raw = sse_url_from_init.strip()
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        return urljoin(base_url, raw.lstrip("/"))
    return urljoin(base_url, f"supervisor/sse/{thread_id}")


def run_case(
    *,
    base_url: str,
    user_id: str,
    case: CaseInput,
    headers: dict[str, str],
    timeout_seconds: float,
    sse_connect_delay_seconds: float,
) -> CaseOutput:
    base_url = base_url.rstrip("/") + "/"

    with requests.Session() as post_session, requests.Session() as sse_session:
        init_url = urljoin(base_url, "supervisor/initialize")
        init_payload: dict[str, Any] = {"user_id": user_id, "voice": False}
        init_data = _post_json(post_session, init_url, init_payload, headers=headers, timeout_seconds=timeout_seconds)

        thread_id = init_data.get("thread_id")
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise ValueError("Supervisor initialize did not return thread_id")
        thread_id = thread_id.strip()

        sse_url = _resolve_sse_url(base_url, init_data.get("sse_url"), thread_id)

        done = threading.Event()
        answer_holder: dict[str, str] = {}
        routing_holder: dict[str, Any] = {"transfers": []}
        confirm_holder: dict[str, Any] = {}

        t = threading.Thread(
            target=_listen_for_message_completed,
            kwargs={
                "session": sse_session,
                "sse_url": sse_url,
                "headers": headers,
                "timeout_seconds": timeout_seconds,
                "done": done,
                "answer_holder": answer_holder,
                "routing_holder": routing_holder,
                "confirm_holder": confirm_holder,
            },
            daemon=True,
        )
        t.start()
        time.sleep(sse_connect_delay_seconds)

        msg_url = urljoin(base_url, "supervisor/message")
        msg_payload: dict[str, Any] = {"thread_id": thread_id, "text": case.question, "voice": case.voice}
        _post_json(post_session, msg_url, msg_payload, headers=headers, timeout_seconds=timeout_seconds)

        if not done.wait(timeout=timeout_seconds):
            done.set()
            raise TimeoutError(f"Timed out waiting for '{MESSAGE_COMPLETED_EVENT}' after {timeout_seconds}s")

        answer = answer_holder.get("answer", "")
        confirm = confirm_holder.get("confirm")
        confirm_dict = confirm if isinstance(confirm, dict) else None
        transfers: list[str] = routing_holder.get("transfers", []) if isinstance(routing_holder.get("transfers"), list) else []
        routes = [TRANSFER_TOOL_TO_ROUTE[t] for t in transfers if t in TRANSFER_TOOL_TO_ROUTE]
        response_path = routing_holder.get("response_path")
        response_path_dict = response_path if isinstance(response_path, dict) else None
        routing = {
            "transfers": transfers,
            "routes": routes,
            "primary": routes[0] if routes else None,
            "final": routes[-1] if routes else None,
            "response_path": response_path_dict,
        }
        return CaseOutput(
            id=case.id,
            question=case.question,
            answer=answer,
            thread_id=thread_id,
            expected=case.expected,
            expected_route=case.expected_route,
            expected_path=case.expected_path,
            routing=routing,
            confirm=confirm_dict,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run supervisor SSE cases and export question/answer JSON")
    parser.add_argument("--in", dest="in_path", required=False, help="Path to input JSON with cases (defaults to cases.json next to this script)")
    parser.add_argument("--base-url", dest="base_url", default=None, help="Override base_url from input JSON")
    parser.add_argument("--user-id", dest="user_id", default=None, help="Override user_id from input JSON")
    parser.add_argument("--token", dest="token", default=None, help="Optional Bearer token for API calls")
    parser.add_argument("--timeout", dest="timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Timeout seconds")
    parser.add_argument("--quiet", dest="quiet", action="store_true", help="Disable progress output (only results.json is written)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--only",
        dest="only",
        default=None,
        help="Run only a subset of cases: single id, comma-separated ids, or regex (/pattern/ or re:pattern) matched against case ids",
    )
    group.add_argument(
        "--only-failed",
        dest="only_failed",
        action="store_true",
        help="Run only cases that previously had status=error or judge.score==0 (reads existing results.json next to this script)",
    )
    parser.add_argument(
        "--sse-connect-delay",
        dest="sse_connect_delay",
        type=float,
        default=DEFAULT_SSE_CONNECT_DELAY_SECONDS,
        help="Delay between opening SSE and sending /message",
    )
    args = parser.parse_args()

    # Fix Windows console encoding
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    default_in_path = Path(__file__).parent / DEFAULT_CASES_FILENAME
    in_path = Path(args.in_path) if args.in_path else default_in_path
    out_path = Path(__file__).parent / DEFAULT_RESULTS_FILENAME
    payload = _load_json(in_path)

    base_url = args.base_url or payload.get("base_url") or DEFAULT_BASE_URL
    user_id = args.user_id or payload.get("user_id")

    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("base_url must be provided (CLI --base-url or in JSON)")
    base_url = base_url.strip()
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id must be provided (CLI --user-id or in JSON)")
    user_id = user_id.strip()

    cases = _parse_cases(payload.get("cases"))
    parallelism = _parse_parallelism(payload)
    show_progress = DEFAULT_SHOW_PROGRESS and not bool(args.quiet)

    headers = _build_headers(args.token)

    all_case_ids = [c.id for c in cases]
    selected_ids: set[str] | None = None
    if args.only_failed:
        existing_results = _try_load_existing_results(out_path)
        if existing_results is None:
            raise ValueError("--only-failed requires an existing results.json next to this script")
        selected_ids = _select_failed_case_ids(existing_results)
    elif isinstance(args.only, str) and args.only.strip():
        selected_ids = _select_case_ids_from_only_arg(args.only, all_case_ids)
        missing = selected_ids - set(all_case_ids)
        if missing:
            raise ValueError(f"--only referenced unknown case ids: {sorted(missing)}")

    existing_results = _try_load_existing_results(out_path)
    existing_by_id: dict[str, dict[str, Any]] = {}
    if existing_results is not None:
        for r in existing_results:
            cid = r.get("id")
            if isinstance(cid, str) and cid.strip() and cid.strip() not in existing_by_id:
                existing_by_id[cid.strip()] = r

    results: list[dict[str, Any]] = []
    for c in cases:
        prev = existing_by_id.get(c.id)
        if isinstance(prev, dict):
            merged = dict(prev)
            merged["id"] = c.id
            merged["question"] = c.question
            merged["expected"] = c.expected
            merged["expected_route"] = c.expected_route
            merged["expected_path"] = c.expected_path
            merged.setdefault("routing", {"transfers": [], "routes": [], "primary": None, "final": None, "response_path": None})
            merged.setdefault("status", STATUS_PENDING)
            merged.setdefault("answer", None)
            merged.setdefault("thread_id", None)
            merged.setdefault("judge", None)
            merged.setdefault("confirm", None)
            results.append(merged)
        else:
            results.append(
                {
                    "id": c.id,
                    "question": c.question,
                    "expected": c.expected,
                    "expected_route": c.expected_route,
                    "expected_path": c.expected_path,
                    "status": STATUS_PENDING,
                    "answer": None,
                    "thread_id": None,
                    "judge": None,
                    "routing": {"transfers": [], "routes": [], "primary": None, "final": None, "response_path": None},
                    "confirm": None,
                }
            )
    _atomic_write_json(out_path, results)

    selected_indices: list[int] = []
    for i, c in enumerate(cases):
        if selected_ids is None or c.id in selected_ids:
            selected_indices.append(i)
    if isinstance(args.only, str) and args.only.strip() and not selected_indices:
        raise ValueError("--only did not match any cases")
    _print_progress(
        f"[start] cases={len(cases)} selected={len(selected_indices)} parallelism={parallelism} out={out_path.as_posix()} base_url={base_url}",
        show=show_progress,
    )

    if not cases or not selected_indices:
        _atomic_write_json(out_path, results)
    else:
        max_workers = min(parallelism, len(selected_indices))
        total_cases = len(selected_indices)
        completed_cases = 0

        def _run_one(case_index: int, case: CaseInput) -> tuple[int, CaseOutput]:
            try:
                out = run_case(
                    base_url=base_url,
                    user_id=user_id,
                    case=case,
                    headers=headers,
                    timeout_seconds=float(args.timeout),
                    sse_connect_delay_seconds=float(args.sse_connect_delay),
                )
                return case_index, out
            except Exception as exc:
                err_out = CaseOutput(
                    id=case.id,
                    question=case.question,
                    answer=f"[ERROR] {type(exc).__name__}: {exc}",
                    thread_id="",
                    expected=None,
                    expected_route=case.expected_route,
                    expected_path=case.expected_path,
                    routing={"transfers": [], "routes": [], "primary": None, "final": None, "response_path": None},
                    confirm=None,
                )
                return case_index, err_out

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_run_one, idx, cases[idx]) for idx in selected_indices]
            for fut in as_completed(futures):
                idx, result = fut.result()
                status = STATUS_CONFIRM_REQUESTED if result.confirm is not None else STATUS_COMPLETED
                if status != STATUS_CONFIRM_REQUESTED and isinstance(result.answer, str) and result.answer.startswith("["):
                    status = STATUS_ERROR
                results[idx] = {
                    "id": result.id,
                    "question": result.question,
                    "expected": result.expected,
                    "expected_route": result.expected_route,
                    "expected_path": result.expected_path,
                    "status": status,
                    "answer": result.answer,
                    "thread_id": result.thread_id,
                    "judge": None,
                    "routing": result.routing,
                    "confirm": result.confirm,
                }
                _atomic_write_json(out_path, results)
                completed_cases += 1
                _print_progress(
                    f"[cases] {completed_cases}/{total_cases} done (last_id={result.id} status={status})",
                    show=show_progress,
                )

    # Judge incrementally and persist after each judgment result.
    asyncio.run(
        _judge_all_incremental(
            results=results,
            parallelism=parallelism,
            out_path=out_path,
            show_progress=show_progress,
            only_ids=selected_ids,
        )
    )

    status_counts = _count_statuses(results)
    route_mismatches, path_mismatches = _summarize_mismatches(results)
    failures = _summarize_failures(results)

    _print_progress("", show=show_progress)
    _print_progress("[summary]", show=show_progress)
    _print_progress(f"  total: {len(results)}", show=show_progress)
    _print_progress(f"  statuses: {status_counts}", show=show_progress)
    _print_progress(f"  route_mismatches: {len(route_mismatches)}", show=show_progress)
    if route_mismatches:
        _print_progress(f"    ids: {route_mismatches}", show=show_progress)
    _print_progress(f"  path_mismatches: {len(path_mismatches)}", show=show_progress)
    if path_mismatches:
        _print_progress(f"    ids: {path_mismatches}", show=show_progress)
    _print_progress(f"  judge_failures: {len(failures)}", show=show_progress)
    for cid, score, reason0 in failures[:10]:
        _print_progress(f"    - {cid}: score={score} reason0={reason0}", show=show_progress)


if __name__ == "__main__":
    main()


