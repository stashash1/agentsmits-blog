import re
_VERSION_RE = re.compile(
    r"\b(?:GPT|Claude|Gemini|Llama|Grok|Mixtral|Mistral|DeepSeek|Qwen|Phi|Sora)"
    r"[\s\-]*\d+(?:\.\d+)?\b",
    re.IGNORECASE,
)

titles = [
    "Claude Code 2.1.263",
    "Claude Code 2.1.261",
    "Claude Code 2.1.260",
    "Claude Code 2.1.259",
    "Set an expiration date for individual user budgets",
    "Copilot code review can now approve pull requests",
    "Claude Fable 5.1 is generally available in GitHub Copilot",
    "Enterprise-managed settings support any default model",
    "Content exclusions generally available in Copilot app and CLI",
    "Upcoming deprecation of selected GitHub Copilot models",
    "Reopening Copilot Business and Enterprise signups",
    "Mistral raises �3B as sovereign AI becomes big business",
]
for t in titles:
    print(f"{_VERSION_RE.search(t) is not None}: {t}")
