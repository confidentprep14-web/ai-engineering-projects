"""Tool registry and built-in tools: calculator, get_datetime, wikipedia_search.

Same implementation as the standalone tool-calling-agent project (p1-06):
the registry pattern means adding a new tool is one decorator, not a change
to the agent loop in main.py. call_tool() never raises — every failure mode
becomes a string the LLM can read and react to.
"""

import ast
import datetime
import operator
import os
import urllib.parse

import requests

TOOL_REGISTRY: dict[str, dict] = {}

WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
# Wikimedia rejects requests without a descriptive User-Agent (HTTP 403) per
# https://meta.wikimedia.org/wiki/User-Agent_policy
WIKIPEDIA_USER_AGENT = "ai-assistant-capstone/1.0 (https://github.com/; educational project)"
WIKIPEDIA_EXTRACT_MAX_CHARS = 500

_SUPPORTED_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_SUPPORTED_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def register_tool(name: str, description: str, parameters: dict):
    """Decorator that registers a function as a callable tool."""

    def decorator(func):
        TOOL_REGISTRY[name] = {
            "function": func,
            "description": description,
            "parameters": parameters,
        }
        return func

    return decorator


def get_tool_schemas() -> list[dict]:
    """Return tool definitions in OpenAI-compatible format."""
    return [
        {
            "name": tool_name,
            "description": tool_spec["description"],
            "parameters": tool_spec["parameters"],
        }
        for tool_name, tool_spec in TOOL_REGISTRY.items()
    ]


def call_tool(tool_name: str, arguments: dict) -> str:
    """Execute a registered tool and return its result as a string.

    Never raises. Unknown tools and tool-internal exceptions both become
    error strings, so the agent loop in main.py can keep going instead of
    crashing.
    """
    if tool_name not in TOOL_REGISTRY:
        return f"Error: tool '{tool_name}' does not exist. Available: {list(TOOL_REGISTRY.keys())}"
    try:
        return str(TOOL_REGISTRY[tool_name]["function"](**arguments))
    except Exception as tool_execution_error:
        return f"Tool error: {tool_execution_error}"


@register_tool(
    name="calculator",
    description="Evaluate an arithmetic expression. Supports +, -, *, /, ** (power), % (modulo), and parentheses.",
    parameters={
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    },
)
def calculator(expression: str) -> str:
    """Safely evaluate an arithmetic expression using an AST whitelist (no eval())."""
    try:
        parsed_expression = ast.parse(expression, mode="eval")
    except SyntaxError:
        return "Error: only arithmetic is allowed"

    try:
        result = _evaluate_arithmetic_node(parsed_expression.body)
    except _UnsafeExpressionError:
        return "Error: only arithmetic is allowed"
    except ZeroDivisionError:
        return "Error: division by zero"

    return str(result)


class _UnsafeExpressionError(Exception):
    """Raised when an expression node is outside the arithmetic whitelist."""


def _evaluate_arithmetic_node(node: ast.AST):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise _UnsafeExpressionError("only numeric literals are allowed")
    if isinstance(node, ast.BinOp) and type(node.op) in _SUPPORTED_BINARY_OPERATORS:
        left_value = _evaluate_arithmetic_node(node.left)
        right_value = _evaluate_arithmetic_node(node.right)
        return _SUPPORTED_BINARY_OPERATORS[type(node.op)](left_value, right_value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SUPPORTED_UNARY_OPERATORS:
        operand_value = _evaluate_arithmetic_node(node.operand)
        return _SUPPORTED_UNARY_OPERATORS[type(node.op)](operand_value)
    raise _UnsafeExpressionError(f"unsupported expression node: {type(node).__name__}")


@register_tool(
    name="get_datetime",
    description="Get the current UTC date and time.",
    parameters={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "IANA timezone name, e.g. UTC, America/New_York",
            }
        },
        "required": [],
    },
)
def get_datetime(timezone: str = "UTC", **unexpected_kwargs) -> str:
    """Return the current UTC time in ISO 8601 format.

    Unexpected kwargs (e.g. an LLM passing {"format": "ISO"}) are accepted
    and ignored rather than raising a TypeError that would crash the agent.
    """
    current_utc_time = datetime.datetime.now(datetime.timezone.utc)
    iso_timestamp = current_utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    if timezone and timezone.upper() != "UTC":
        return f"{iso_timestamp} (timezone conversion not implemented — returning UTC)"
    return iso_timestamp


@register_tool(
    name="wikipedia_search",
    description="Fetch a summary of a Wikipedia article by title.",
    parameters={
        "type": "object",
        "properties": {"title": {"type": "string"}},
        "required": ["title"],
    },
)
def wikipedia_search(title: str) -> str:
    """Fetch a Wikipedia article summary over HTTP. Never raises."""
    timeout_seconds = float(os.environ.get("WIKIPEDIA_TIMEOUT_SECONDS", 5))
    summary_url = WIKIPEDIA_SUMMARY_URL.format(title=urllib.parse.quote(title))

    try:
        wikipedia_response = requests.get(
            summary_url, timeout=timeout_seconds, headers={"User-Agent": WIKIPEDIA_USER_AGENT}
        )
    except requests.Timeout:
        return "Wikipedia request timed out"
    except requests.RequestException as request_error:
        return f"Wikipedia request failed: {request_error}"

    if wikipedia_response.status_code == 404:
        return f"No Wikipedia article found for '{title}'"
    if wikipedia_response.status_code != 200:
        return f"Wikipedia returned HTTP {wikipedia_response.status_code}"

    article_extract = wikipedia_response.json().get("extract", "")
    return article_extract[:WIKIPEDIA_EXTRACT_MAX_CHARS]
