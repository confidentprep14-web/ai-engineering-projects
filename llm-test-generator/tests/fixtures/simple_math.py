"""Simple math functions used as a fixture for test generation."""


def add(a: int, b: int) -> int:
    """Return the sum of a and b."""
    return a + b


def subtract(a: int, b: int) -> int:
    """Return a minus b."""
    return a - b


def divide(a: int, b: int) -> float:
    """Divide a by b. Raises ZeroDivisionError if b is 0."""
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b
