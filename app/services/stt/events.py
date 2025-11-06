from typing import Any, Dict

TRANSCRIPT_EVENTS = {
    "start": "transcript_start",
    "chunk": "transcript_chunk",
    "completed": "transcript_completed",
    "error": "transcript_error",
}


def create_transcript_start_event(meta: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": TRANSCRIPT_EVENTS["start"], "meta": meta}


def create_transcript_chunk_event(text: str, is_final: bool = False, ts: float | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"type": TRANSCRIPT_EVENTS["chunk"], "text": text, "final": is_final}
    if ts is not None:
        payload["ts"] = ts
    return payload


def create_transcript_completed_event(result: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": TRANSCRIPT_EVENTS["completed"], "result": result}


def create_transcript_error_event(message: str, code: str | None = None) -> Dict[str, Any]:
    return {"type": TRANSCRIPT_EVENTS["error"], "message": message, "code": code}
