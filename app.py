from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
import subprocess, tempfile, os, yt_dlp, imageio_ffmpeg as ffmpeg

# Ensure ffmpeg binary path is available
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg.get_ffmpeg_exe())

app = FastAPI()

@app.get("/")
def home():
    return {"status": "OK", "message": "Clipper Service is live!"}

@app.post("/clip")
async def clip_video(req: Request):
    """
    Create a TikTok/Reels-style clip: vertical 9:16, logo overlay, subtitles.
    Input JSON:
    {
      "videoUrl": "https://youtube.com/watch?v=xxxx",
      "start": "30.0",
      "end": "60.0",
      "subtitles": "Optional text to add as captions"
    }
    """
    data = await req.json()
    video_url = data.get("videoUrl")
    start = data.get("start")
    end = data.get("end")
    subtitles_text = data.get("subtitles")

    if not video_url or not start or not end:
        return JSONResponse({"error": "Missing videoUrl/start/end"}, status_code=400)

    try:
        tmpdir = tempfile.mkdtemp()
        video_path = os.path.join(tmpdir, "input.mp4")
        raw_clip = os.path.join(tmpdir, "clip_raw.mp4")
        output_clip = os.path.join(tmpdir, "clip_final.mp4")

        cookie_file = "youtube_cookies.txt"
        ydl_opts = {"outtmpl": video_path, "format": "mp4"}
        if os.path.exists(cookie_file):
            ydl_opts["cookiefile"] = cookie_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Step 1: Cut the raw clip
        subprocess.run(
            ["ffmpeg", "-ss", str(start), "-to", str(end),
             "-i", video_path, "-c", "copy", raw_clip],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Step 2: Prepare optional subtitles
        subs_path = None
        if subtitles_text:
            subs_path = os.path.join(tmpdir, "subs.srt")
            with open(subs_path, "w", encoding="utf-8") as f:
                f.write("1\n00:00:00,000 --> 00:00:59,000\n" + subtitles_text)

        # Step 3: Build ffmpeg filters
        filters = ["crop=(ih*9/16):ih,scale=1080:1920"]
        logo_path = "logo.png"
        if os.path.exists(logo_path):
            filters.append(f"movie={logo_path}[wm];[in][wm]overlay=W-w-50:H-h-50[out]")
        if subs_path:
            filters.append(f"subtitles={subs_path}")

        vf = ",".join(filters)

        cmd = ["ffmpeg", "-i", raw_clip, "-vf", vf,
               "-c:a", "copy", output_clip]

        subprocess.run(cmd, check=True)

        return FileResponse(output_clip, media_type="video/mp4", filename="tiktok_clip.mp4")

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
