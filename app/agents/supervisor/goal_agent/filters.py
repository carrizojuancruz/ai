from __future__ import annotations


def strip_notifications(value):
    if isinstance(value, dict):
        return {
            k: strip_notifications(v)
            for k, v in value.items()
            if k == "notifications_enabled" or ("notification" not in k and "reminder" not in k)
        }
    if isinstance(value, list):
        return [strip_notifications(v) for v in value]
    return value
