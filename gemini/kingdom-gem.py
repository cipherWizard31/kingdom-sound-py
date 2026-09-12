import json
import re

from pathlib import Path

# ============================================================
# SETTINGS
# ============================================================

CHANNEL_URL = "https://www.youtube.com/@kingdomsoundministry/videos"
OUTPUT_FILE = "kingdom_sound_checklist.md"
RAW_FILE = "kingdom_sound_raw.json"


# ============================================================
# GET ALL VIDEOS (SINGLE FETCH)
# ============================================================

def get_channel_videos():
    """Fetches all video metadata in a single yt-dlp call directly via Python API.

    Avoids spawning N subprocesses and making N individual network requests.
    """
    print("\n========================================")
    print(" Kingdom Sound Fast Scanner")
    print("========================================\n")
    print("Scanning Kingdom Sound channel metadata...")

    try:
        import yt_dlp
    except ImportError:
        print("ERROR: yt-dlp package not installed in current Python environment.")
        print("Install it via: pip install yt-dlp")
        return []

    # Extract all metadata in 1 request without downloading video files
    ydl_opts = {
        "extract_flat": "in_playlist",  # Extract playlist metadata quickly
        "skip_download": True,
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(CHANNEL_URL, download=False)

    if not result:
        print("Failed to fetch channel data.")
        return []

    # Handle single playlist/channel layout
    entries = result.get("entries", [])
    videos = [e for e in entries if e]

    print(f"Found {len(videos)} videos.\n")
    return videos


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(text):
    if not text:
        return ""
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ============================================================
# FIND VALUE AFTER A LABEL
# ============================================================

def find_labeled_value(text, labels):
    for label in labels:
        pattern = rf"{label}\s*[:\-–—]\s*(.+)"
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            value = match.group(1).split("\n")[0]
            value = re.split(r"\s+\|\s+|\s+•\s+", value)[0]
            return clean_text(value)

    return ""


# ============================================================
# EXTRACT SONG / SINGER
# ============================================================

def extract_song_data(title, description):
    title = clean_text(title)
    description = clean_text(description)
    combined = f"{title}\n{description}"

    original_singer = find_labeled_value(
        combined,
        [
            r"Original Singer",
            r"Original Artist",
            r"Original Song By",
            r"Original Song",
            r"Originally By",
            r"Original",
        ],
    )

    singer = find_labeled_value(
        combined,
        [
            r"Singer",
            r"Performed By",
            r"Performed by",
            r"Artist",
            r"Vocal",
        ],
    )

    song = find_labeled_value(combined, [r"Song", r"Title"])

    if not song:
        cleaned_title = re.sub(
            r"\s*@?\s*Kingdom\s*Sound.*$", "", title, flags=re.IGNORECASE
        )
        cleaned_title = re.sub(r"\s*\|\s*.*$", "", cleaned_title)
        cleaned_title = re.sub(
            r"\b(official video|official audio|live|lyrics?)\b",
            "",
            cleaned_title,
            flags=re.IGNORECASE,
        )
        cleaned_title = re.sub(
            r"\b(worship night|worship service|worship)\s*\d{0,4}\b",
            "",
            cleaned_title,
            flags=re.IGNORECASE,
        )
        song = clean_text(cleaned_title)

    if not singer:
        patterns = [
            r"\s+by\s+(.+)$",
            r"\s+-\s+(.+)$",
            r"\s+–\s+(.+)$",
            r"\s+—\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                possible_singer = clean_text(match.group(1))
                if not re.search(
                    r"kingdom\s*sound|worship\s*night",
                    possible_singer,
                    re.IGNORECASE,
                ):
                    singer = possible_singer
                    song = clean_text(re.sub(pattern, "", title, flags=re.IGNORECASE))
                    break

    return {
        "song": song or title,
        "singer": singer or "Unknown",
        "original_singer": original_singer or "Unknown",
    }


# ============================================================
# NORMALIZE FOR DUPLICATE DETECTION
# ============================================================

def normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


# ============================================================
# CREATE CHECKLIST
# ============================================================

def create_checklist(songs):
    lines = [
        "# 🎵 Kingdom Sound — Listening Checklist",
        "",
        f"**Total unique songs: {len(songs)}**",
        "",
        "Format: **Song — Singer (Original Singer)**",
        "",
        "---",
        "",
    ]

    songs = sorted(songs, key=lambda x: normalize(x["song"]))

    for song in songs:
        lines.append(
            f"- [ ] **{song['song']}** — {song['singer']} ({song['original_singer']})"
        )
        lines.append(f"  - [YouTube]({song['url']})\n")

    Path(OUTPUT_FILE).write_text("\n".join(lines), encoding="utf-8")


# ============================================================
# MAIN
# ============================================================

def main():
    videos = get_channel_videos()
    if not videos:
        print("No videos found.")
        return

    songs = []
    print("Processing video metadata...\n")

    for video in videos:
        video_id = video.get("id") or video.get("url")
        if not video_id:
            continue

        title = video.get("title", "")
        # Flat extraction gets description if available; defaults to title parsing
        description = video.get("description", "")

        data = extract_song_data(title, description)
        data["url"] = (
            video_id
            if video_id.startswith("http")
            else f"https://www.youtube.com/watch?v={video_id}"
        )
        data["youtube_title"] = title
        songs.append(data)

    # Save raw data
    Path(RAW_FILE).write_text(
        json.dumps(songs, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Deduplicate
    unique = {}
    for song in songs:
        key = (
            normalize(song["song"]),
            normalize(song["singer"]),
            normalize(song["original_singer"]),
        )
        if key not in unique:
            unique[key] = song

    unique_songs = list(unique.values())
    create_checklist(unique_songs)

    print("========================================")
    print(" DONE!")
    print("========================================")
    print(f"Videos scanned: {len(videos)}")
    print(f"Songs found:    {len(songs)}")
    print(f"Unique songs:   {len(unique_songs)}")
    print(f"Checklist file: {OUTPUT_FILE}")
    print(f"Raw data file:  {RAW_FILE}\n")


if __name__ == "__main__":
    main()