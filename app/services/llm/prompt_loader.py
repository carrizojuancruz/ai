"""Prompt loader service for centralized prompt management.

Provides a unified interface to load prompts from bundled defaults.
Enforces ASCII formatting rules and prevents hardcoded prompt literals.
"""

import importlib
import logging
import sys

logger = logging.getLogger(__name__)


def _clean_malformed_message_lines(text: str) -> str:
    r"""Clean malformed message lines from conversation state.

    When human-in-the-loop interrupts occur (e.g., LangGraph confirm_human),
    they can leave malformed messages in the conversation state with empty
    bullet points like "-" or "- ". These malformed lines break prompt loading
    when recent messages are included in prompts.

    This function removes lines that are:
    - Just "-" (empty bullet point)
    - End with " -" (incomplete bullet point)

    Args:
        text: Raw text from conversation messages that may contain malformed lines

    Returns:
        Cleaned text with malformed lines removed

    Example:
        >>> _clean_malformed_message_lines("Hello\n-\nWorld")
        "Hello\nWorld"

    """
    if not text:
        return text

    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.rstrip()
        if stripped and stripped != '-' and not stripped.endswith(' -'):
            cleaned_lines.append(stripped)
    return '\n'.join(cleaned_lines)


def _normalize_markdown_bullets(text: str) -> str:
    r"""Normalize markdown bullet formatting in prompts.

    Ensures consistent markdown formatting by:
    - Converting standalone "-" to "---" (horizontal rule)
    - Normalizing bullet points to use "- " format (ensures space after dash)
    - Preserving indentation when fixing bullet points

    This is used to ensure prompts meet the formatting requirements enforced
    by _validate_prompt_format() which requires bullets to use "- " format.

    Args:
        text: Prompt text that may contain improperly formatted bullets

    Returns:
        Normalized text with properly formatted markdown bullets

    Example:
        >>> _normalize_markdown_bullets("-item\n-text")
        "- item\n- text"
        >>> _normalize_markdown_bullets("  -item")
        "  - item"

    """
    if not text:
        return text

    lines = []
    for line in text.splitlines():
        s = line.rstrip()
        t = s.strip()
        if t == "-":
            s = "---"
        else:
            leading = len(s) - len(s.lstrip())
            prefix, body = s[:leading], s[leading:]
            bt = body.strip()
            if bt.startswith("-") and not (bt.startswith("- ") or bt.startswith("---")):
                body = "- " + body[1:].lstrip()
                s = prefix + body
        lines.append(s)
    return "\n".join(lines)


