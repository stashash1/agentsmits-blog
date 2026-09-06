"""Claude Code changelog via raw GitHub CHANGELOG.md."""
from __future__ import annotations

from agentsblog.models import SourceKind
from agentsblog.sources.base import ChangelogMdSource, Registry
from agentsblog.sources.registry import add_meta


@Registry.register("claude_code")
class ClaudeCodeSource(ChangelogMdSource):
    raw_url = "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md"
    repo_label = "anthropics/claude-code"
    max_versions = 5


add_meta(id="claude_code", name="Claude Code",
         url="https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md",
         kind=SourceKind.CHANGELOG_MD, tier=2)