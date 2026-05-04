"""
Record a short Streamlit demo video for README / YC applications.

Requires:
  pip install playwright
  playwright install chromium

Run from anywhere:
  python research_os/scripts/record_demo_video.py

Or from inside the research_os package folder:
  python scripts/record_demo_video.py
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _wait_port(host: str, port: int, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError(f"Port {port} did not open within {timeout}s")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install Playwright first: pip install playwright && playwright install chromium", file=sys.stderr)
        return 1

    here = Path(__file__).resolve()
    pkg_root = here.parents[1]  # research_os/ (contains ui/, scripts/)
    parent = pkg_root.parent  # directory that should be on PYTHONPATH for `import research_os`

    port = 8765
    video_dir = Path(tempfile.mkdtemp(prefix="research_os_demo_"))
    out_webm = pkg_root / "assets" / "demo-research-os.webm"
    out_mp4 = pkg_root / "assets" / "demo-research-os.mp4"
    out_webm.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(parent)
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(pkg_root / "ui" / "app.py"),
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(pkg_root),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        _wait_port("127.0.0.1", port, timeout=180.0)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                record_video_dir=str(video_dir),
                record_video_size={"width": 1280, "height": 800},
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()
            page.set_default_timeout(180_000)

            page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded")
            page.wait_for_timeout(2500)

            page.get_by_role("button", name=re.compile(r"Compile problem", re.I)).click()
            page.wait_for_timeout(2500)

            page.get_by_role("button", name=re.compile(r"Run experiment", re.I)).click()
            # DenseRetriever may load sentence-transformers / torch on first run
            page.get_by_text(re.compile(r"Experiment finished", re.I)).wait_for(timeout=180_000)

            page.get_by_role("tab", name=re.compile(r"Results", re.I)).click()
            page.wait_for_timeout(5000)

            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(2000)

            context.close()
            browser.close()

        webms = sorted(video_dir.glob("*.webm"))
        if not webms:
            print(f"No webm produced in {video_dir}; contents: {list(video_dir.iterdir())}", file=sys.stderr)
            return 2

        shutil.copy2(webms[0], out_webm)
        print(f"Wrote {out_webm} ({out_webm.stat().st_size // 1024} KB)")

        # Optional MP4 for wider compatibility (YC / players)
        def _ffmpeg_bin() -> str | None:
            try:
                import imageio_ffmpeg as ioffmpeg

                return ioffmpeg.get_ffmpeg_exe()
            except Exception:
                return None

        ffmpeg_bin = shutil.which("ffmpeg") or _ffmpeg_bin()
        if ffmpeg_bin:
            try:
                subprocess.run(
                    [
                        ffmpeg_bin,
                        "-y",
                        "-i",
                        str(out_webm),
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-movflags",
                        "+faststart",
                        "-an",
                        str(out_mp4),
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print(f"Wrote {out_mp4} ({out_mp4.stat().st_size // 1024} KB)")
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                print(f"ffmpeg encode failed ({e}) — WebM only.", file=sys.stderr)
        else:
            print("No ffmpeg executable — WebM only. pip install imageio-ffmpeg for bundled ffmpeg.", file=sys.stderr)

        return 0
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=15)
        except Exception:
            proc.kill()
        shutil.rmtree(video_dir, ignore_errors=True)
        err = proc.stderr.read() if proc.stderr else ""
        if proc.returncode not in (0, None) and err:
            print(err[-4000:], file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
