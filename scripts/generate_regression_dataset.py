import shutil
import subprocess
from pathlib import Path

OUT_DIR = Path("regression")
ARTWORK = OUT_DIR / "dummy_artwork.jpg"
METADATA_OPTS = [
    "-metadata", "title=Regression Title",
    "-metadata", "artist=Regression Artist",
    "-metadata", "album=Regression Album",
    "-metadata", "date=2026",
]

def run_cmd(cmd: list[str]) -> bool:
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(cmd)}")
        print(e.stderr.decode(errors='replace'))
        return False

def generate_artwork():
    if ARTWORK.exists():
        ARTWORK.unlink()
    # 320x240 solid blue jpeg
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1",
        "-vframes", "1", str(ARTWORK)
    ]
    return run_cmd(cmd)

def generate_video(filename: str, vcodec: str, include_meta: bool = True, include_thumb: bool = True):
    path = OUT_DIR / filename
    if path.exists():
        path.unlink()

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "testsrc=s=320x240:r=30:d=1",
        "-f", "lavfi", "-i", "sine=f=440:b=4:d=1"
    ]
    if include_thumb:
        cmd.extend(["-i", str(ARTWORK)])

    # Map video and audio
    cmd.extend(["-map", "0:v", "-map", "1:a"])

    # Map artwork if included
    if include_thumb:
        cmd.extend(["-map", "2:v", "-disposition:v:1", "attached_pic"])

    cmd.extend([
        "-c:v:0", vcodec,
        "-b:v", "500k",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100"
    ])

    if include_thumb:
        cmd.extend(["-c:v:1", "mjpeg"])

    if include_meta:
        cmd.extend(METADATA_OPTS)

    cmd.append(str(path))
    return run_cmd(cmd)

def generate_audio(filename: str, ext: str, acodec: str, include_meta: bool = True, include_thumb: bool = True):
    path = OUT_DIR / filename
    if path.exists():
        path.unlink()

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=f=440:b=4:d=1"
    ]
    if include_thumb:
        cmd.extend(["-i", str(ARTWORK)])

    cmd.extend(["-map", "0:a"])
    if include_thumb:
        cmd.extend(["-map", "1:v", "-disposition:v", "attached_pic"])

    cmd.extend([
        "-c:a", acodec,
        "-b:a", "128k",
        "-ar", "44100"
    ])

    if include_thumb:
        cmd.extend(["-c:v", "mjpeg" if ext != ".flac" else "copy"])

    if include_meta:
        cmd.extend(METADATA_OPTS)

    cmd.append(str(path))
    return run_cmd(cmd)

def main():
    if not shutil.which("ffmpeg"):
        print("Error: ffmpeg not found in PATH.")
        return

    OUT_DIR.mkdir(exist_ok=True)

    print("Generating regression dataset...")

    if not generate_artwork():
        return

    tasks = [
        # Positive video
        ("valid_h264.mp4", lambda: generate_video("valid_h264.mp4", "libx264")),
        ("valid_vp9.mp4", lambda: generate_video("valid_vp9.mp4", "libvpx-vp9")),
        ("valid_av1.mp4", lambda: generate_video("valid_av1.mp4", "libaom-av1")),
        # Positive audio
        ("mp3_artwork.mp3", lambda: generate_audio("mp3_artwork.mp3", ".mp3", "libmp3lame")),
        ("m4a_artwork.m4a", lambda: generate_audio("m4a_artwork.m4a", ".m4a", "aac")),
        ("flac_artwork.flac", lambda: generate_audio("flac_artwork.flac", ".flac", "flac")),
        # Negative cases
        ("no_metadata.mp4", lambda: generate_video("no_metadata.mp4", "libx264", include_meta=False, include_thumb=True)),
        ("no_thumbnail.mp4", lambda: generate_video("no_thumbnail.mp4", "libx264", include_meta=True, include_thumb=False)),
        ("no_chapters.mp4", lambda: generate_video("no_chapters.mp4", "libx264")), # Chapters not yet synthesized, but we create the file
        ("mp3_no_artwork.mp3", lambda: generate_audio("mp3_no_artwork.mp3", ".mp3", "libmp3lame", include_meta=True, include_thumb=False)),
    ]

    success = True
    for name, func in tasks:
        if func():
            print(f"[OK] {name}")
        else:
            print(f"[FAIL] {name}")
            success = False

    if success:
        print("\nDataset generated successfully.")
    else:
        print("\nDataset generation completed with errors.")

if __name__ == "__main__":
    main()
