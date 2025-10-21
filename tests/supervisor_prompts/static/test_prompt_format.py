"""Consolidated static tests for prompt quality and format validation."""

import ast
import json
import os
from pathlib import Path
from typing import Any, Dict, Set

import pytest

from app.services.llm.prompt_loader import prompt_loader


class PromptLiteralDetector(ast.NodeVisitor):
    """AST visitor to detect hardcoded prompt literals."""

    def __init__(self):
        self.violations = []
        self.allowed_modules = {
            "app/services/llm/prompt_loader.py",
            "app/services/llm/agent_prompts.py",
            "app/services/llm/memory_prompts.py",
            "app/services/llm/utility_prompts.py",
            "app/services/llm/onboarding_prompts.py",
        }
        self.allowed_symbols = {
            "SUPERVISOR_PROMPT",
            "WEALTH_AGENT_PROMPT",
            "GOAL_AGENT_PROMPT",
            "GOAL_AGENT_PROMPT_RAW",
        }

    def visit_Assign(self, node):
        """Check for triple-quoted string assignments."""
        if (len(node.targets) == 1 and
            isinstance(node.targets[0], ast.Name) and
            isinstance(node.value, ast.Constant) and
            isinstance(node.value.value, str)):

            target_name = node.targets[0].id
            if target_name in self.allowed_symbols:
                return

            if '\n' in node.value.value:
                prompt_keywords = {
                    'you are', 'your job', 'task:', 'output', 'return',
                    '## ', '### ', '- ', '🚨', '⚠️', '✅', '❌'
                }
                text_lower = node.value.value.lower()
                if any(keyword in text_lower for keyword in prompt_keywords):
                    self.violations.append({
                        'target': target_name,
                        'line': node.lineno,
                        'text_preview': node.value.value[:100] + '...' if len(node.value.value) > 100 else node.value.value
                    })

        elif (isinstance(node.value, ast.Call) and
              isinstance(node.value.func, ast.Attribute) and
              node.value.func.attr in {'invoke', 'invoke_model', 'chat'} and
              len(node.value.args) > 0 and
              isinstance(node.value.args[0], ast.Constant) and
              isinstance(node.value.args[0].value, str)):

            text = node.value.args[0].value
            if len(text) > 50:  # Only flag substantial strings
                self.violations.append({
                    'target': f"LLM call at line {node.lineno}",
                    'line': node.lineno,
                    'text_preview': text[:100] + '...' if len(text) > 100 else text
                })

        self.generic_visit(node)

    def visit_Call(self, node):
        """Check for direct LLM calls with string literals."""
        if (isinstance(node.func, ast.Attribute) and
            node.func.attr in {'invoke_model', 'invoke'} and
            len(node.args) >= 2):

            body_arg = node.args[1]
            if isinstance(body_arg, ast.Dict):
                for key, value in zip(body_arg.keys, body_arg.values, strict=False):
                    if (isinstance(key, ast.Constant) and key.value == "messages" and
                        isinstance(value, ast.List) and len(value.elts) > 0):
                        first_msg = value.elts[0]
                        if (isinstance(first_msg, ast.Dict) and
                            len(first_msg.keys) >= 2 and
                            len(first_msg.values) >= 2):
                            content_key = first_msg.keys[1] if len(first_msg.keys) > 1 else None
                            content_value = first_msg.values[1] if len(first_msg.values) > 1 else None
                            if (isinstance(content_key, ast.Constant) and content_key.value == "content" and
                                isinstance(content_value, ast.List) and len(content_value.elts) > 0):
                                first_content = content_value.elts[0]
                                if (isinstance(first_content, ast.Dict) and
                                    len(first_content.keys) >= 1 and
                                    len(first_content.values) >= 1):
                                    text_key = first_content.keys[0]
                                    text_value = first_content.values[0]
                                    if (isinstance(text_key, ast.Constant) and text_key.value == "text" and
                                        isinstance(text_value, ast.Constant) and
                                        isinstance(text_value.value, str) and
                                        len(text_value.value) > 50):
                                        self.violations.append({
                                            'target': f"Direct LLM messages call at line {node.lineno}",
                                            'line': node.lineno,
                                            'text_preview': text_value.value[:100] + '...' if len(text_value.value) > 100 else text_value.value
                                        })

        self.generic_visit(node)


