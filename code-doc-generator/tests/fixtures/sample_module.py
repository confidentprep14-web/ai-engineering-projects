"""Sample module used as a fixture for ast_parser and generator tests.

Contains a mix of public functions with type hints, a public function
without type hints, a private function (should be skipped), and a
function with container type hints (list[str], dict[str, int]).
"""


def connect(host: str, port: int = 5432) -> None:
    """Open a connection to the database."""
    pass


def _internal_helper():
    """This is private and must never appear in extracted output."""
    pass


def process(data: list[str]) -> dict[str, int]:
    """Count occurrences of each string in data."""
    counts: dict[str, int] = {}
    for item in data:
        counts[item] = counts.get(item, 0) + 1
    return counts


def untyped_function(a, b):
    return a + b


async def fetch_remote(url: str) -> str:
    """Fetch a remote resource asynchronously."""
    return url


@staticmethod
def decorated_example(value: int) -> int:
    return value * 2
