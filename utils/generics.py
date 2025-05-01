from re import Match, compile
from typing import Any

from aiocache import cached
from motor.motor_asyncio import AsyncIOMotorClient

from settings import MONGO_DB, MONGO_URI

TRAILING_DOTS_RE = compile(r"#\S+")


def mongo_client():
    client = AsyncIOMotorClient(MONGO_URI)
    return client.get_database(MONGO_DB)


def fix_hashtag_trailing_dots(text: str):

    def clean_trailing_dots(match: Match[str]):
        match_str = match.group()
        return match_str.rstrip(".") + (" ." if match_str.endswith(".") else "")

    return TRAILING_DOTS_RE.sub(clean_trailing_dots, text)


def recursive_fix(data):
    """Recursively apply fix_hashtag_trailing_dots to all strings in nested dictionaries and lists."""
    if isinstance(data, str):
        # If it's a string, apply the fix
        return fix_hashtag_trailing_dots(data)
    elif isinstance(data, dict):
        # If it's a dictionary, apply recursively to each value
        return {k: recursive_fix(v) for k, v in data.items()}
    elif isinstance(data, list):
        # If it's a list, apply recursively to each element
        return [recursive_fix(item) for item in data]
    else:
        # If it's neither a string, dictionary, nor list, return as is
        return data


def cleanup_dict(original: dict) -> dict:
    def is_empty(value):
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        if isinstance(value, (list, dict)) and not value:
            return True
        return False

    return {k: v for k, v in original.items() if not is_empty(v)}


@cached(ttl=300)
async def get_workflow_items() -> list[dict[str, Any]]:
    """
    Retrieve available Workflow Action items.

    Args:
        lang (Literal["en", "zh"], optional): Language of the Workflow Action items.
            Use "zh" for Traditional Chinese / Taiwanese. Defaults to "en" for other languages.

    Returns:
        list[dict[str, Any]]: List of available Workflow Action items.
    """

    filters = {"trigger": 0}
    projects = {
        "_id": 0,
        "categories": 0,
        "trigger": 0,
        "lang": 0,
        "logo": 0,
        "config.display_name": 0,
        "config.outputs": 0,
        "config.input_trigger": 0,
    }

    workflow_actions_collection = mongo_client().get_collection("ai_workflow_action")
    actions = await workflow_actions_collection.find(filters, projects).to_list(None)

    updated_actions: list[dict[str, Any]] = []
    for action in actions:
        action = cleanup_dict(action)
        action_code = action.get("action_code")
        if not action_code:
            continue

        action_name = action.pop("display_name", "")
        config: dict[str, Any] = action.pop("config", {})
        default_input = action.pop("inputs", {})
        input_fields = config.pop("fields", {})
        examples_raw = action.pop("examples", [])

        # Update the action dictionary with structured keys
        action.update(
            {
                "action_name": action_name,
                "default_input": default_input,
                "input_fields": input_fields,
                "placeholder_name": f"#{action_code}",
            }
        )

        if isinstance(examples_raw, dict):
            if "output" not in examples_raw:
                if "input" in examples_raw:
                    action["usage_examples"] = [examples_raw]
                else:
                    action["usage_examples"] = [{"input": examples_raw}]
            else:
                action["usage_examples"] = [examples_raw]
        elif isinstance(examples_raw, list):
            action["usage_examples"] = examples_raw

        updated_actions.append(cleanup_dict(action))

    return updated_actions
