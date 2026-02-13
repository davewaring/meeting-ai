"""Library context loading — agendas, pulse, project docs for monitor prompts."""

import re
from pathlib import Path


# Core files always loaded (relative to LIBRARY_PATH)
CORE_FILES = [
    "agendas/dave-j.md",
    "agendas/nav.md",
    "pulse/pulse.md",
    "AGENT.md",
]

# Project entry points (AGENT.md inside each project folder)
PROJECT_DIRS = [
    "braindrive-code",
    "braindrive-hardware",
    "braindrive-plus-one",
    "community-engagement",
]


def load_core_context(library_path: str) -> str:
    """Load core Library files into a single context string.

    Reads agendas, pulse, and top-level AGENT.md. Skips missing files silently.
    """
    root = Path(library_path)
    sections = []
    for rel_path in CORE_FILES:
        full = root / rel_path
        if full.exists():
            content = full.read_text(encoding="utf-8", errors="replace")
            sections.append(f"--- {rel_path} ---\n{content}")
    return "\n\n".join(sections)


def detect_projects(transcript: str) -> list[str]:
    """Detect which BrainDrive projects are mentioned in the transcript.

    Scans for project keywords and returns matching project directory names.
    """
    keywords = {
        "braindrive-code": ["braindrive code", "braindrive-code", "plugin", "crypto dashboard", "node_modules"],
        "braindrive-hardware": ["hardware", "braindrive-hardware", "watch", "wearable"],
        "braindrive-plus-one": ["plus one", "+1", "plus-one", "braindrive-plus-one", "meeting ai"],
        "community-engagement": ["community", "forum", "community-engagement", "discourse"],
    }
    lower = transcript.lower()
    found = []
    for project, terms in keywords.items():
        if any(term in lower for term in terms):
            found.append(project)
    return found


def load_project_context(library_path: str, project_names: list[str]) -> str:
    """Load AGENT.md for detected projects.

    Args:
        library_path: Root of the BrainDrive Library.
        project_names: List of project directory names to load.
    """
    root = Path(library_path)
    sections = []
    for name in project_names:
        agent_file = root / name / "AGENT.md"
        if agent_file.exists():
            content = agent_file.read_text(encoding="utf-8", errors="replace")
            # Truncate to first 3000 chars to keep prompt manageable
            if len(content) > 3000:
                content = content[:3000] + "\n... [truncated]"
            sections.append(f"--- {name}/AGENT.md ---\n{content}")
    return "\n\n".join(sections)


def build_full_context(library_path: str, transcript: str) -> str:
    """Build complete Library context: core files + detected project files."""
    core = load_core_context(library_path)
    projects = detect_projects(transcript)
    project_ctx = load_project_context(library_path, projects)

    parts = []
    if core:
        parts.append(core)
    if project_ctx:
        parts.append(project_ctx)
    return "\n\n".join(parts)
