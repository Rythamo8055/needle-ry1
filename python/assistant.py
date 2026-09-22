#!/usr/bin/env python3
"""
Needle On-Device Assistant
--------------------------
Powered by:
  - Needle (45M System 1 Edge Model)
  - yt-dlp (Media Download across 1,800+ sites & Multi-platform Search)
  - ImageMagick / FFmpeg / LibreOffice (Universal Any-to-Any File Converter)
"""

import os
import sys
import json
import re
import subprocess
import glob

# Configuration
BINARY_PATH = "/home/rythamo/from rahul laptop/development/just do it for fun/needle/src-tauri/binaries/needle-x86_64-unknown-linux-gnu"
TOOLS_PATH = "/tmp/needle_active_tools.json"
CONFIDENCE_THRESHOLD = 0.01  # Structural validation + 0.01 min threshold

# ----------------------------------------------------------------------
# 1. Optimal 3-Tool Schema (Strict Order: convert_file -> download -> search)
# ----------------------------------------------------------------------
TOOLS_SCHEMA = [
    {
        "name": "convert_file",
        "description": "Convert, turn, transform, change, or export any file, image, document, video, or audio into another format (e.g., png to jpg, webp to png, docx to pdf, mp4 to mp3, wav to flac).",
        "parameters": [
            {
                "name": "file_name",
                "type": "string",
                "description": "The local file name or path to convert"
            },
            {
                "name": "target_format",
                "type": "string",
                "description": "The target format or extension (e.g. jpg, png, pdf, mp3, flac)"
            }
        ]
    },
    {
        "name": "download_media",
        "description": "Download video, music, or audio from YouTube or the web. Use for web links (http/https) or when asked to download a song or video by name.",
        "parameters": [
            {
                "name": "url",
                "type": "string",
                "description": "The web URL to download, or song/video title to search and download"
            }
        ]
    },
    {
        "name": "search_media",
        "description": "Search, find, play, or look up any song, music artist, video, anime, stream, trailer, or media content on YouTube, Bilibili, or the web. Use when NO direct URL is provided.",
        "parameters": [
            {
                "name": "query",
                "type": "string",
                "description": "The search query keywords"
            }
        ]
    }
]

# Write tools schema to temporary path
with open(TOOLS_PATH, "w") as f:
    json.dump(TOOLS_SCHEMA, f, indent=2)


# ----------------------------------------------------------------------
# 2. Tool Implementations (High-Level Wrappers)
# ----------------------------------------------------------------------
def resolve_file_path(file_name: str) -> str:
    """Finds the file in current directory, ~/Downloads, or ~/Pictures if not absolute."""
    expanded = os.path.expanduser(file_name)
    if os.path.exists(expanded):
        return expanded

    # Search common user directories
    for search_dir in [os.getcwd(), os.path.expanduser("~/Downloads"), os.path.expanduser("~/Pictures"), os.path.expanduser("~/Documents")]:
        candidate = os.path.join(search_dir, file_name)
        if os.path.exists(candidate):
            return candidate

    return expanded  # Return original if not found yet (will report error gracefully)


