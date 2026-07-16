from vidsmith.downloader.job import ThumbnailMode
from vidsmith.downloader.validators.context import ValidationContext
from vidsmith.downloader.validators.models import (
    DownloadValidationResult,
    ThumbnailValidationResult,
    ValidationErrorCode,
)

_NO_THUMBNAIL_EMBED = {".ts", ".webm", ".avi", ".flv", ".wav"}


def validate_thumbnail(ctx: ValidationContext, validation: DownloadValidationResult) -> None:
    if ctx.job.thumbnail_mode == ThumbnailMode.NONE:
        return

    thumb_val = ThumbnailValidationResult()
    validation.thumbnail = thumb_val

    if ctx.job.thumbnail_mode == ThumbnailMode.SAVE:
        thumb_val.saved = True
        return

    if not ctx.exists:
        thumb_val.success = False
        return

    # Check embedding if EMBED or BOTH
    if ctx.job.thumbnail_mode in {ThumbnailMode.EMBED, ThumbnailMode.BOTH}:
        suffix = ctx.primary_output.suffix.lower() if ctx.primary_output else ""
        if suffix not in _NO_THUMBNAIL_EMBED:
            if ctx.ffprobe_data:
                is_emb = False
                for stream in ctx.ffprobe_data.get("streams", []):
                    c_type = stream.get("codec_type", "")
                    c_name = stream.get("codec_name", "")
                    tags = stream.get("tags", {})
                    mimetype = tags.get("mimetype", "").lower()
                    handler_name = tags.get("handler_name", "").lower()
                    disp = stream.get("disposition", {})
                    attached_pic = disp.get("attached_pic", 0)

                    duration_str = stream.get("duration", tags.get("DURATION", ""))
                    try:
                        duration = float(duration_str) if duration_str else -1.0
                    except ValueError:
                        duration = -1.0

                    if suffix in {".mp4", ".m4a", ".m4v"}:
                        if attached_pic == 1:
                            is_emb = True
                            break
                        if c_type == "video" and c_name in {"mjpeg", "jpeg", "jpg", "png", "webp"}:
                            if (
                                duration == 0.0
                                or duration_str == "0.000000"
                                or "cover" in handler_name
                                or "artwork" in handler_name
                            ):
                                is_emb = True
                                break
                            nb_frames = stream.get("nb_frames", "")
                            if nb_frames == "1":
                                is_emb = True
                                break
                    else:
                        if c_type == "attachment":
                            is_emb = True
                            break
                        if attached_pic == 1:
                            is_emb = True
                            break
                        if mimetype.startswith("image/"):
                            is_emb = True
                            break
                        if c_type == "video" and c_name in {"mjpeg", "jpeg", "jpg", "png", "webp"}:
                            if mimetype.startswith("image/"):
                                is_emb = True
                                break
                            if (
                                duration == 0.0
                                or duration_str == "0.000000"
                                or stream.get("nb_frames") == "1"
                            ):
                                is_emb = True
                                break

                if is_emb:
                    thumb_val.embedded = True
                    if ctx.job.thumbnail_mode == ThumbnailMode.BOTH:
                        thumb_val.saved = True
                else:
                    validation.fail(
                        ValidationErrorCode.THUMBNAIL_NOT_EMBEDDED,
                        f"Validation failed: Thumbnail embedding failed for {ctx.primary_output.name}. Temporary files preserved.",  # type: ignore
                    )
                    thumb_val.success = False
            else:
                # ffprobe missing or failed, assume graceful degradation
                thumb_val.embedded = False
                if ctx.job.thumbnail_mode == ThumbnailMode.BOTH:
                    thumb_val.saved = True
        else:
            if ctx.job.thumbnail_mode == ThumbnailMode.BOTH:
                thumb_val.saved = True
