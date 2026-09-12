import subprocess
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
# GET ALL VIDEOS FROM CHANNEL
# ============================================================

def get_channel_videos():
    print("\n========================================")
    print(" Kingdom Sound Scanner")
    print("========================================\n")

    print("Scanning Kingdom Sound channel...")
    print("This may take a while depending on the number of videos.\n")

    command = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-single-json",
        "--ignore-errors",
        CHANNEL_URL
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    if result.returncode != 0:
        print("ERROR:")
        print(result.stderr)
        return []

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Could not read YouTube's response.")
        return []

    videos = data.get("entries", [])

    print(f"Found {len(videos)} videos.\n")

    return videos


# ============================================================
# GET FULL VIDEO INFORMATION
# ============================================================

def get_video_info(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"

    command = [
        "yt-dlp",
        "--dump-single-json",
        "--skip-download",
        "--ignore-errors",
        url
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    if result.returncode != 0:
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


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
    """
    Looks for things such as:

    Original Singer: Someone
    Original Song: Someone
    Original Artist - Someone
    Singer: Someone
    Artist: Someone
    """

    for label in labels:

        pattern = rf"{label}\s*[:\-–—]\s*(.+)"

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            value = match.group(1).split("\n")[0]

            # Stop at common separators
            value = re.split(
                r"\s+\|\s+|\s+•\s+",
                value
            )[0]

            return clean_text(value)

    return ""


# ============================================================
# EXTRACT SONG / SINGER
# ============================================================

def extract_song_data(title, description):

    title = clean_text(title)
    description = clean_text(description)

    combined = title + "\n" + description

    # --------------------------------------------------------
    # ORIGINAL SINGER
    # --------------------------------------------------------

    original_singer = find_labeled_value(
        combined,
        [
            r"Original Singer",
            r"Original Artist",
            r"Original Song By",
            r"Original Song",
            r"Originally By",
            r"Original"
        ]
    )

    # --------------------------------------------------------
    # PERFORMER / SINGER
    # --------------------------------------------------------

    singer = find_labeled_value(
        combined,
        [
            r"Singer",
            r"Performed By",
            r"Performed by",
            r"Artist",
            r"Vocal"
        ]
    )

    # --------------------------------------------------------
    # SONG
    # --------------------------------------------------------

    song = find_labeled_value(
        combined,
        [
            r"Song",
            r"Title"
        ]
    )

    # --------------------------------------------------------
    # TRY TO UNDERSTAND TITLE
    # --------------------------------------------------------

    if not song:

        # Remove common Kingdom Sound information
        cleaned_title = re.sub(
            r"\s*@?\s*Kingdom\s*Sound.*$",
            "",
            title,
            flags=re.IGNORECASE
        )

        cleaned_title = re.sub(
            r"\s*\|\s*.*$",
            "",
            cleaned_title
        )

        # Remove things like:
        # "Official Video"
        # "Live"
        # "Worship Night 2025"

        cleaned_title = re.sub(
            r"\b(official video|official audio|live|lyrics?)\b",
            "",
            cleaned_title,
            flags=re.IGNORECASE
        )

        cleaned_title = re.sub(
            r"\b(worship night|worship service|worship)\s*\d{0,4}\b",
            "",
            cleaned_title,
            flags=re.IGNORECASE
        )

        song = clean_text(cleaned_title)

    # --------------------------------------------------------
    # TRY TO FIND "BY" IN TITLE
    # --------------------------------------------------------

    if not singer:

        patterns = [
            r"\s+by\s+(.+)$",
            r"\s+-\s+(.+)$",
            r"\s+–\s+(.+)$",
            r"\s+—\s+(.+)$"
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                title,
                re.IGNORECASE
            )

            if match:

                possible_singer = clean_text(
                    match.group(1)
                )

                # Avoid treating event names as singers
                if not re.search(
                    r"kingdom\s*sound|worship\s*night",
                    possible_singer,
                    re.IGNORECASE
                ):
                    singer = possible_singer

                    # Remove singer from song
                    song = re.sub(
                        pattern,
                        "",
                        title,
                        flags=re.IGNORECASE
                    )

                    song = clean_text(song)

                    break

    # --------------------------------------------------------
    # FALLBACKS
    # --------------------------------------------------------

    if not song:
        song = title

    if not singer:
        singer = "Unknown"

    if not original_singer:
        original_singer = "Unknown"

    return {
        "song": song,
        "singer": singer,
        "original_singer": original_singer
    }


# ============================================================
# NORMALIZE FOR DUPLICATE DETECTION
# ============================================================

def normalize(text):

    text = text.lower()

    text = re.sub(
        r"[^\w\s]",
        "",
        text,
        flags=re.UNICODE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# CREATE CHECKLIST
# ============================================================

def create_checklist(songs):

    lines = []

    lines.append("# 🎵 Kingdom Sound — Listening Checklist")
    lines.append("")
    lines.append(
        f"**Total unique songs: {len(songs)}**"
    )
    lines.append("")
    lines.append(
        "Format: **Song — Singer (Original Singer)**"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Sort alphabetically
    songs = sorted(
        songs,
        key=lambda x: normalize(x["song"])
    )

    for song in songs:

        song_name = song["song"]
        singer = song["singer"]
        original = song["original_singer"]
        url = song["url"]

        lines.append(
            f"- [ ] **{song_name}** — "
            f"{singer} ({original})"
        )

        lines.append(
            f"  - [YouTube]({url})"
        )

        lines.append("")

    Path(OUTPUT_FILE).write_text(
        "\n".join(lines),
        encoding="utf-8"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    videos = get_channel_videos()

    if not videos:
        print("No videos found.")
        return

    songs = []

    print("Reading video information...\n")

    for index, video in enumerate(videos, start=1):

        video_id = video.get("id")

        if not video_id:
            continue

        print(
            f"[{index}/{len(videos)}] "
            f"Reading video..."
        )

        info = get_video_info(video_id)

        if not info:
            continue

        title = info.get("title", "")
        description = info.get("description", "")

        data = extract_song_data(
            title,
            description
        )

        data["url"] = (
            f"https://www.youtube.com/watch?v={video_id}"
        )

        data["youtube_title"] = title

        songs.append(data)

    # ========================================================
    # SAVE RAW DATA
    # ========================================================

    Path(RAW_FILE).write_text(
        json.dumps(
            songs,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    unique = {}

    for song in songs:

        key = (
            normalize(song["song"]),
            normalize(song["singer"]),
            normalize(song["original_singer"])
        )

        if key not in unique:
            unique[key] = song

    unique_songs = list(unique.values())

    # ========================================================
    # CREATE CHECKLIST
    # ========================================================

    create_checklist(unique_songs)

    print("\n========================================")
    print(" DONE!")
    print("========================================\n")

    print(
        f"Videos scanned: {len(videos)}"
    )

    print(
        f"Songs found: {len(songs)}"
    )

    print(
        f"Unique songs: {len(unique_songs)}"
    )

    print(
        f"\nChecklist: {OUTPUT_FILE}"
    )

    print(
        f"Raw data:   {RAW_FILE}"
    )

    print("\n")


if __name__ == "__main__":
    main()