import traceback
from pathlib import Path

import vidsmith.cli.executor as executor
from vidsmith.cli.wizard.base import WizardState
from vidsmith.metadata.analyzer import analyze


def main():
    print("Analyzing URL...")
    result = analyze("https://youtu.be/jNQXAC9IVRw")

    # Mock the prompt properly returning a Path
    executor._prompt_download_location = lambda: Path(".")  # type: ignore

    # Override the _show_error so it doesn't wait for input
    def no_prompt_error(title, msg):
        print(f"Error Title: {title}\nMessage: {msg}")
        raise RuntimeError(f"{title}: {msg}")

    executor._show_error = no_prompt_error

    print("Executing Best Download directly...")
    try:
        executor.execute_best_download(WizardState(), result)
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
