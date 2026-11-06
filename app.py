import os, uuid, subprocess, shutil
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).parent.resolve()
UPLOADS = BASE / "uploads"
OUTPUTS = BASE / "outputs"
UPLOADS.mkdir(exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)

app = FastAPI(title="ClipMaster AI")
app.mount("/outputs", StaticFiles(directory=OUTPUTS), name="outputs")

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-2500:])
    return p.stdout

def probe_duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    return float(out.strip())

def transcribe(path: Path, language: str = "es"):
    try:
        from faster_whisper import WhisperModel
        model_name = os.getenv("WHISPER_MODEL", "base")
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(path), language=language, vad_filter=True)
        return [{"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
                for s in segments if s.text.strip()]
    except ImportError:
        return None

def make_srt(segments, start, end, destination):
    selected = [s for s in segments if s["end"] > start and s["start"] < end]
    def stamp(seconds):
        ms = int(max(0, seconds) * 1000)
        h, rem = divmod(ms, 3600000)
        m, rem = divmod(rem, 60000)
        sec, milli = divmod(rem, 1000)
        return f"{h:02}:{m:02}:{sec:02},{milli:03}"
    with open(destination, "w", encoding="utf-8") as f:
        for i, s in enumerate(selected, 1):
            a, b = max(0, s["start"] - start), min(end-start, s["end"] - start)
            f.write(f"{i}\\n{stamp(a)} --> {stamp(b)}\\n{s['text']}\\n\\n")

@app.get("/", response_class=HTMLResponse)
def home():
    return (BASE / "static" / "index.html").read_text(encoding="utf-8")

@app.post("/api/create")
async def create_clips(video: UploadFile = File(...),
                       clip_seconds: int = Form(35),
                       number_clips: int = Form(5),
                       language: str = Form("es"),
                       captions: bool = Form(True)):
    if not video.filename or Path(video.filename).suffix.lower() not in {".mp4", ".mov", ".m4v", ".mkv", ".webm"}:
        raise HTTPException(400, "Formato no compatible. Usa MP4, MOV, MKV o WEBM.")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise HTTPException(500, "FFmpeg y FFprobe deben estar instalados en el servidor.")
    job = uuid.uuid4().hex[:10]
    safe_name = Path(video.filename).name.replace(" ", "_")
    source = UPLOADS / f"{job}_{safe_name}"
    with source.open("wb") as f:
        while chunk := await video.read(1024 * 1024):
            f.write(chunk)
    try:
        duration = probe_duration(source)
        if duration <= 0:
            raise ValueError("No se pudo leer la duración del video.")
        clip_seconds = max(15, min(int(clip_seconds), 90))
        number_clips = max(1, min(int(number_clips), 20))
        transcript = transcribe(source, language) if captions else None

        # Distribuye los clips a lo largo del video. Si hay transcripción,
        # prioriza ventanas con más palabras; es una selección inicial, no una promesa viral.
        starts = []
        if transcript:
            step = max(clip_seconds, duration / number_clips)
            candidates = []
            for i in range(number_clips * 3):
                st = max(0, min(duration - clip_seconds, i * max(1, (duration-clip_seconds)/max(1, number_clips*3-1))))
                words = sum(len(s["text"].split()) for s in transcript if s["end"] > st and s["start"] < st + clip_seconds)
                candidates.append((words, st))
            candidates.sort(reverse=True)
            for _, st in candidates:
                if all(abs(st-x) > clip_seconds*0.7 for x in starts):
                    starts.append(st)
                if len(starts) >= number_clips: break
        if not starts:
            if duration <= clip_seconds:
                starts = [0]
            else:
                starts = [i * (duration-clip_seconds) / max(1, number_clips-1)
                          for i in range(number_clips)]
        starts = sorted(starts)

        results = []
        for idx, st in enumerate(starts, 1):
            length = min(clip_seconds, duration-st)
            out = OUTPUTS / f"{job}_clip_{idx:02}.mp4"
            filters = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
            srt_path = OUTPUTS / f"{job}_{idx:02}.srt"
            if transcript:
                make_srt(transcript, st, st+length, srt_path)
                # FFmpeg subtitles filter requires escaped path; use relative safe filename.
                subtitle_filter = f"subtitles={str(srt_path).replace(':', r'\\:')}:force_style='FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=100'"
                filters += "," + subtitle_filter
            cmd = ["ffmpeg", "-y", "-ss", str(st), "-i", str(source), "-t", str(length),
                   "-vf", filters, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                   "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)]
            run(cmd)
            results.append({"name": f"Clip {idx}", "url": f"/outputs/{out.name}",
                            "start": round(st, 1), "duration": round(length, 1)})
            if srt_path.exists(): srt_path.unlink()
        return {"job_id": job, "clips": results,
                "captions_available": bool(transcript),
                "message": "Clips creados. " + ("" if transcript else "Para subtítulos instala faster-whisper y activa subtítulos.")}
    except Exception as e:
        raise HTTPException(500, f"No se pudo procesar el video: {e}")
    finally:
        try: source.unlink()
        except OSError: pass
