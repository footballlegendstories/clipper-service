from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
import subprocess, tempfile, os, yt_dlp
import imageio_ffmpeg as ffmpeg

# ✅ Ensure FFmpeg binary path is available
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg.get_ffmpeg_exe())

app = FastAPI()


@app.get("/")
def home():
    return {"status": "OK", "message": "Clipper Service is live!"}


@app.post("/clip")
async def clip_video(req: Request):
    """
    Download a YouTube video, cut the specified time segment, and return it as a file.
    Input JSON:
    {
        "videoUrl": "https://www.youtube.com/watch?v=xxxx",
        "start": "30.0",
        "end": "60.0"
    }
    """
    data = await req.json()
    video_url = data.get("videoUrl")
    start = data.get("start")
    end = data.get("end")

    # Validate inputs
    if not video_url or not start or not end:
        return JSONResponse(
            {"error": "Missing required parameters: videoUrl, start, end"},
            status_code=400,
        )

    try:
        tmpdir = tempfile.mkdtemp()
        video_path = os.path.join(tmpdir, "input.mp4")
        clip_path = os.path.join(tmpdir, "clip.mp4")

        # ✅ Download video using yt-dlp
        ydl_opts = {"outtmpl": video_path, "format": "mp4"}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # ✅ Use ffmpeg to trim the clip
        subprocess.run(
            [
                "ffmpeg",
                "-ss",
                str(start),
                "-to",
                str(end),
                "-i",
                video_path,
                "-c",
                "copy",
                clip_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # ✅ Return the video clip
        return FileResponse(clip_path, media_type="video/mp4", filename="clip.mp4")

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

