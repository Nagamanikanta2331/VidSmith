from mediaforge.cli.executor import execute_subtitles
from mediaforge.cli.wizard.base import WizardState
from mediaforge.models.media import AnalysisResult, MediaType

state = WizardState()
state.set("output_dir", ".")
state.set("languages", ["en"])
state.set("output_format", "txt")

result = AnalysisResult(
    url="https://www.youtube.com/watch?v=jNQXAC9IVRw",
    title="Me at the zoo",
    media_type=MediaType.VIDEO,
    subtitle_languages=["en"],
)

execute_subtitles(state, result)
