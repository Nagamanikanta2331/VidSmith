from rich.console import Console
from rich.theme import Theme

_THEME = Theme(
    {
        "primary": "bold cyan",
        "secondary": "bold magenta",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "muted": "dim white",
        "title": "bold white",
        "accent": "cyan",
    }
)

# legacy_windows=False forces ANSI escape-code output on Windows instead of
# the Win32 API renderer, which encodes text through cp1252 and cannot handle
# box-drawing characters.  This flag is a no-op on non-Windows platforms.
# main.py reconfigures sys.stdout to UTF-8 before these objects are created.
console = Console(theme=_THEME, legacy_windows=False)
err_console = Console(stderr=True, theme=_THEME, legacy_windows=False)
