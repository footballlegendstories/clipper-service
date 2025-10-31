from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
import subprocess, tempfile, os, yt_dlp

app = FastAPI()

@app.post("/clip")
async def clip_video(req: Request):
    data = await req.json()
    video_url = data.get("videoUrl")
    start = data.get("start")
    end = data.get("end")

    if not video_url or not start or not end:
        return JSONResponse({"error": "Missing required parameters"}, status_code=400)

    tmpdir = tempfile.mkdtemp()
    video_path = os.path.join(tmpdir, "input.mp4")
    clip_path = os.path.join(tmpdir, "clip.mp4")

    # Download YouTube video
    ydl_opts = {"outtmpl": video_path, "format": "mp4"}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    # Cut the clip
    subprocess.run([
        "ffmpeg", "-ss", str(start), "-to", str(end),
        "-i", video_path, "-c", "copy", clip_path
    ], check=True)

    return FileResponse(clip_path, media_type="video/mp4", filename="clip.mp4")
