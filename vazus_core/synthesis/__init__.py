"""Synthesis and evolutionary archive module."""

try:
    from vazus_core.synthesis.map_elites_archive import CodeCandidate, MapElitesArchive
except ImportError:
    CodeCandidate = None  # type: ignore
    MapElitesArchive = None  # type: ignore

__all__ = ["MapElitesArchive", "CodeCandidate"]
