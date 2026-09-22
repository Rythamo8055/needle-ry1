#!/usr/bin/env python3
"""
ry1 - Standalone Desktop Floating Window
-----------------------------------------
Spawns the frameless, transparent, floating command palette powered by:
- Needle (45M System 1 On-Device Model)
- ImageMagick / FFmpeg / LibreOffice (Universal File Converter)
- yt-dlp (1,800+ Site Media Downloader & Search)
"""

import os
import sys
import json
import re
import subprocess
import webview

# Import our production assistant engine
sys.path.insert(0, "/home/rythamo/truing stuff")
import assistant

HTML_FILE = "/home/rythamo/truing stuff/ry1/src/index.html"

class Ry1Api:
    def __init__(self):
        self._current_proc = None

    def ask(self, query: str):
        """Calls the embedded 45M Needle model."""
        clean_query = query.strip() if query else ""
        if len(clean_query) < 3:
            return {
                "tool": None,
                "args": {},
                "confidence": 0.0,
                "reasoning": "Query too short"
            }

        # Terminate any previous in-flight needle process if still running
        if self._current_proc and self._current_proc.poll() is None:
            try:
                self._current_proc.terminate()
            except Exception:
                pass

        try:
            self._current_proc = subprocess.Popen(
                [assistant.BINARY_PATH, "--tools", assistant.TOOLS_PATH, "--prompt", clean_query],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, _ = self._current_proc.communicate(timeout=5)
            data = json.loads(stdout.strip())
        except Exception:
            return {"tool": None, "args": {}, "confidence": 0.0, "reasoning": "Model execution error"}

        conf = data.get("confidence", 0.0)
        calls = data.get("function_calls", [])
        validation = data.get("validation", {})
        ungrounded = validation.get("ungrounded", [])

        if not calls:
            return {
                "tool": None,
                "args": {},
                "confidence": conf,
                "reasoning": "Unrecognized command"
            }

        call = calls[0]
        tool_name = call.get("name")
        args = dict(call.get("arguments", {}))

        KNOWN_EXTS = {
            'jpg', 'jpeg', 'png', 'webp', 'gif', 'svg', 'bmp', 'tiff', 'tif', 'ico',
            'pdf', 'docx', 'doc', 'pptx', 'xlsx', 'odt', 'rtf', 'txt', 'csv',
            'mp4', 'mkv', 'avi', 'mov', 'webm', 'mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac'
        }
        EXT_SYNONYMS = {'jpeg': 'jpg', 'text': 'txt', 'word': 'docx'}

        # 1. CONVERT_FILE
        if tool_name == "convert_file":
            file_arg = args.get("file_name") or args.get("file_path") or args.get("input_file", "")
            fmt_arg = (args.get("target_format") or args.get("format") or "").lstrip(".").lower()

            # Check if prompt specifies format (e.g. "to jpeg", "as pdf", "into mp3")
            fmt_match = re.search(r"\b(to|into|as|format)\s+([a-zA-Z0-9]+)\b", clean_query, re.IGNORECASE)
            if fmt_match:
                prompt_fmt = fmt_match.group(2).lower()
                if prompt_fmt in KNOWN_EXTS or prompt_fmt in EXT_SYNONYMS:
                    fmt_arg = EXT_SYNONYMS.get(prompt_fmt, prompt_fmt)
                    args["target_format"] = fmt_arg

            if not fmt_arg or fmt_arg not in KNOWN_EXTS:
                return {
                    "tool": None,
                    "args": {},
                    "confidence": conf,
                    "reasoning": f"Unrecognized target format: '{fmt_arg}'"
                }

            # Check for quoted path or extract file from prompt if placeholder used
            if not file_arg or file_arg in ("file_name", "input_file"):
                quoted = re.findall(r"[\"']([^\"']+)[\"']", clean_query)
                if quoted:
                    file_arg = quoted[0]
                    args["file_name"] = file_arg

            return {
                "tool": "convert_file",
                "args": args,
                "confidence": max(conf, 0.85),
                "reasoning": f"Convert '{file_arg}' -> {fmt_arg}"
            }

        # 2. DOWNLOAD_MEDIA
        elif tool_name == "download_media":
            has_dl_word = bool(re.search(r"\b(download|get|save)\b", clean_query, re.IGNORECASE))
            url_match = re.search(r"https?://[^\s]+", clean_query)

            if url_match:
                return {
                    "tool": "download_media",
                    "args": {"url": url_match.group(0)},
                    "confidence": max(conf, 0.95),
                    "reasoning": f"Download from direct URL {url_match.group(0)}"
                }
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
                    cleaned = re.sub(r"^(download|get|save)\s+(song|video|audio|movie|track)?\s*(named|called)?\s*", "", clean_query, flags=re.IGNORECASE)
                    cleaned = re.sub(r"\s+(from\s+youtube|from\s+the\s+web|online).*$", "", cleaned, flags=re.IGNORECASE)
                    target_query = cleaned.strip()

                if target_query:
                    return {
                        "tool": "download_media",
                        "args": {"query": target_query, "url": f"ytsearch1:{target_query}"},
                        "confidence": 0.95,
                        "reasoning": f"Search & Download '{target_query}' from YouTube"
                    }

        # 3. SEARCH_MEDIA
        elif tool_name == "search_media":
            query = args.get("query")
            if not query:
                cleaned = re.sub(r"^(search|find|look\s+up|play)\s+(for|the|a)?\s*", "", clean_query, flags=re.IGNORECASE)
                query = cleaned.strip()

            if query:
                return {
                    "tool": "search_media",
                    "args": {"query": query},
                    "confidence": max(conf, 0.85),
                    "reasoning": f"Search for '{query}'"
                }

        return {
            "tool": None,
            "args": {},
            "confidence": conf,
            "reasoning": "Unrecognized or ambiguous command"
        }

    def execute_tool(self, tool: str, args: dict):
        """Executes the tool via native engines with real-time feedback."""
        if tool == "convert_file":
            file_arg = args.get("file_name") or args.get("file_path") or args.get("input_file", "")
            fmt_arg = args.get("target_format") or args.get("format", "")
            return assistant.execute_convert(file_arg, fmt_arg)
        elif tool == "download_media":
            def on_progress(percent, speed, eta):
                if window:
                    try:
                        window.evaluate_js(f"window.updateDownloadProgress('{percent}', '{speed}', '{eta}')")
                    except Exception:
                        pass
            return assistant.execute_download(args.get("url", ""), progress_callback=on_progress)
        elif tool == "search_media":
            return assistant.execute_search(args.get("query", ""))
        return "Unknown tool."

    def close(self):
        """Closes the floating window."""
        window.destroy()


if __name__ == "__main__":
    api = Ry1Api()

    # Read HTML
    with open(HTML_FILE, "r") as f:
        html_content = f.read()

    # Inject webview API bridge into HTML
    bridge_script = """
    <script>
      window.__TAURI__ = {
        core: {
          invoke: async function(cmd, payload) {
            if (cmd === 'ask') {
              return await window.pywebview.api.ask(payload.query);
            } else if (cmd === 'execute_tool') {
              return await window.pywebview.api.execute_tool(payload.tool, payload.args);
            }
          }
        }
      };
    </script>
    """
    html_content = html_content.replace("<head>", f"<head>{bridge_script}")

    print("[*] Launching ry1 Floating Window...")
    window = webview.create_window(
        title="ry1",
        html=html_content,
        js_api=api,
        width=680,
        height=420,
        frameless=True,
        easy_drag=True,
        on_top=True,
        transparent=True,
        background_color='#000000'
    )
    webview.start()
