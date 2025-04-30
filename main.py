import asyncio
from datetime import datetime, timezone
import re
from typing import Literal

import opencc
import requests
from bs4 import BeautifulSoup
from fastmcp import FastMCP
from motor.motor_asyncio import AsyncIOMotorClient
from validators.url import url as is_valid_url
from validators.utils import ValidationError as ValidatorsError

from settings import MONGO_DB, MONGO_URI
from utils.serper import GoogleSerperAPIWrapper

mcp = FastMCP("growise-mcp", host="0.0.0.0", port=6969)


def mongo_client():
    client = AsyncIOMotorClient(MONGO_URI)
    return client.get_database(MONGO_DB)


_CONVERTERS = opencc.OpenCC("s2tw.json")


@mcp.tool()
def normalize_traditional_chinese(chinese_text: str) -> str:
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
    return _CONVERTERS.convert(chinese_text)


@mcp.tool()
async def google_search(
    query_str: str,
    search_type: Literal["news", "search", "places", "images"] = "search",
    raw: bool = False,
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

    search = GoogleSerperAPIWrapper(type=search_type)
    results = await search.aresults(query_str)
    credits = results.get("credits")

    if not raw:
        parsed_results = search._parse_results(results)
        if parsed_results != "No good Google Search Result was found":
            return parsed_results, credits

    return results, credits


@mcp.tool()
def is_url_accessible(url: str):
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


@mcp.tool()
def validate_urls(url_list: list[str]) -> list[str]:
    """Validate URLs before returning them to the user.

    This function **must always be used** whenever a URL is present in the response or context,
    ensuring that all URLs are valid and accessible before being returned.

    Args:
        url_list (list[str]): A list of URLs to validate.

    Returns:
        list[str]: A list of validated URLs.
    """

    validated_urls: list[str] = []
    for url in url_list:
        try:
            if is_valid_url(url) and is_url_accessible(url):
                validated_urls.append(url)
        except ValidatorsError as e:
            print(f"Error validating URL {url}: {e}")

    return validated_urls


@mcp.tool()
def get_current_datetime():
    """Returns the current UTC date and time in ISO 8601 format.

    Returns:
        str: The current UTC date and time in ISO format (YYYY-MM-DDTHH:MM:SSZ).
    """
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
    selectors: list[str], html: str
) -> dict[str, bool] | str:
    soup = BeautifulSoup(html, "html5lib")
    escape_regex = re.compile(r"/\*.*?\*/")
    """
    Validate generated CSS selectors.

    Args:
        selectors (list[str]): List of CSS selectors to validate.

    Returns:
        dict[str, bool] | str: A dictionary mapping each selector to its validation results
        or an error message string if validation fails.
    """

    selectors = [escape_regex.sub("", selector).strip() for selector in selectors]

    try:
        tasks = [test_selector(selector, soup) for selector in selectors]
        results = await asyncio.gather(*tasks)
        return {k: v for k, v in zip(selectors, results)}
    except Exception as e:
        return f"Error during validation: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="sse")