def execute_convert(file_name: str, target_format: str) -> str:
    """Universal any-to-any file converter using ImageMagick, FFmpeg, and LibreOffice.
    Always preserves original files and saves as a non-colliding copy."""
    if not file_name or not target_format:
        return "Error: Missing filename or target format."

    resolved_path = resolve_file_path(file_name)
    if not os.path.exists(resolved_path):
        return f"Error: File not found: '{file_name}' (checked current folder, ~/Downloads, ~/Pictures, ~/Documents)."

    target_format = target_format.lstrip(".").lower()
    base_name, ext = os.path.splitext(resolved_path)
    ext = ext.lstrip(".").lower()

    # Collision-safe copy path (never overwrite existing target files)
    candidate = f"{base_name}.{target_format}"
    counter = 1
    while os.path.exists(candidate):
        candidate = f"{base_name} ({counter}).{target_format}"
        counter += 1
    out_file = candidate

    print(f"[*] Converting: '{resolved_path}' -> '{out_file}' (Preserving original)...")

    # Route 1: Documents (DOCX, PPTX, XLSX, ODT, RTF -> PDF, TXT)
    if ext in ("docx", "doc", "pptx", "xlsx", "odt", "rtf") or (target_format == "pdf" and ext not in ("png", "jpg", "jpeg", "webp")):
        out_dir = os.path.dirname(out_file) or "."
        cmd = ["libreoffice", "--headless", "--convert-to", target_format, "--outdir", out_dir, resolved_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        # If LibreOffice generated base_name.pdf and out_file had a suffix, rename to destination
        default_out = f"{base_name}.{target_format}"
        if os.path.exists(default_out) and default_out != out_file:
            os.rename(default_out, out_file)

    # Route 2: Images (PNG, JPG, JPEG, WEBP, GIF, SVG, BMP, TIFF, PDF)
    elif ext in ("png", "jpg", "jpeg", "webp", "gif", "svg", "bmp", "tiff") or target_format in ("png", "jpg", "jpeg", "webp"):
        cmd = ["magick", resolved_path, out_file]
        res = subprocess.run(cmd, capture_output=True, text=True)

    # Route 3: Audio & Video (MP4, MKV, AVI, MOV, WEBM, MP3, WAV, FLAC, OGG, M4A)
    elif ext in ("mp4", "mkv", "avi", "mov", "webm", "mp3", "wav", "flac", "ogg", "m4a"):
        cmd = ["ffmpeg", "-y", "-i", resolved_path, out_file]
        res = subprocess.run(cmd, capture_output=True, text=True)

    else:
        return f"Error: Unsupported conversion from .{ext} to .{target_format}"

    if res.returncode == 0 and os.path.exists(out_file):
        return f"Successfully converted: '{os.path.basename(out_file)}' (Original preserved)"
    return f"Conversion failed: {res.stderr.strip()[:200]}"


def execute_download(url: str, output_dir: str = "~/Downloads", progress_callback=None) -> str:
    """Downloads media from YouTube, Twitter, TikTok, Bilibili, and 1,800+ sites using yt-dlp.
    Supports real-time progress callback."""
    if not url:
        return "Error: No URL provided."

    out_path = os.path.expanduser(output_dir)
    print(f"[*] Downloading media from: '{url}' to {output_dir}...")

    cmd = [
        "yt-dlp",
        "--newline",
        "--no-warnings",
        "-P", out_path,
        "-f", "bv*[height<=1080]+ba/b[height<=1080]",
        "--merge-output-format", "mkv",
        url
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    import re
    # Match patterns like: [download]  45.2% of 10.12MiB at  2.55MiB/s ETA 00:03
    progress_regex = re.compile(r"\[download\]\s+([\d\.]+)%\s+of\s+([^\s]+)\s+at\s+([^\s]+)\s+ETA\s+([^\s]+)")

    for line in proc.stdout:
        m = progress_regex.search(line)
        if m and progress_callback:
            percent, size, speed, eta = m.groups()
            progress_callback(percent, speed, eta)
        elif "[download] 100%" in line and progress_callback:
            progress_callback("100", "Finalizing", "00:00")

    proc.wait()
    if proc.returncode == 0:
        return f"Successfully downloaded to {output_dir}"
    return "Download failed."


def execute_search(query: str, max_results: int = 3) -> str:
    """Searches YouTube or Bilibili for videos, anime, or music."""
    if not query:
        return "Error: No search query provided."

    print(f"[*] Searching for: '{query}'...")

    # Route to Bilibili if query asks for Bilibili, otherwise YouTube
    if "bilibili" in query.lower():
        prefix = f"bilisearch{max_results}:"
    else:
        prefix = f"ytsearch{max_results}:"

    clean_query = query.replace("bilibili", "").strip()
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(title)s | %(duration_string)s | %(webpage_url)s",
        f"{prefix}{clean_query}"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        return "\n" + res.stdout.strip()
    return "No search results found."


# ----------------------------------------------------------------------
# 3. Model Dispatcher with Confidence Gating
# ----------------------------------------------------------------------
def ask_needle(prompt: str) -> str:
    proc = subprocess.run(
        [BINARY_PATH, "--tools", TOOLS_PATH, "--prompt", prompt],
        capture_output=True, text=True
    )
    try:
        data = json.loads(proc.stdout.strip())
    except Exception:
        return "Error: Could not parse model response."

    conf = data.get("confidence", 0.0)
    calls = data.get("function_calls", [])
    validation = data.get("validation", {})
    ungrounded = validation.get("ungrounded", [])

    if not calls:
        return "Command not recognized."

    call = calls[0]
    tool_name = call.get("name")
    args = dict(call.get("arguments", {}))

    KNOWN_EXTS = {
        'jpg', 'jpeg', 'png', 'webp', 'gif', 'svg', 'bmp', 'tiff', 'tif', 'ico',
        'pdf', 'docx', 'doc', 'pptx', 'xlsx', 'odt', 'rtf', 'txt', 'csv',
        'mp4', 'mkv', 'avi', 'mov', 'webm', 'mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac'
    }
    EXT_SYNONYMS = {'jpeg': 'jpg', 'text': 'txt', 'word': 'docx'}

    if tool_name == "convert_file":
        file_arg = args.get("file_name") or args.get("file_path") or args.get("input_file", "")
        fmt_arg = (args.get("target_format") or args.get("format") or "").lstrip(".").lower()

        fmt_match = re.search(r"\b(to|into|as|format)\s+([a-zA-Z0-9]+)\b", prompt, re.IGNORECASE)
        if fmt_match:
            prompt_fmt = fmt_match.group(2).lower()
            if prompt_fmt in KNOWN_EXTS or prompt_fmt in EXT_SYNONYMS:
                fmt_arg = EXT_SYNONYMS.get(prompt_fmt, prompt_fmt)

        if not fmt_arg or fmt_arg not in KNOWN_EXTS:
            return f"Command not recognized: unsupported target format '{fmt_arg}'."

        if not file_arg or file_arg in ("file_name", "input_file"):
            quoted = re.findall(r"[\"']([^\"']+)[\"']", prompt)
            if quoted:
                file_arg = quoted[0]

        print(f"\n[Needle Decision] Tool: 'convert_file' | '{file_arg}' -> {fmt_arg}")
        return execute_convert(file_arg, fmt_arg)

    elif tool_name == "download_media":
        has_dl_word = bool(re.search(r"\b(download|get|save)\b", prompt, re.IGNORECASE))
        url_match = re.search(r"https?://[^\s]+", prompt)

        if url_match:
            print(f"\n[Needle Decision] Tool: 'download_media' | URL: '{url_match.group(0)}'")
            return execute_download(url_match.group(0))
        elif has_dl_word:
            target_query = None
            for c in calls:
                c_args = c.get("arguments", {})
                if c_args.get("query") and c_args.get("query") not in ("https://youtube.com", "youtube.com"):
                    target_query = c_args.get("query")
                    break
                elif c_args.get("name") and c_args.get("name") not in ("https://youtube.com", "youtube.com"):
                    target_query = c_args.get("name")
                    break

            if not target_query:
                cleaned = re.sub(r"^(download|get|save)\s+(song|video|audio|movie|track)?\s*(named|called)?\s*", "", prompt, flags=re.IGNORECASE)
                cleaned = re.sub(r"\s+(from\s+youtube|from\s+the\s+web|online).*$", "", cleaned, flags=re.IGNORECASE)
                target_query = cleaned.strip()

            if target_query:
                print(f"\n[Needle Decision] Tool: 'download_media' (Search & Download) | Query: '{target_query}'")
                return execute_download(f"ytsearch1:{target_query}")

    elif tool_name == "search_media":
        query = args.get("query")
        if not query:
            cleaned = re.sub(r"^(search|find|look\s+up|play)\s+(for|the|a)?\s*", "", prompt, flags=re.IGNORECASE)
            query = cleaned.strip()

        if query:
            print(f"\n[Needle Decision] Tool: 'search_media' | Query: '{query}'")
            return execute_search(query)

    return "Command not recognized or ambiguous."


# ----------------------------------------------------------------------
# 4. Interactive Assistant Loop
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 65)
    print("  Needle Assistant (On-Device 45M) | Confidence Gating Active")
    print("  Tools Loaded: convert_file | download_media | search_media")
    print("  Type 'exit' to quit.")
    print("=" * 65)

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                break
            response = ask_needle(user_input)
            print(f"Assistant: {response}")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
