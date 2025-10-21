"""Prompt loader service for centralized prompt management.

Provides a unified interface to load prompts from bundled defaults.
Enforces ASCII formatting rules and prevents hardcoded prompt literals.
"""



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
        })


    def _get_supervisor_prompt_local(self) -> str:
        from .agent_prompts import SUPERVISOR_SYSTEM_PROMPT_LOCAL
        return SUPERVISOR_SYSTEM_PROMPT_LOCAL.strip()

    def _get_wealth_agent_constant_prompt_local(self) -> str:
        from .agent_prompts import build_wealth_system_prompt_local
        return build_wealth_system_prompt_local()

    def _get_goal_agent_prompt_local(self) -> str:
        from .agent_prompts import build_goal_agent_system_prompt_local
        return build_goal_agent_system_prompt_local()

    def _get_finance_agent_prompt_local(self, **kwargs) -> str:
        from .agent_prompts import build_finance_system_prompt_local
        return build_finance_system_prompt_local(**kwargs)

    def _get_wealth_agent_system_prompt_local(self, **kwargs) -> str:
        from .agent_prompts import build_wealth_system_prompt_local
        return build_wealth_system_prompt_local(**kwargs)

    def _get_onboarding_name_extraction_local(self) -> str:
        from .onboarding_prompts import ONBOARDING_NAME_EXTRACTION_LOCAL
        return ONBOARDING_NAME_EXTRACTION_LOCAL.strip()

    def _get_onboarding_location_extraction_local(self) -> str:
        from .onboarding_prompts import ONBOARDING_LOCATION_EXTRACTION_LOCAL
        return ONBOARDING_LOCATION_EXTRACTION_LOCAL.strip()

    def _get_memory_hotpath_trigger_classifier_local(self, **kwargs) -> str:
        from .memory_prompts import MEMORY_HOTPATH_TRIGGER_CLASSIFIER_LOCAL
        return MEMORY_HOTPATH_TRIGGER_CLASSIFIER_LOCAL.format(**kwargs).strip()

    def _get_memory_same_fact_classifier_local(self, **kwargs) -> str:
        from .memory_prompts import MEMORY_SAME_FACT_CLASSIFIER_LOCAL
        return MEMORY_SAME_FACT_CLASSIFIER_LOCAL.strip()

    def _get_memory_compose_summaries_local(self, **kwargs) -> str:
        from .memory_prompts import MEMORY_COMPOSE_SUMMARIES_LOCAL
        return MEMORY_COMPOSE_SUMMARIES_LOCAL.strip()

    def _get_episodic_memory_summarizer_local(self, **kwargs) -> str:
        from .memory_prompts import MEMORY_EPISODIC_SUMMARIZER_LOCAL
        return MEMORY_EPISODIC_SUMMARIZER_LOCAL.strip()

    def _get_profile_sync_extractor_local(self, **kwargs) -> str:
        from .memory_prompts import MEMORY_PROFILE_SYNC_EXTRACTOR_LOCAL
        return MEMORY_PROFILE_SYNC_EXTRACTOR_LOCAL.strip()

    def _get_guest_system_prompt_local(self, **kwargs) -> str:
        from .agent_prompts import build_guest_system_prompt_local
        max_messages = kwargs.get('max_messages', 5)
        return build_guest_system_prompt_local(max_messages)

    def _get_title_generator_system_prompt_local(self) -> str:
        from .utility_prompts import TITLE_GENERATOR_SYSTEM_PROMPT_LOCAL
        return TITLE_GENERATOR_SYSTEM_PROMPT_LOCAL.strip()

    def _get_conversation_summarizer_system_prompt_local(self) -> str:
        from .utility_prompts import CONVERSATION_SUMMARIZER_SYSTEM_PROMPT_LOCAL
        return CONVERSATION_SUMMARIZER_SYSTEM_PROMPT_LOCAL

    def _get_welcome_generator_system_prompt_local(self) -> str:
        from .utility_prompts import WELCOME_GENERATOR_SYSTEM_PROMPT_LOCAL
        return WELCOME_GENERATOR_SYSTEM_PROMPT_LOCAL

    def _get_title_generator_user_prompt_template_local(self, **kwargs) -> str:
        from .utility_prompts import TITLE_GENERATOR_USER_PROMPT_TEMPLATE_LOCAL
        body = kwargs.get('body', '')
        return TITLE_GENERATOR_USER_PROMPT_TEMPLATE_LOCAL.format(body=body)

    def _get_supervisor_delegation_template_local(self, **kwargs) -> str:
        from .agent_prompts import SUPERVISOR_DELEGATION_TEMPLATE_LOCAL
        task_description = kwargs.get('task_description', '')
        instruction_block = kwargs.get('instruction_block', '')
        return SUPERVISOR_DELEGATION_TEMPLATE_LOCAL.format(
            task_description=task_description,
            instruction_block=instruction_block
        )

    def _get_memory_icebreaker_generation_prompt_local(self, **kwargs) -> str:
        from .memory_prompts import MEMORY_ICEBREAKER_GENERATION_PROMPT_LOCAL
        icebreaker_text = kwargs.get('icebreaker_text', '')
        return MEMORY_ICEBREAKER_GENERATION_PROMPT_LOCAL.format(icebreaker_text=icebreaker_text)

    def _get_conversation_summarizer_instruction_local(self, **kwargs) -> str:
        from .utility_prompts import CONVERSATION_SUMMARIZER_INSTRUCTION_LOCAL
        summary_max_tokens = kwargs.get('summary_max_tokens', 100)
        return CONVERSATION_SUMMARIZER_INSTRUCTION_LOCAL.format(summary_max_tokens=summary_max_tokens)


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
        """Load bundled default prompt."""
        if name not in self._bundled_defaults:
            raise ValueError(f"No bundled default found for prompt '{name}'")

        default = self._bundled_defaults[name]
        if callable(default):
            result = default(**kwargs)
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
        """Async version of load() for consistency (currently synchronous)."""
        return self.load(name, **kwargs)


prompt_loader = PromptLoader()
