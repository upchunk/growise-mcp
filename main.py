import asyncio
import json
import re
import traceback
from datetime import datetime, timezone
from typing import Literal

import opencc
import requests
from bs4 import BeautifulSoup
from fastmcp import FastMCP, Context
from validators.url import url as is_valid_url
from validators.utils import ValidationError as ValidatorsError

from utils.generics import get_workflow_items, mongo_client, recursive_fix
from utils.serper import GoogleSerperAPIWrapper

mcp = FastMCP("growise-mcp", host="0.0.0.0", port=6969)


_CONVERTERS = opencc.OpenCC("s2tw.json")


@mcp.tool()
def normalize_traditional_chinese(chinese_text: str, ctx: Context, **kwargs) -> str:
    """
    Normalize Chinese text to Taiwan Standard Traditional Chinese.

    Use this function after generating or translating Chinese text to ensure the output
    adheres to Taiwan Standard Traditional Chinese.

    Important:
        - Only call this tool if your answer is already in Chinese.
        - If the answer doesn't include Chinese characters, do not use this tool.

    Args:
        chinese_text (str): The text to normalize.

    Returns:
        str: Text normalized to Taiwan Standard Traditional Chinese.
    """

    print(ctx.model_dump())
    print(kwargs)
    del kwargs

    return _CONVERTERS.convert(chinese_text)


@mcp.tool()
async def google_search(
    query_str: str,
    search_type: Literal["news", "search", "places", "images"] = "search",
    raw: bool = False,
    ctx: Context = None,
    **kwargs,
) -> tuple[dict | str, int]:
    """
    Perform an asynchronous Google search using the provided query string and search type
    to obtain relevant and up-to-date search results.

    Args:
        query_str (str): The search query to execute.
        search_type (Literal["news", "search", "places", "images"], optional): Information to search. Defaults to "search".
        raw (bool, optional): If True, return the raw search results (default is False).

    Returns:
        tuple[dict | str, int] : A dictionary or string containing the search results and the credits usage
    """

    print(ctx.model_dump())
    print(kwargs)

    search = GoogleSerperAPIWrapper(type=search_type, **kwargs)
    results = await search.aresults(query_str)
    credits = results.get("credits")

    if not raw:
        parsed_results = search._parse_results(results)
        if parsed_results != "No good Google Search Result was found":
            return parsed_results, credits

    return results, credits


def is_url_accessible(url: str):
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


@mcp.tool()
def validate_urls(url_list: list[str], ctx: Context, **kwargs) -> list[str]:
    """Validate URLs before returning them to the user.

    This function **must always be used** whenever a URL is present in the response or context,
    ensuring that all URLs are valid and accessible before being returned.

    Args:
        url_list (list[str]): A list of URLs to validate.

    Returns:
        list[str]: A list of validated URLs.
    """
    print(ctx.model_dump())
    print(kwargs)
    del kwargs

    validated_urls: list[str] = []
    for url in url_list:
        try:
            if is_valid_url(url) and is_url_accessible(url):
                validated_urls.append(url)
        except ValidatorsError as e:
            print(f"Error validating URL {url}: {e}")

    return validated_urls


@mcp.tool()
def get_current_datetime(ctx: Context, **kwargs):
    """Returns the current UTC date and time in ISO 8601 format.

    Returns:
        str: The current UTC date and time in ISO format (YYYY-MM-DDTHH:MM:SSZ).
    """
    print(ctx.model_dump())
    print(kwargs)
    del kwargs

    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


NON_STANDARD_PSEUDO_CLASSES = [
    ":contains",  # Not standard CSS
    ":has",  # Partial/experimental support
    ":matches",  # Deprecated in favor of :is()
    # ":not()",  # :not() is standard but with limitations; adjust if needed
    # ":nth-last-child",  # Supported, but can exclude if targeting CSS2.1 only
    # ":nth-last-of-type",  # Supported mostly, adjust if targeting CSS2.1
    # Add any other custom or non-standard pseudo-classes you want to exclude
]


