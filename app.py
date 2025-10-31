from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
import subprocess
import tempfile
import os
import yt_dlp
import imageio_ffmpeg as ffmpeg

# Ensure FFmpeg is on PATH
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg.get_ffmpeg_exe())

app = FastAPI()


@app.get("/")
def home():
    return {"status": "OK", "message": "Clipper Service is live!"}


@app.post("/clip")
async def clip_video(req: Request):
    """
    Input JSON Example:
    {
      "videoUrl": "https://youtube.com/watch?v=XXXX",
      "start": "30.0",
      "end": "60.0",
      "subtitles": "Optional caption text"
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
        tmpdir = tempfile.mkdtemp()
        input_path = os.path.join(tmpdir, "input.mp4")
        raw_clip = os.path.join(tmpdir, "clip_raw.mp4")
        output_path = os.path.join(tmpdir, "clip_final.mp4")

        # --- Download YouTube Video ---
        cookie_file = "youtube_cookies.txt"
        ydl_opts = {"outtmpl": input_path, "format": "mp4"}
        if os.path.exists(cookie_file):
            ydl_opts["cookiefile"] = cookie_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        if not os.path.exists(input_path):
            return JSONResponse({"error": "Video download failed"}, status_code=500)

        # --- Cut the Requested Segment ---
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
                "-y",
            ],
            check=True,
        )

        # --- Optional Subtitles File ---
        subs_path = None
        if subtitles_text:
            subs_path = os.path.join(tmpdir, "subs.srt")
            with open(subs_path, "w", encoding="utf-8") as f:
                f.write("1\n00:00:00,000 --> 00:00:59,000\n" + subtitles_text)

        logo_path = "logo.png"
        logo_exists = os.path.exists(logo_path)

        # --- Build the Base Resize/Pad Filter (1080x1920 vertical) ---
        vf_resize = (
            "scale=w=1080:h=1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
        )

        # --- TikTok-Style Subtitles ---
        if subs_path:
            # White bold font, black border, centered, safe margin
            vf_resize += (
                f",subtitles={subs_path}:force_style='FontName=Arial,FontSize=36,"
                "PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BorderStyle=1,"
                "Outline=2,Shadow=1,Alignment=2,MarginV=80'"
            )

        # --- FFmpeg Command ---
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", raw_clip]

        if logo_exists:
            # Auto-scale logo to 10% of video width (≈108px)
            ffmpeg_cmd += [
                "-i",
                logo_path,
                "-filter_complex",
                f"[1:v]scale=iw*0.1:-1[logo];"
                f"[0:v]{vf_resize}[bg];"
                f"[bg][logo]overlay=W-w-40:H-h-40",
            ]
        else:
            ffmpeg_cmd += ["-vf", vf_resize]

        ffmpeg_cmd += ["-c:a", "aac", "-b:a", "192k", output_path]

        # --- Run FFmpeg ---
        subprocess.run(ffmpeg_cmd, check=True)

        return FileResponse(output_path, media_type="video/mp4", filename="tiktok_clip.mp4")

    except subprocess.CalledProcessError as e:
        return JSONResponse({"error": f"FFmpeg failed: {e}"}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
