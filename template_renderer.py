import re
from html import escape
from typing import Any, Dict, Iterable, List


VARIABLE_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


def normalize_variable_key(value: str) -> str:
    """Convert CSV headings into stable template variable names."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(value).strip().lower())
    return normalized.strip("_")


def build_recipient_context(recipient: Dict[str, Any]) -> Dict[str, str]:
    context = {
        normalize_variable_key(key): "" if value is None else str(value)
        for key, value in recipient.items()
        if normalize_variable_key(key)
    }

    full_name = context.get("name") or context.get("full_name") or ""
    name_parts = full_name.split(maxsplit=1)
    context.setdefault("full_name", full_name)
    context.setdefault("first_name", name_parts[0] if name_parts else "")
    context.setdefault("last_name", name_parts[1] if len(name_parts) > 1 else "")
    context.setdefault("email", context.get("emails", ""))
    return context


def render_template_text(template: str, context: Dict[str, str]) -> str:
    """Render supported placeholders, leaving unknown placeholders visible."""

    def replace(match: re.Match) -> str:
        key = match.group(1)
        return context.get(key, match.group(0))

    return VARIABLE_PATTERN.sub(replace, template or "")


def render_message_html(template: str, context: Dict[str, str]) -> str:
    rendered = render_template_text(template, context)
    return escape(rendered).replace("\n", "<br>")


def discover_template_variables(recipients: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    keys = {"first_name", "last_name", "full_name", "email"}
    for recipient in recipients:
        keys.update(
            normalize_variable_key(key)
            for key in recipient.keys()
            if normalize_variable_key(key)
        )

    preferred_order = ["first_name", "last_name", "full_name", "email"]
    ordered_keys = preferred_order + sorted(keys.difference(preferred_order))
    return [
        {
            "key": key,
            "label": key.replace("_", " ").title(),
            "token": "{{" + key + "}}",
        }
        for key in ordered_keys
    ]