async def test_selector(selector: str, soup: BeautifulSoup):
    try:
        if any(pseudo in selector.lower() for pseudo in NON_STANDARD_PSEUDO_CLASSES):
            return False
        soup.select(selector)
        return True
    except Exception:
        return False


@mcp.tool()
async def validate_css_selectors(
    selectors: list[str], html: str, ctx: Context, **kwargs
) -> dict[str, bool] | str:
    """
    Validate generated CSS selectors.

    Args:
        selectors (list[str]): List of CSS selectors to validate.

    Returns:
        dict[str, bool] | str: A dictionary mapping each selector to its validation results
        or an error message string if validation fails.
    """

    print(ctx.model_dump())
    print(kwargs)
    del kwargs
    soup = BeautifulSoup(html, "html5lib")
    escape_regex = re.compile(r"/\*.*?\*/")

    selectors = [escape_regex.sub("", selector).strip() for selector in selectors]

    try:
        tasks = [test_selector(selector, soup) for selector in selectors]
        results = await asyncio.gather(*tasks)
        return {k: v for k, v in zip(selectors, results)}
    except Exception as e:
        return f"Error during validation: {str(e)}"


@mcp.tool()
async def workflow_saver(
    workflow_title: str,
    comment: str,
    workflow_inputs: list[dict] = None,
    workflow_actions: list[dict] = None,
    workflow_id: str = None,
    group_id: str = None,
    user_id: str = None,
    ctx: Context = None,
    **kwargs,
) -> str:
    """
    Asynchronously validates and saves (or updates) a workflow in the database.

    Args:
        workflow_title (str): The title of the workflow.
        comment (str): A summary of the changes.
        workflow_inputs (list[dict]): Pre-validated workflow inputs.
        workflow_actions (list[dict]): Pre-validated workflow actions.
        workflow_id (str): The ID of the workflow to save or update.
        group_id (str): The ID of the group associated with the workflow.
        user_id (str): The ID of the user associated with the workflow.

    Returns:
        str: A status message indicating whether the workflow was saved, updated, or remained unchanged.
            If saving fails, an error message is returned.
    """

    print(ctx.model_dump())
    print(kwargs)
    del kwargs

    # Validate input identifiers
    if not all(
        isinstance(v, str) and v.strip() for v in [workflow_id, group_id, user_id]
    ):
        raise ValueError(
            "workflow_id, group_id, and user_id must be non-empty strings."
        )

    # Predefine Mongo filter
    mongo_filter = {
        "workflow_id": workflow_id,
        "group_id": group_id,
        "user_id": user_id,
    }

    # Input validation - early returns for invalid inputs
    if not isinstance(workflow_actions, list) or not workflow_actions:
        return "Error: workflow_actions must be a non-empty list."
    if not isinstance(workflow_inputs, list) or not workflow_inputs:
        return "Error: workflow_inputs must be a non-empty list."
    if not isinstance(workflow_title, str) or not workflow_title.strip():
        return "Error: workflow_title must be a non-empty string."
    if not isinstance(comment, str) or not comment.strip():
        return "Error: comment must be a non-empty string."

    try:
        # Fetch available action definitions
        action_items = await get_workflow_items()
        available_action_map = {item["action_code"]: item for item in action_items}

        action_map = {}

        # Validate and clean workflow actions
        for action in workflow_actions:
            action_code = action.get("action_code")
            if not action_code:
                return "Error: Missing action_code in workflow_actions."

            # Match action_code with available actions
            matching_actions = [
                v for k, v in available_action_map.items() if action_code.startswith(k)
            ]

            if not matching_actions:
                return f"Error: Invalid or unavailable action_code '{action_code}'."

            ref_action = matching_actions[-1]  # Use the closest matching action
            ref_action_inputs = ref_action.get("input_fields", {})

            # Validate required inputs
            action_input = action.get("input", {})
            missing_inputs = [
                k
                for k, v in ref_action_inputs.items()
                if v.get("required") and k not in action_input
            ]

            if missing_inputs:
                return f"Error: Missing required inputs {str(missing_inputs)} for action '{action_code}'."

            # Clean action inputs
            action["input"] = {k: recursive_fix(v) for k, v in action_input.items()}

            # Store validated actions
            action_map[action_code] = action

        # Validate workflow inputs
        validated_inputs = []
        for input_item in workflow_inputs:
            action_code = input_item.get("action_code")
            input_name = input_item.get("name")
            if not action_code or not input_name:
                return "Error: Missing 'action_code' or 'name' in workflow_inputs."

            action = action_map.get(action_code)
            if not action:
                available_actions = ", ".join(action_map.keys())
                return (
                    f"Error: Invalid 'workflow_actions' action_code for '#{input_name}' input. "
                    f"Available actions [{available_actions}]"
                )

            # Validate input references
            if f"#{input_name}" not in action["input"].values():
                return (
                    f"Error: `#{input_name}` placeholder are not in {action_code} action input.\n"
                    f"Current {action_code} action Input:\n{json.dumps(action["input"], ensure_ascii=False, indent=2)}"
                )

            input_item.setdefault("type", "string")
            validated_inputs.append(input_item)

        # Get current timestamp
        timestamp = datetime.now(tz=timezone.utc).isoformat()

        # Fetch existing workflow data
        raw_workflow_collection = mongo_client().get_collection("raw_workflow_actions")
        prev_data = (
            await raw_workflow_collection.find_one(
                mongo_filter,
                projection={
                    "workflow_inputs": 1,
                    "workflow_actions": 1,
                    "history": 1,
                },
            )
            or {}
        )

        prev_inputs, prev_actions = prev_data.get("workflow_inputs", []), prev_data.get(
            "workflow_actions", []
        )
        actions_to_save = list(action_map.values())

        # Skip update if no changes detected
        if prev_inputs == validated_inputs and prev_actions == actions_to_save:
            return f"No changes detected for workflow '{workflow_id}'."

        # Update history (limit to 100 entries)
        history = prev_data.get("history", [])
        history.append({"timestamp": timestamp, "summary": comment})
        history = history[-100:]

        # Prepare workflow document
        workflow_to_save = {
            "workflow_title": workflow_title.strip(),
            "workflow_inputs": validated_inputs,
            "workflow_actions": actions_to_save,
            "timestamp": timestamp,
            "history": history,
            **mongo_filter,
        }

        # Save workflow
        raw_workflow_collection = mongo_client().get_collection("raw_workflow_actions")
        update_result = await raw_workflow_collection.update_one(
            mongo_filter, {"$set": workflow_to_save}, upsert=True
        )

        if update_result.modified_count > 0 or update_result.upserted_id:
            return f"Workflow '{workflow_id}' saved successfully."

        return f"No changes were made to workflow '{workflow_id}'."

    except asyncio.CancelledError:
        raise  # Allow task cancellation to propagate

    except Exception as e:
        return f"Error: Failed to save workflow '{workflow_id}'. {str(e)}\n{traceback.format_exc()}"


@mcp.tool()
async def workflow_loader(
    workflow_id: str = None,
    group_id: str = None,
    user_id: str = None,
    ctx: Context = None,
    **kwargs,
) -> dict | None:
    """
    Asynchronously checks and loads an existing workflow from the database.

    Args:
        workflow_id (str): The ID of the workflow to save or update.
        group_id (str): The ID of the group associated with the workflow.
        user_id (str): The ID of the user associated with the workflow.

    Returns:
        dict | None: The workflow details if found; otherwise, None.
    """

    print(ctx.model_dump())
    print(kwargs)
    del kwargs
    # Retrieve workflow actions from the database if not provided
    if workflow_id:
        raw_workflow_collection = mongo_client().get_collection("raw_workflow_actions")
        workflow: dict = await raw_workflow_collection.find_one(
            {
                "workflow_id": workflow_id,
                "group_id": group_id,
                "user_id": user_id,
            }
        )
        if workflow:
            workflow.pop("_id")
            return workflow


if __name__ == "__main__":
    mcp.run(transport="sse")
