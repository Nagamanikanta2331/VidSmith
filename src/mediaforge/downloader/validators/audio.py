from mediaforge.downloader.validators.context import ValidationContext
from mediaforge.downloader.validators.models import AudioValidationResult, DownloadValidationResult


def validate_audio(ctx: ValidationContext, validation: DownloadValidationResult) -> None:
    if not ctx.is_audio:
        return

    audio_val = AudioValidationResult()
    validation.audio = audio_val

    if not ctx.exists:
        return

    ext = ctx.primary_output.suffix.lower() if ctx.primary_output else ""
    # Check if format reliably supports embedded artwork
    supported_artwork_formats = {".mp3", ".m4a", ".m4b", ".flac", ".ogg", ".opus"}
    if ext in supported_artwork_formats:
        audio_val.artwork_status = "Missing"
    else:
        audio_val.artwork_status = "Unsupported"

    # 1. Verify Artwork via mutagen (cached in context)
    if audio_val.artwork_status == "Missing" and ctx.mutagen_has_artwork is True:
        audio_val.artwork_status = "Embedded"

    # 2. Fallback to ffprobe for artwork + extract metadata
    if ctx.ffprobe_data:
        # Fallback artwork verification
        if audio_val.artwork_status == "Missing":
            for stream in ctx.ffprobe_data.get("streams", []):
                if stream.get("codec_type") == "video":
                    disp = stream.get("disposition", {})
                    if disp.get("attached_pic") == 1:
                        audio_val.artwork_status = "Embedded"
                        break

        # 3. Verify Metadata
        tags = ctx.ffprobe_data.get("format", {}).get("tags", {})
        tags_lower = {k.lower(): v for k, v in tags.items()}

        if "title" in tags_lower:
            audio_val.title_present = True
        if any(k in tags_lower for k in ["artist", "album_artist", "uploader", "channel"]):
            audio_val.artist_present = True
        if "album" in tags_lower:
            audio_val.album_present = True
        if any(k in tags_lower for k in ["date", "year", "upload_date"]):
            audio_val.date_present = True

        if (
            audio_val.title_present
            or audio_val.artist_present
            or audio_val.album_present
            or audio_val.date_present
        ):
            audio_val.metadata_present = True
