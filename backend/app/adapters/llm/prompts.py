from pathlib import Path


class PromptRepository:
    def __init__(self, prompt_dir: Path | None = None) -> None:
        self.prompt_dir = prompt_dir or Path(__file__).with_name("prompts")

    def load(self, name: str) -> str:
        path = self.prompt_dir / f"{name}.txt"
        if not path.is_file():
            raise FileNotFoundError(f"Prompt not found: {name}")
        return path.read_text(encoding="utf-8").strip()
