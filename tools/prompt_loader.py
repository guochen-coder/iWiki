from pathlib import Path
from string import Template

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
_cache: dict[str, Template] = {}


def load_prompt(name: str, **kwargs) -> str:
    if name not in _cache:
        path = PROMPT_DIR / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")
        _cache[name] = Template(path.read_text(encoding="utf-8"))
    return _cache[name].safe_substitute(**kwargs)