def find_python_files() -> Set[Path]:
    """Find all Python files in the project."""
    project_root = Path(__file__).parent.parent.parent.parent
    python_files = set()

    skip_dirs = {
        '__pycache__',
        '.git',
        '.pytest_cache',
        'node_modules',
        'venv',
        '.venv',
        '.venv-evals',
        'env',
        '.env',
        'htmlcov',
        'coverage',
        'streamlit_supervisor_test',
    }

    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for file in files:
            if file.endswith('.py'):
                python_files.add(Path(root) / file)

    return python_files


def _build_prompt_params(prompt_spec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        param["name"]: param["default"]
        for param in prompt_spec.get("parameters", [])
        if "default" in param
    }


@pytest.mark.prompt_static
def test_all_prompts_load_successfully():
    """Test that all prompts in the inventory can be loaded."""
    inventory_path = Path(__file__).parent.parent / "prompt_specs.json"

    with open(inventory_path, 'r', encoding='utf-8') as f:
        inventory = json.load(f)

        failed_loads = []
        for prompt_spec in inventory:
            prompt_name = prompt_spec["name"]
            try:
                text = prompt_loader.load(prompt_name, **_build_prompt_params(prompt_spec))
                assert isinstance(text, str)
                assert len(text.strip()) > 0
            except Exception as e:
                print(f"DEBUG: Actual exception for {prompt_name}: {repr(str(e))}")
                failed_loads.append(f"{prompt_name}: {e}")

    if failed_loads:
        pytest.fail(f"Failed to load {len(failed_loads)} prompts:\n" + "\n".join(failed_loads))


@pytest.mark.prompt_static
def test_prompt_utf8_valid():
    """Test that all prompts contain valid UTF-8 characters."""
    inventory_path = Path(__file__).parent.parent / "prompt_specs.json"

    with open(inventory_path, 'r', encoding='utf-8') as f:
        inventory = json.load(f)

    violations = []
    for prompt_spec in inventory:
        prompt_name = prompt_spec["name"]
        try:
            text = prompt_loader.load(prompt_name, **_build_prompt_params(prompt_spec))
            try:
                text.encode('utf-8')
            except UnicodeEncodeError as e:
                violations.append(f"{prompt_name}: Invalid UTF-8 character at position {e.start}: {repr(text[e.start:e.end])}")
        except Exception as e:
            violations.append(f"{prompt_name}: Failed to load - {e}")

    if violations:
        pytest.fail("UTF-8 violations found:\n" + "\n".join(violations))


@pytest.mark.prompt_static
def test_prompt_no_unicode_escapes():
    """Test that prompts contain no Unicode escape sequences."""
    inventory_path = Path(__file__).parent.parent / "prompt_specs.json"

    with open(inventory_path, 'r', encoding='utf-8') as f:
        inventory = json.load(f)

    violations = []
    for prompt_spec in inventory:
        prompt_name = prompt_spec["name"]
        try:
            text = prompt_loader.load(prompt_name, **_build_prompt_params(prompt_spec))
            if '\\u' in text or '\\U' in text:
                lines = text.split('\n')
                for i, line in enumerate(lines, 1):
                    if '\\u' in line or '\\U' in line:
                        violations.append(f"{prompt_name} line {i}: {line.strip()}")
                        break
        except Exception as e:
            violations.append(f"{prompt_name}: Failed to load - {e}")

    if violations:
        pytest.fail("Unicode escape sequences found:\n" + "\n".join(violations))


@pytest.mark.prompt_static
def test_prompt_no_tabs():
    """Test that prompts contain no tab characters."""
    inventory_path = Path(__file__).parent.parent / "prompt_specs.json"

    with open(inventory_path, 'r', encoding='utf-8') as f:
        inventory = json.load(f)

    violations = []
    for prompt_spec in inventory:
        prompt_name = prompt_spec["name"]
        try:
            text = prompt_loader.load(prompt_name, **_build_prompt_params(prompt_spec))
            if '\t' in text:
                lines = text.split('\n')
                for i, line in enumerate(lines, 1):
                    if '\t' in line:
                        violations.append(f"{prompt_name} line {i}: {repr(line)}")
        except Exception as e:
            violations.append(f"{prompt_name}: Failed to load - {e}")

    if violations:
        pytest.fail("Tab characters found:\n" + "\n".join(violations))


@pytest.mark.prompt_static
def test_prompt_no_trailing_spaces():
    """Test that prompts have no trailing spaces on any line."""
    inventory_path = Path(__file__).parent.parent / "prompt_specs.json"

    with open(inventory_path, 'r', encoding='utf-8') as f:
        inventory = json.load(f)

    violations = []
    for prompt_spec in inventory:
        prompt_name = prompt_spec["name"]
        try:
            text = prompt_loader.load(prompt_name, **_build_prompt_params(prompt_spec))
            lines = text.split('\n')
            for i, line in enumerate(lines, 1):
                if line.rstrip() != line and line.strip() != '':
                    violations.append(f"{prompt_name} line {i}: trailing spaces")
        except Exception as e:
            violations.append(f"{prompt_name}: Failed to load - {e}")

    if violations:
        pytest.fail("Trailing spaces found:\n" + "\n".join(violations))


