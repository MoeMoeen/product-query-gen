"""Evaluator service public API."""

from . import evaluate as _evaluate

evaluate_one = _evaluate.evaluate_one

__all__ = [
    "evaluate_one",
]
