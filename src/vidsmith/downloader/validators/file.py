from vidsmith.downloader.validators.context import ValidationContext
from vidsmith.downloader.validators.models import DownloadValidationResult, ValidationErrorCode


def validate_files(ctx: ValidationContext, validation: DownloadValidationResult) -> None:
    if not ctx.primary_output:
        validation.fail(
            ValidationErrorCode.FILE_MISSING, "Validation failed: no primary output determined."
        )
        return

    if not ctx.exists:
        validation.fail(
            ValidationErrorCode.FILE_MISSING,
            f"Validation failed: output file does not exist at {ctx.primary_output}",
        )
        return

    if ctx.size_bytes == 0:
        validation.fail(
            ValidationErrorCode.FILE_EMPTY,
            f"Validation failed: output file is empty at {ctx.primary_output}",
        )
        return