@pytest.mark.prompt_static
def test_prompt_headers_format():
    """Test that headers start with '##'."""
    inventory_path = Path(__file__).parent.parent / "prompt_specs.json"

    with open(inventory_path, 'r', encoding='utf-8') as f:
        inventory = json.load(f)

    violations = []
    for prompt_spec in inventory:
        prompt_name = prompt_spec["name"]
        try:
            text = prompt_loader.load(prompt_name, **_build_prompt_params(prompt_spec))
            lines = text.split('\n')
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith('#') and not stripped.startswith('##'):
                    violations.append(f"{prompt_name} line {i}: {stripped} (headers must start with '##')")
        except Exception as e:
            violations.append(f"{prompt_name}: Failed to load - {e}")

    if violations:
        pytest.fail("Header format violations:\n" + "\n".join(violations))


@pytest.mark.prompt_static
def test_prompt_bullets_format():
    """Test that bullets use '- ' format."""
    inventory_path = Path(__file__).parent.parent / "prompt_specs.json"

    with open(inventory_path, 'r', encoding='utf-8') as f:
        inventory = json.load(f)

    violations = []
    for prompt_spec in inventory:
        prompt_name = prompt_spec["name"]
        try:
            text = prompt_loader.load(prompt_name, **_build_prompt_params(prompt_spec))
            lines = text.split('\n')
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith('-') and not (stripped.startswith('- ') or stripped.startswith('---')):
                    violations.append(f"{prompt_name} line {i}: {stripped} (bullets must use '- ' or horizontal rules must use '---')")
        except Exception as e:
            violations.append(f"{prompt_name}: Failed to load - {e}")

    if violations:
        pytest.fail("Bullet format violations:\n" + "\n".join(violations))


@pytest.mark.prompt_static
def test_prompt_no_emojis():
    """Test that prompts contain no emoji characters."""
    inventory_path = Path(__file__).parent.parent / "prompt_specs.json"

    with open(inventory_path, 'r', encoding='utf-8') as f:
        inventory = json.load(f)

    violations = []
    for prompt_spec in inventory:
        prompt_name = prompt_spec["name"]
        try:
            text = prompt_loader.load(prompt_name, **_build_prompt_params(prompt_spec))
            # Check for emoji characters (basic check for common emoji ranges)
            emoji_ranges = [
                (0x1F600, 0x1F64F),  # Emoticons
                (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
                (0x1F680, 0x1F6FF),  # Transport and Map
                (0x1F1E0, 0x1F1FF),  # Flags
                (0x2600, 0x26FF),    # Misc symbols
                (0x2700, 0x27BF),    # Dingbats
            ]

            for char in text:
                code = ord(char)
                for start, end in emoji_ranges:
                    if start <= code <= end:
                        violations.append(f"{prompt_name}: contains emoji '{char}' (U+{code:04X})")
                        break
        except Exception as e:
            violations.append(f"{prompt_name}: Failed to load - {e}")

    if violations:
        pytest.fail("Emoji characters found in prompts (prompts should not contain emojis):\n" + "\n".join(violations))


@pytest.mark.prompt_static
def test_no_hardcoded_prompt_literals():
    """Test that no hardcoded prompt literals exist outside the loader."""
    detector = PromptLiteralDetector()
    python_files = find_python_files()

    for file_path in python_files:
        relative_path = file_path.relative_to(Path(__file__).parent.parent.parent.parent)
        normalized_path = str(relative_path).replace('\\', '/')
        if normalized_path in detector.allowed_modules or 'test' in str(relative_path):
            continue

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source, filename=str(file_path))
            detector.visit(tree)

        except SyntaxError:
            continue
        except Exception as e:
            pytest.fail(f"Error parsing {file_path}: {e}")

    if detector.violations:
        violation_messages = []
        for violation in detector.violations:
            violation_messages.append(
                f"{violation['target']} at {violation['line']}: {violation['text_preview']}"
            )

        pytest.fail(
            f"Found {len(detector.violations)} hardcoded prompt literals:\n" +
            "\n".join(violation_messages) +
            "\n\nAll prompts must be loaded via prompt_loader.load() instead of hardcoded literals."
        )
