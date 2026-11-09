"""Presentation rules shared by every page (SPEC §2)."""

from __future__ import annotations

import unicodedata


def humanize(token: str) -> str:
    """`jane_doe` → `Jane Doe`. Raw values remain the identifiers everywhere else."""
    words = token.replace("_", " ").split()
    if not words:
        return token
    return " ".join(word[:1].upper() + word[1:] for word in words)


def display_title(title: str, filename: str) -> str:
    trimmed = title.strip()
    return humanize(trimmed) if trimmed else filename


def join_list(items: list[str]) -> str:
    """"A", "A and B", "A, B and C" — English list formatting, as the other apps produce."""
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def credits(studio: str, actors: list[str]) -> str:
    parts = [humanize(studio), join_list([humanize(a) for a in actors])]
    return " · ".join(part for part in parts if part)


def fold(text: str) -> str:
    """Case- and diacritic-insensitive comparison form."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def sort_key(display: str, filename: str) -> tuple[str, str, str]:
    return (fold(display), fold(filename), filename)
