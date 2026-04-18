"""Shared shingling utilities used by the indexer and plagiarism engine."""

from __future__ import annotations


def make_shingles(text: str, n: int) -> list[str]:
    """Return word-level n-gram shingles from *text*.

    Words are lowercased and split on whitespace.  If there are fewer
    than *n* words, a single shingle of all words is returned (or an
    empty list for empty text).
    """
    words = text.lower().split()
    if len(words) < n:
        return [" ".join(words)] if words else []
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]
