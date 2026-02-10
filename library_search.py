"""Library search using ripgrep subprocess."""

import subprocess
import shutil
from pathlib import Path
from config import LIBRARY_PATH

MAX_RESULTS = 10
CONTEXT_LINES = 2


def search_library(query: str, library_path: str | None = None, max_results: int = MAX_RESULTS) -> list[dict]:
    """Search the BrainDrive Library for content matching the query.

    Returns a list of dicts with 'file' and 'snippet' keys, capped at max_results.
    """
    lib = Path(library_path).expanduser() if library_path else LIBRARY_PATH
    if not lib.exists():
        return []

    rg = shutil.which("rg")
    if not rg:
        return []

    try:
        result = subprocess.run(
            [
                rg,
                "--ignore-case",
                "--max-count", "3",          # max matches per file
                "--context", str(CONTEXT_LINES),
                "--type", "md",              # markdown files only
                "--no-heading",
                "--with-filename",
                "--line-number",
                "--color", "never",
                "--max-filesize", "100K",     # skip huge files
                query,
                str(lib),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    if result.returncode not in (0, 1):  # 1 = no matches
        return []

    return _parse_rg_output(result.stdout, max_results)


def _parse_rg_output(output: str, max_results: int) -> list[dict]:
    """Parse ripgrep output into file + snippet results."""
    if not output.strip():
        return []

    # Group lines by file
    file_snippets: dict[str, list[str]] = {}
    for line in output.strip().split("\n"):
        if "--" == line.strip():
            continue
        # Format: filepath:line_number:content
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        filepath = parts[0]
        content = parts[2].strip()
        if filepath not in file_snippets:
            file_snippets[filepath] = []
        if content and content not in file_snippets[filepath]:
            file_snippets[filepath].append(content)

    # Build results
    results = []
    for filepath, lines in file_snippets.items():
        snippet = "\n".join(lines[:6])  # cap snippet length
        if not snippet.strip():
            continue  # skip empty snippets
        # Make path relative to home for readability
        display_path = filepath.replace(str(Path.home()), "~")
        results.append({
            "file": display_path,
            "snippet": snippet,
        })
        if len(results) >= max_results:
            break

    return results
