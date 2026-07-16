from mediaforge.downloader.job import MetadataMode
from mediaforge.downloader.validators.context import ValidationContext
from mediaforge.downloader.validators.models import (
    DownloadValidationResult,
    MetadataValidationResult,
)


def validate_metadata(ctx: ValidationContext, validation: DownloadValidationResult) -> None:
    if ctx.job.metadata_mode == MetadataMode.NONE:
        return

    meta_val = MetadataValidationResult()
    validation.metadata = meta_val

    if not ctx.exists:
        meta_val.success = False
        return

    if ctx.job.metadata_mode == MetadataMode.EMBED:
        if ctx.ffprobe_data:
            # Check format tags for general metadata
            tags = ctx.ffprobe_data.get("format", {}).get("tags", {})
            if tags:
                meta_val.embedded = True

            # Check chapters
            chapters = ctx.ffprobe_data.get("chapters", [])
            if chapters:
                meta_val.chapter_count = len(chapters)
        else:
            # We assume success if ffprobe is missing/failed
            meta_val.embedded = True