class PromptLoader:
    """Centralized prompt loader that enforces meta-invariants."""

    def __init__(self):
        self._bundled_defaults = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register bundled prompt defaults."""
        self._bundled_defaults.update({
            "supervisor_system_prompt": self._get_supervisor_prompt_local,
            "wealth_agent_constant_prompt": self._get_wealth_agent_constant_prompt_local,
            "goal_agent_system_prompt": self._get_goal_agent_prompt_local,
            "finance_agent_system_prompt": self._get_finance_agent_prompt_local,
            "wealth_agent_system_prompt": self._get_wealth_agent_system_prompt_local,
            "onboarding_name_extraction": self._get_onboarding_name_extraction_local,
            "onboarding_location_extraction": self._get_onboarding_location_extraction_local,
            "memory_hotpath_trigger_classifier": self._get_memory_hotpath_trigger_classifier_local,
            "memory_same_fact_classifier": self._get_memory_same_fact_classifier_local,
            "memory_compose_summaries": self._get_memory_compose_summaries_local,
            "episodic_memory_summarizer": self._get_episodic_memory_summarizer_local,
            "profile_sync_extractor": self._get_profile_sync_extractor_local,
            "guest_system_prompt": self._get_guest_system_prompt_local,
            "title_generator_system_prompt": self._get_title_generator_system_prompt_local,
            "conversation_summarizer_system_prompt": self._get_conversation_summarizer_system_prompt_local,
            "welcome_generator_system_prompt": self._get_welcome_generator_system_prompt_local,
            "title_generator_user_prompt_template": self._get_title_generator_user_prompt_template_local,
            "supervisor_delegation_template": self._get_supervisor_delegation_template_local,
            "memory_icebreaker_generation_prompt": self._get_memory_icebreaker_generation_prompt_local,
            "conversation_summarizer_instruction": self._get_conversation_summarizer_instruction_local,
            "finance_capture_nova_intent_prompt": self._get_finance_capture_nova_intent_prompt,
            "memory_merge_summaries": self._get_memory_merge_summaries_local,
        })


    async def _get_supervisor_prompt_local(self) -> str:
        agent_prompts = sys.modules.get('app.services.llm.agent_prompts')
        if agent_prompts is None:
            from . import agent_prompts
        result = await agent_prompts.get_supervisor_system_prompt()
        return result.strip()

    def _get_wealth_agent_constant_prompt_local(self) -> str:
        agent_prompts = sys.modules.get('app.services.llm.agent_prompts')
        if agent_prompts is None:
            from . import agent_prompts
        result = agent_prompts.build_wealth_system_prompt()
        return result

    def _get_goal_agent_prompt_local(self) -> str:
        agent_prompts = sys.modules.get('app.services.llm.agent_prompts')
        if agent_prompts is None:
            from . import agent_prompts
        result = agent_prompts.build_goal_agent_system_prompt()
        return result

    def _get_finance_agent_prompt_local(self, **kwargs) -> str:
        agent_prompts = sys.modules.get('app.services.llm.agent_prompts')
        if agent_prompts is None:
            from . import agent_prompts
        result = agent_prompts.build_finance_system_prompt_local(**kwargs)
        return result

    def _get_wealth_agent_system_prompt_local(self, **kwargs) -> str:
        agent_prompts = sys.modules.get('app.services.llm.agent_prompts')
        if agent_prompts is None:
            from . import agent_prompts
        result = agent_prompts.build_wealth_system_prompt_local(**kwargs)
        return result

    def _get_onboarding_name_extraction_local(self) -> str:
        onboarding_prompts = sys.modules.get('app.services.llm.onboarding_prompts')
        if onboarding_prompts is None:
            from . import onboarding_prompts
        return onboarding_prompts.ONBOARDING_NAME_EXTRACTION_LOCAL.strip()

    def _get_onboarding_location_extraction_local(self) -> str:
        onboarding_prompts = sys.modules.get('app.services.llm.onboarding_prompts')
        if onboarding_prompts is None:
            from . import onboarding_prompts
        return onboarding_prompts.ONBOARDING_LOCATION_EXTRACTION_LOCAL.strip()

    def _get_memory_hotpath_trigger_classifier_local(self, **kwargs) -> str:
        memory_prompts = sys.modules.get('app.services.llm.memory_prompts')
        if memory_prompts is None:
            from . import memory_prompts

        text_param = kwargs.get('text', '')
        if text_param:
            kwargs['text'] = _clean_malformed_message_lines(text_param)

        return memory_prompts.MEMORY_HOTPATH_TRIGGER_CLASSIFIER_LOCAL.format(**kwargs).strip()

    def _get_memory_same_fact_classifier_local(self, **kwargs) -> str:
        memory_prompts = sys.modules.get('app.services.llm.memory_prompts')
        if memory_prompts is None:
            from . import memory_prompts
        return memory_prompts.MEMORY_SAME_FACT_CLASSIFIER_LOCAL.format(**kwargs).strip()

    def _get_memory_compose_summaries_local(self, **kwargs) -> str:
        memory_prompts = sys.modules.get('app.services.llm.memory_prompts')
        if memory_prompts is None:
            from . import memory_prompts
        return memory_prompts.MEMORY_COMPOSE_SUMMARIES_LOCAL.format(**kwargs).strip()

    def _get_episodic_memory_summarizer_local(self, **kwargs) -> str:
        memory_prompts = sys.modules.get('app.services.llm.memory_prompts')
        if memory_prompts is None:
            from . import memory_prompts
        return memory_prompts.MEMORY_EPISODIC_SUMMARIZER_LOCAL.strip()

    def _get_profile_sync_extractor_local(self, **kwargs) -> str:
        memory_prompts = sys.modules.get('app.services.llm.memory_prompts')
        if memory_prompts is None:
            from . import memory_prompts
        return memory_prompts.MEMORY_PROFILE_SYNC_EXTRACTOR_LOCAL.strip()

    def _get_guest_system_prompt_local(self, **kwargs) -> str:
        agent_prompts = sys.modules.get('app.services.llm.agent_prompts')
        if agent_prompts is None:
            from . import agent_prompts
        max_messages = kwargs.get('max_messages', 5)
        return agent_prompts.build_guest_system_prompt_local(max_messages)

    def _get_title_generator_system_prompt_local(self) -> str:
        utility_prompts = sys.modules.get('app.services.llm.utility_prompts')
        if utility_prompts is None:
            from . import utility_prompts
        return utility_prompts.TITLE_GENERATOR_SYSTEM_PROMPT_LOCAL.strip()

    def _get_conversation_summarizer_system_prompt_local(self) -> str:
        utility_prompts = sys.modules.get('app.services.llm.utility_prompts')
        if utility_prompts is None:
            from . import utility_prompts
        return utility_prompts.CONVERSATION_SUMMARIZER_SYSTEM_PROMPT_LOCAL

    def _get_welcome_generator_system_prompt_local(self) -> str:
        utility_prompts = sys.modules.get('app.services.llm.utility_prompts')
        if utility_prompts is None:
            from . import utility_prompts
        return utility_prompts.WELCOME_GENERATOR_SYSTEM_PROMPT_LOCAL

    def _get_title_generator_user_prompt_template_local(self, **kwargs) -> str:
        utility_prompts = sys.modules.get('app.services.llm.utility_prompts')
        if utility_prompts is None:
            from . import utility_prompts
        body = kwargs.get('body', '')
        return utility_prompts.TITLE_GENERATOR_USER_PROMPT_TEMPLATE_LOCAL.format(body=body)

    def _get_supervisor_delegation_template_local(self, **kwargs) -> str:
        agent_prompts = sys.modules.get('app.services.llm.agent_prompts')
        if agent_prompts is None:
            from . import agent_prompts
        task_description = kwargs.get('task_description', '')
        instruction_block = kwargs.get('instruction_block', '')
        return agent_prompts.SUPERVISOR_DELEGATION_TEMPLATE_LOCAL.format(
            task_description=task_description,
            instruction_block=instruction_block
        )

    def _get_memory_icebreaker_generation_prompt_local(self, **kwargs) -> str:
        memory_prompts = sys.modules.get('app.services.llm.memory_prompts')
        if memory_prompts is None:
            from . import memory_prompts
        icebreaker_text = kwargs.get('icebreaker_text', '')
        return memory_prompts.MEMORY_ICEBREAKER_GENERATION_PROMPT_LOCAL.format(icebreaker_text=icebreaker_text)

    def _get_conversation_summarizer_instruction_local(self, **kwargs) -> str:
        utility_prompts = sys.modules.get('app.services.llm.utility_prompts')
        if utility_prompts is None:
            from . import utility_prompts
        summary_max_tokens = kwargs.get('summary_max_tokens', 100)
        return utility_prompts.CONVERSATION_SUMMARIZER_INSTRUCTION_LOCAL.format(summary_max_tokens=summary_max_tokens)

    def _get_finance_capture_nova_intent_prompt(self, **kwargs) -> str:
        agent_prompts = sys.modules.get('app.services.llm.agent_prompts')
        if agent_prompts is None:
            from . import agent_prompts

        text = kwargs.get("text", "")
        allowed_kinds: tuple[str, ...] = kwargs.get("allowed_kinds", ("asset", "liability", "manual_tx"))
        plaid_expense_categories: tuple[str, ...] = kwargs.get("plaid_expense_categories", tuple())
        plaid_category_subcategories: str = kwargs.get("plaid_category_subcategories", "")
        vera_to_plaid_mapping: str = kwargs.get("vera_to_plaid_mapping", "")
        asset_categories: tuple[str, ...] = kwargs.get("asset_categories", tuple())
        liability_categories: tuple[str, ...] = kwargs.get("liability_categories", tuple())

        prompt = agent_prompts.build_finance_capture_nova_intent_prompt(
            text=text,
            allowed_kinds=allowed_kinds,
            plaid_expense_categories=plaid_expense_categories,
            plaid_category_subcategories=plaid_category_subcategories,
            vera_to_plaid_mapping=vera_to_plaid_mapping,
            asset_categories=asset_categories,
            liability_categories=liability_categories,
        )
        logger.info("[prompt_loader] finance_capture_nova_intent_prompt generated:\n%s", prompt)
        return prompt

    def _get_memory_merge_summaries_local(self, **kwargs) -> str:
        memory_prompts = sys.modules.get('app.services.llm.memory_prompts')
        if memory_prompts is None:
            from . import memory_prompts
        memory_type = kwargs.get('memory_type', 'semantic')
        category = kwargs.get('category', 'Mixed')
        summaries_text = kwargs.get('summaries_text', '')
        importances_text = kwargs.get('importances_text', '')
        return memory_prompts.MEMORY_MERGE_SUMMARIES_LOCAL.format(
            memory_type=memory_type,
            category=category,
            summaries_text=summaries_text,
            importances_text=importances_text
        )


    def _validate_prompt_format(self, text: str, name: str) -> None:
        """Validate prompt formatting rules."""
        if not isinstance(text, str):
            raise ValueError(f"Prompt '{name}' must be a string, got {type(text)}")

        if '\\u' in text or '\\U' in text:
            raise ValueError(f"Prompt '{name}' contains Unicode escape sequences")

        if '\t' in text:
            raise ValueError(f"Prompt '{name}' contains tabs")

        for i, line in enumerate(text.split('\n'), 1):
            if line.rstrip() != line and line.strip() != '':
                raise ValueError(f"Prompt '{name}' line {i} has trailing spaces: {repr(line)}")

        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('#') and not line.startswith('##'):
                raise ValueError(f"Prompt '{name}' header must start with '##', got: {line}")

        for line in lines:
            if line.strip().startswith('-') and not (line.strip().startswith('- ') or line.strip().startswith('---')):
                raise ValueError(f"Prompt '{name}' bullet must use '- ' or horizontal rule must use '---', got: {line.strip()}")


    def _load_default(self, name: str, **kwargs) -> str:
        """Load bundled default prompt (synchronous version)."""
        if name not in self._bundled_defaults:
            raise ValueError(f"No bundled default found for prompt '{name}'")

        default = self._bundled_defaults[name]
        if callable(default):
            result = default(**kwargs)
            # Check if result is a coroutine (async function was called)
            if hasattr(result, '__await__'):
                # Run the coroutine synchronously
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Loop is already running (e.g., in FastAPI context)
                        # Run in a new thread with its own event loop
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, result)
                            return future.result()
                    else:
                        return loop.run_until_complete(result)
                except RuntimeError as e:
                    if "no running event loop" in str(e).lower() or "no current event loop" in str(e).lower():
                        # Create new event loop if needed
                        return asyncio.run(result)
                    else:
                        raise
            if callable(result):
                return result()
            return result
        else:
            return default

    async def _load_default_async(self, name: str, **kwargs) -> str:
        """Load bundled default prompt (async version)."""
        if name not in self._bundled_defaults:
            raise ValueError(f"No bundled default found for prompt '{name}'")

        default = self._bundled_defaults[name]
        if callable(default):
            result = default(**kwargs)
            # Check if result is a coroutine
            if hasattr(result, '__await__'):
                return await result
            if callable(result):
                return result()
            return result
        else:
            return default

    def load(self, name: str, **kwargs) -> str:
        """Load a prompt by name from local bundled defaults.

        Args:
            name: The prompt name (e.g., 'supervisor_system_prompt')
            **kwargs: Additional arguments for callable prompts

        Returns:
            The prompt text as a string

        Raises:
            ValueError: If prompt cannot be loaded or fails validation

        """
        text = self._load_default(name, **kwargs)
        self._validate_prompt_format(text, name)
        return text

    async def load_async(self, name: str, **kwargs) -> str:
        """Async version of load() for coroutines.

        Args:
            name: The prompt name (e.g., 'supervisor_system_prompt')
            **kwargs: Additional arguments for callable prompts

        Returns:
            The prompt text as a string

        """
        text = await self._load_default_async(name, **kwargs)
        self._validate_prompt_format(text, name)
        return text

    def reload(self, verify_reload: bool = False) -> dict[str, str]:
        """Reload prompt modules from disk and re-register defaults.

        This method:
        1. Reloads all prompt modules (agent_prompts, memory_prompts, etc.) from disk
        2. Re-registers the default prompts with fresh module references
        3. Optionally verifies reload by testing a sample prompt
        4. Returns a list of reloaded modules

        Use this when TEST_MODE configuration changes or when prompt files are modified.

        Args:
            verify_reload: If True, will test load a prompt after reload to verify it works

        Returns:
            dict: Status with list of reloaded modules

        """
        reloaded_modules = []
        prompt_modules = [
            'app.services.llm.agent_prompts',
            'app.services.llm.memory_prompts',
            'app.services.llm.onboarding_prompts',
            'app.services.llm.utility_prompts',
        ]

        logger.info("=== STARTING PROMPT RELOAD ===")

        # Log current module IDs before reload
        for module_name in prompt_modules:
            if module_name in sys.modules:
                module = sys.modules[module_name]
                logger.info(f"BEFORE reload - {module_name}: id={id(module)}")

        for module_name in prompt_modules:
            if module_name in sys.modules:
                try:
                    old_id = id(sys.modules[module_name])
                    importlib.reload(sys.modules[module_name])
                    new_id = id(sys.modules[module_name])
                    reloaded_modules.append(module_name)
                    logger.info(f"✓ Reloaded {module_name}: old_id={old_id} → new_id={new_id}")
                except Exception as e:
                    logger.error(f"✗ Failed to reload {module_name}: {e}")

        # Re-register defaults with fresh module references
        logger.info("Re-registering prompt defaults...")
        self._register_defaults()
        logger.info("✓ Re-registered prompt defaults")

        result = {
            "status": "success",
            "reloaded_modules": reloaded_modules,
            "total_reloaded": len(reloaded_modules)
        }

        # Verification test
        if verify_reload:
            try:
                logger.info("=== VERIFYING RELOAD ===")
                test_prompt = self.load("goal_agent_system_prompt")
                logger.info(f"✓ Verification successful - loaded prompt length: {len(test_prompt)} chars")
                result["verification"] = "success"
                result["test_prompt_length"] = len(test_prompt)
            except Exception as e:
                logger.error(f"✗ Verification failed: {e}")
                result["verification"] = "failed"
                result["verification_error"] = str(e)

        logger.info("=== PROMPT RELOAD COMPLETE ===")
        return result


prompt_loader = PromptLoader()
