import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from app.observability.logging_config import get_logger

from .templates import NudgeChannel, NudgeRegistry, NudgeType

logger = get_logger(__name__)


@dataclass
class NudgeSelection:
    memory_key: Optional[str] = None
    variables: dict[str, Any] = None
    preview_text: str = ""
    nudge_prompt_line: str = ""
    channel: NudgeChannel = NudgeChannel.PUSH
    rule_id: Optional[str] = None

    def __post_init__(self):
        if self.variables is None:
            self.variables = {}


class NudgeSelector:
    def __init__(self, s3_vectors_store, registry: Optional[NudgeRegistry] = None):
        self.s3_vectors_store = s3_vectors_store
        self.registry = registry or NudgeRegistry()

    async def select_nudge(
        self,
        user_id: UUID,
        nudge_type: NudgeType,
        now: Optional[datetime] = None,
        rule_id: Optional[str] = None,
        payload: Optional[dict] = None,
        user_context: Optional[dict] = None,
    ) -> Optional[NudgeSelection]:
        now = now or datetime.utcnow()

        logger.info(
            "nudge.selector.start",
            extra={
                "user_id": str(user_id),
                "nudge_type": nudge_type.value,
                "rule_id": rule_id,
            },
        )

        try:
            if nudge_type == NudgeType.STATIC_BILL:
                selection = self._select_static_bill(payload)
            elif nudge_type == NudgeType.MEMORY_ICEBREAKER:
                selection = await self._select_memory_icebreaker(user_id, now)
            elif nudge_type == NudgeType.INFO_BASED:
                selection = await self._select_info_based(user_id, rule_id, now, user_context)
            else:
                logger.warning(f"Unknown nudge type: {nudge_type}")
                return None

            if selection:
                logger.info(
                    "nudge.selector.end",
                    extra={
                        "user_id": str(user_id),
                        "nudge_type": nudge_type.value,
                        "rule_id": selection.rule_id,
                        "memory_key": selection.memory_key,
                    },
                )
            else:
                logger.info(
                    "nudge.skipped",
                    extra={
                        "user_id": str(user_id),
                        "nudge_type": nudge_type.value,
                        "reason": "no_candidates",
                    },
                )

            return selection

        except Exception as e:
            logger.error(
                "nudge.selector.error",
                extra={
                    "user_id": str(user_id),
                    "error": str(e),
                },
            )
            return None

    def _select_static_bill(self, payload: Optional[dict]) -> Optional[NudgeSelection]:
        if not payload or "bill" not in payload:
            logger.warning("Static bill nudge missing payload")
            return None

        bill = payload["bill"]

        return NudgeSelection(
            variables={
                "label": bill.get("label", "Bill"),
                "due_date": bill.get("due_date", "soon"),
                "amount": bill.get("amount", 0),
            },
            preview_text=f"{bill.get('label', 'Bill')} due {bill.get('due_date', 'soon')}",
            nudge_prompt_line=(
                f"NUDGE_CONTEXT: The user has a {bill.get('label', 'bill')} "
                f"due on {bill.get('due_date', 'soon')} for ${bill.get('amount', 0):.2f}. "
                "Open with a friendly reminder about this upcoming payment."
            ),
            channel=NudgeChannel(payload.get("channel", "push")),
            rule_id="static_bill",
        )

    async def _select_memory_icebreaker(self, user_id: UUID, now: datetime) -> Optional[NudgeSelection]:
        last_week = now - timedelta(days=7)
        bucket_week = last_week.strftime("%Y-%W")

        filter_dict = {
            "importance_bin": "high",
            "bucket_week": bucket_week,
        }

        candidates = await self.s3_vectors_store.search_by_filter(
            namespace=(str(user_id), "semantic"),
            filter=filter_dict,
            limit=100,
        )

        if not candidates:
            return None

        seed_str = f"{user_id}{now.strftime('%Y-%m-%d')}"
        seed = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16)

        sorted_candidates = sorted(candidates, key=lambda c: (c.metadata.get("created_at", ""), c.key))

        selected = sorted_candidates[seed % len(sorted_candidates)]

        memory_value = selected.value
        category = memory_value.get("category", "recent activity")
        summary = memory_value.get("summary", "")[:100]

        return NudgeSelection(
            memory_key=selected.key,
            variables={
                "category": category,
                "summary": summary,
            },
            preview_text=f"Let's talk about your {category}",
            nudge_prompt_line=(
                f"NUDGE_CONTEXT: Start a conversation about {category}: {summary}. "
                "Open with a friendly observation and invite discussion."
            ),
            channel=NudgeChannel.IN_APP,
            rule_id="memory_icebreaker",
        )

    async def _select_info_based(
        self, user_id: UUID, rule_id: Optional[str], now: datetime, user_context: Optional[dict]
    ) -> Optional[NudgeSelection]:
        if not rule_id:
            templates = self.registry.get_by_type(NudgeType.INFO_BASED)
            logger.info(
                "nudge.info_based.all_templates",
                extra={
                    "user_id": str(user_id),
                    "template_count": len(templates),
                    "template_ids": [t.rule_id for t in templates],
                },
            )
        else:
            template = self.registry.get(rule_id)
            if not template:
                logger.warning(f"Template not found: {rule_id}")
                return None
            templates = [template]

        user_context = user_context or {}

        logger.info(
            "nudge.info_based.context_check",
            extra={
                "user_id": str(user_id),
                "has_budget": user_context.get("budget_posture", {}).get("active_budget", False),
                "timezone": user_context.get("locale_info", {}).get("time_zone", "UTC"),
                "current_hour": now.hour,
            },
        )

        for template in templates:
            logger.info(
                "nudge.template.evaluating",
                extra={
                    "user_id": str(user_id),
                    "template_id": template.rule_id,
                    "topic_keys": template.topic_keys,
                    "required_metadata": template.required_metadata_keys,
                },
            )

            if not self._check_quiet_hours(template, now, user_context):
                logger.info(
                    "nudge.template.quiet_hours",
                    extra={
                        "user_id": str(user_id),
                        "template_id": template.rule_id,
                        "current_hour": now.hour,
                        "quiet_start": template.quiet_hours_start,
                        "quiet_end": template.quiet_hours_end,
                    },
                )
                continue

            filter_dict = {}
            if template.topic_keys:
                pass

            all_candidates = []
            for topic_key in template.topic_keys:
                filter_dict = {"topic_key": topic_key}

                if "valid_until" in template.required_metadata_keys:
                    pass

                candidates = await self.s3_vectors_store.search_by_filter(
                    namespace=(str(user_id), "semantic"),
                    filter=filter_dict,
                    limit=50,
                )
                logger.info(
                    "nudge.memory.search",
                    extra={
                        "user_id": str(user_id),
                        "template_id": template.rule_id,
                        "topic_key": topic_key,
                        "candidates_found": len(candidates),
                    },
                )
                all_candidates.extend(candidates)

            if not all_candidates:
                logger.info(
                    "nudge.template.no_candidates",
                    extra={
                        "user_id": str(user_id),
                        "template_id": template.rule_id,
                    },
                )
                continue

            eligible = []
            for candidate in all_candidates:
                memory_value = candidate.value
                memory_meta = candidate.metadata

                cooldown_until = memory_meta.get("nudge_cooldown_until")
                if cooldown_until:
                    cooldown_date = datetime.fromisoformat(cooldown_until.replace("Z", "+00:00"))
                    if now < cooldown_date:
                        logger.debug(
                            "nudge.memory.cooldown",
                            extra={
                                "user_id": str(user_id),
                                "memory_key": candidate.key,
                                "cooldown_until": cooldown_until,
                            },
                        )
                        continue

                if template.predicate:
                    try:
                        predicate_result = template.predicate(user_context, memory_value, memory_meta, now)
                        if predicate_result:
                            eligible.append(candidate)
                            logger.info(
                                "nudge.predicate.match",
                                extra={
                                    "user_id": str(user_id),
                                    "template_id": template.rule_id,
                                    "memory_key": candidate.key,
                                    "memory_category": memory_value.get("category"),
                                    "importance_bin": memory_meta.get("importance_bin"),
                                },
                            )
                    except Exception as e:
                        logger.warning(
                            "nudge.predicate.error",
                            extra={
                                "user_id": str(user_id),
                                "template_id": template.rule_id,
                                "memory_key": candidate.key,
                                "error": str(e),
                            },
                        )
                        continue
                else:
                    eligible.append(candidate)

            if not eligible:
                logger.info(
                    "nudge.template.no_eligible",
                    extra={
                        "user_id": str(user_id),
                        "template_id": template.rule_id,
                        "total_candidates": len(all_candidates),
                    },
                )
                continue

            sorted_eligible = sorted(
                eligible, key=lambda c: (-template.priority, c.metadata.get("created_at", ""), c.key)
            )

            seed_str = f"{user_id}{now.strftime('%Y-%m-%d')}{template.rule_id}"
            seed = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16)
            selected = sorted_eligible[seed % len(sorted_eligible)]

            logger.info(
                "nudge.template.selected",
                extra={
                    "user_id": str(user_id),
                    "template_id": template.rule_id,
                    "eligible_count": len(eligible),
                    "selected_memory": selected.key,
                    "selected_category": selected.value.get("category"),
                },
            )

            variables = self._extract_variables(selected.value, selected.metadata, template.required_metadata_keys)

            preview_text = template.preview_template.format(**variables)
            nudge_prompt_line = template.prompt_template.format(**variables)

            return NudgeSelection(
                memory_key=selected.key,
                variables=variables,
                preview_text=preview_text,
                nudge_prompt_line=nudge_prompt_line,
                channel=template.default_channel,
                rule_id=template.rule_id,
            )

        logger.info(
            "nudge.info_based.no_match",
            extra={
                "user_id": str(user_id),
                "templates_tried": len(templates),
            },
        )
        return None

    def _check_quiet_hours(self, template, now: datetime, user_context: dict) -> bool:
        if not template.quiet_hours_start or not template.quiet_hours_end:
            return True

        # Get user's timezone if available
        timezone = user_context.get("locale_info", {}).get("time_zone", "UTC")
        current_hour = now.hour

        logger.debug(
            "nudge.quiet_hours.check",
            extra={
                "timezone": timezone,
                "current_hour": current_hour,
                "quiet_start": template.quiet_hours_start,
                "quiet_end": template.quiet_hours_end,
            },
        )

        if template.quiet_hours_start > template.quiet_hours_end:
            if current_hour >= template.quiet_hours_start or current_hour < template.quiet_hours_end:
                return False
        else:
            if template.quiet_hours_start <= current_hour < template.quiet_hours_end:
                return False

        return True

    def _extract_variables(self, memory_value: dict, memory_meta: dict, required_keys: list[str]) -> dict[str, Any]:
        variables = {}

        combined = {**memory_value, **memory_meta}

        for key in required_keys:
            variables[key] = combined.get(key, "N/A")

        variables.update(
            {
                "category": combined.get("category", "activity"),
                "importance": combined.get("importance_bin", "normal"),
            }
        )

        return variables


async def update_memory_cooldown(s3_vectors_store, user_id: UUID, memory_key: str, cooldown_days: int) -> None:
    try:
        cooldown_until = datetime.utcnow() + timedelta(days=cooldown_days)

        await s3_vectors_store.update_metadata(
            namespace=(str(user_id), "semantic"),
            key=memory_key,
            metadata_update={
                "nudge_cooldown_until": cooldown_until.isoformat(),
            },
        )

        logger.info(f"Updated cooldown for memory {memory_key}")
    except Exception as e:
        logger.error(f"Failed to update cooldown: {e}")
