# Windows Explorer Compatibility

VidSmith explicitly focuses on delivering high-quality, highly compatible media files that work natively within the Windows ecosystem (Windows Explorer, Movies & TV, Windows Media Player). 

There is an important distinction between a file that is technically formatted correctly (e.g., artwork successfully embedded according to FFprobe) and a file that Windows Explorer visually previews. The constraints of the latter depend heavily on your Windows environment, installed codecs, and Explorer's caching behaviors.

## Support Matrix

| Format      | Status          | Notes                                                     |
| ----------- | --------------- | --------------------------------------------------------- |
| **MP4 (H.264)** | **Fully Supported** | **Primary recommended reference format.** Native Explorer support. |
| MP4 (VP9)   | Fully Supported | Requires installed Windows VP9 Video Extensions for Explorer thumbnails. |
| MP4 (AV1)   | Supported       | Explorer thumbnail behavior depends on OS codec support (AV1 Video Extension). |
| MP3         | Fully Supported | Native support via ID3 APIC frames.                       |
| M4A         | Fully Supported | Native support via `covr` atoms.                          |
| FLAC        | Fully Supported | Native support via FLAC Picture blocks.                   |

## Explorer Thumbnail Caching Limitations

Windows Explorer aggressively caches thumbnails. When you replace a file with identical metadata or download a new version over an existing file, Explorer may display a cached (or blank) thumbnail. 

If VidSmith reports validation success but Explorer fails to show a thumbnail, try the following before assuming a bug:
1.  **Refresh Explorer**: Press `F5` in the directory.
2.  **Reopen the Folder**: Navigate out of the directory and back in.
3.  **Clear Thumbnail Cache**: Use the native "Disk Cleanup" tool and select "Thumbnails" to force Windows to regenerate previews.

## Environmental Codec Limitations

Windows 10/11 does not ship natively with AV1 or VP9 hardware/software decoders out of the box in all configurations.
If you download an AV1 or VP9 video and notice that VLC plays it fine, but Windows Explorer shows a generic video icon, this is an **OS environmental limitation**, not a VidSmith tagging issue. You will need to install the respective codec extensions from the Microsoft Store.
