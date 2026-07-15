"""Corpus configuration.

M2 needs only to read ``corpus.yaml`` for the set of known repo names (so the
validator can reject typo'd ``repo`` fields). The clone/checkout command that
materializes ``corpus/{name}/`` at the pinned SHA lands in M3 and will build on
:func:`load_corpus_config`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_SIZE_CLASSES = frozenset({"small", "medium", "large"})


@dataclass(frozen=True)
class RepoSpec:
    """One corpus repository, pinned by exact commit SHA."""

    name: str
    url: str
    sha: str
    language: str
    size_class: str


def load_corpus_config(path: Path) -> list[RepoSpec]:
    """Parse ``corpus.yaml`` into :class:`RepoSpec` entries.

    Raises ``ValueError`` if the file is structurally wrong; individual field
    constraints (valid SHAs, reachable URLs) are M3's concern.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "repos" not in data:
        raise ValueError(f"{path}: expected a mapping with a 'repos' key")
    repos = data["repos"]
    if not isinstance(repos, list):
        raise ValueError(f"{path}: 'repos' must be a list")

    specs: list[RepoSpec] = []
    for i, entry in enumerate(repos):
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: repos[{i}] must be a mapping")
        missing = {"name", "url", "sha", "language", "size_class"} - set(entry)
        if missing:
            raise ValueError(f"{path}: repos[{i}] missing keys: {sorted(missing)}")
        if entry["size_class"] not in _SIZE_CLASSES:
            raise ValueError(
                f"{path}: repos[{i}] size_class must be one of {sorted(_SIZE_CLASSES)}"
            )
        specs.append(
            RepoSpec(
                name=entry["name"],
                url=entry["url"],
                sha=entry["sha"],
                language=entry["language"],
                size_class=entry["size_class"],
            )
        )
    return specs


def known_repo_names(path: Path) -> frozenset[str]:
    """Return the set of repo names declared in ``corpus.yaml``."""
    return frozenset(spec.name for spec in load_corpus_config(path))
