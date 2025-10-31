from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
import subprocess
import tempfile
import os
import yt_dlp
import imageio_ffmpeg as ffmpeg

# ✅ Ensure FFmpeg binary path is available
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg.get_ffmpeg_exe())

app = FastAPI()


@app.get("/")
def home():
    """Health check endpoint."""
    return {"status": "OK", "message": "Clipper Service is live!"}


@app.post("/clip")
async def clip_video(req: Request):
    """
    Create a TikTok/Reels-style clip:
    - 9:16 vertical format
    - optional logo watermark
    - optional subtitles

    Input JSON:
    {
      "videoUrl": "https://youtube.com/watch?v=xxxx",
      "start": "30.0",
      "end": "60.0",
      "subtitles": "Optional text caption"
    }
    """
    data = await req.json()
    video_url = data.get("videoUrl")
    start = data.get("start")
    end = data.get("end")
    subtitles_text = data.get("subtitles")

    if not video_url or not start or not end:
        return JSONResponse(
            {"error": "Missing required parameters: videoUrl, start, end"},
            status_code=400,
        )

    try:
        # Temporary working directory
        tmpdir = tempfile.mkdtemp()
        input_path = os.path.join(tmpdir, "input.mp4")
        raw_clip = os.path.join(tmpdir, "clip_raw.mp4")
        output_path = os.path.join(tmpdir, "clip_final.mp4")

        # ✅ Use cookies for restricted videos if available
        cookie_file = "youtube_cookies.txt"
        ydl_opts = {"outtmpl": input_path, "format": "mp4"}
        if os.path.exists(cookie_file):
            ydl_opts["cookiefile"] = cookie_file

        # ✅ Download YouTube video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # ✅ Trim the video using ffmpeg
        subprocess.run(
            [
                "ffmpeg",
                "-ss",
                str(start),
                "-to",
                str(end),
                "-i",
                input_path,
                "-c",
                "copy",
                raw_clip,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # ✅ Optional subtitles
        subs_path = None
        if subtitles_text:
            subs_path = os.path.join(tmpdir, "subs.srt")
            with open(subs_path, "w", encoding="utf-8") as f:
                f.write("1\n00:00:00,000 --> 00:00:59,000\n" + subtitles_text)

        # ✅ Build FFmpeg filter chain (Render-compatible)
        vf = "crop=(ih*9/16):ih,scale=1080:1920"

        # Add logo overlay if logo.png exists
        logo_path = "logo.png"
        if os.path.exists(logo_path):
            vf += ",overlay=W-w-50:H-h-50"

        # Add subtitles if provided
        if subs_path:
            vf += f",subtitles={subs_path}"

        # ✅ Apply filters and produce final video
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                raw_clip,
                "-vf",
                vf,
                "-c:a",
                "copy",
                output_path,
            ],
            check=True,
        )

        # ✅ Return the processed file
        return FileResponse(output_path, media_type="video/mp4", filename="tiktok_clip.mp4")

    except subprocess.CalledProcessError as e:
        return JSONResponse({"error": f"FFmpeg failed: {e}"}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
