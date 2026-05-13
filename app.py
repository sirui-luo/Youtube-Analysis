"""
FastAPI web app for YouTube Trend Analyzer.
Run with: uvicorn app:app --reload
"""

import asyncio
import base64
import json
import os
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tools"))

import niche_store

app = FastAPI(title="YouTube Trend Analyzer")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# In-memory job store (MVP — no database needed)
jobs: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze")
async def start_analysis(topic: str = Form(...)):
    """Start a pipeline run. Returns a job_id immediately."""
    if not topic.strip():
        return JSONResponse({"error": "Topic cannot be empty"}, status_code=400)

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "running",
        "topic": topic.strip(),
        "progress": [],
        "result": None,
        "error": None,
    }

    thread = threading.Thread(target=_run_pipeline, args=(topic.strip(), job_id), daemon=True)
    thread.start()

    return {"job_id": job_id}


@app.get("/stream/{job_id}")
async def stream_progress(job_id: str):
    """Server-Sent Events endpoint for live progress updates."""
    async def event_generator():
        sent = 0
        while True:
            job = jobs.get(job_id)
            if not job:
                yield f"data: {json.dumps({'step': 'error', 'message': 'Job not found'})}\n\n"
                break

            progress = job["progress"]
            while sent < len(progress):
                yield f"data: {json.dumps(progress[sent])}\n\n"
                sent += 1

            if job["status"] in ("done", "error"):
                payload = {"step": job["status"], "message": job.get("error") or "Done"}
                yield f"data: {json.dumps(payload)}\n\n"
                break

            await asyncio.sleep(0.4)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/results/{job_id}")
async def get_results(job_id: str):
    """Return the full analysis JSON for a completed job."""
    job = jobs.get(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return JSONResponse(job)


@app.get("/report/{job_id}", response_class=HTMLResponse)
async def report_page(request: Request, job_id: str):
    """Serve the report HTML page for a given job."""
    job = jobs.get(job_id)
    topic = job["topic"] if job else ""
    return templates.TemplateResponse(
        "report.html", {"request": request, "job_id": job_id, "topic": topic}
    )


@app.get("/create-post", response_class=HTMLResponse)
async def create_post_page(request: Request, job_id: str = "", titles: str = "[]"):
    """Serve the post generator page."""
    return templates.TemplateResponse(
        "create_post.html", {"request": request, "job_id": job_id, "titles_json": titles}
    )


@app.post("/generate-post")
async def generate_post_route(
    photos: List[UploadFile] = File(...),
    ideas: str = Form(""),
    platform: str = Form(...),
    tone: str = Form(""),
    rednote_style: str = Form("图文"),
    video_titles: str = Form("[]"),
):
    """Generate a post caption and photo order via Claude Vision."""
    if not photos:
        return JSONResponse({"error": "At least one photo is required"}, status_code=400)

    from generate_post import main as generate_post

    titles = json.loads(video_titles)
    photos_b64 = [base64.b64encode(await p.read()).decode() for p in photos]

    try:
        result = generate_post(photos_b64, titles, ideas, platform, tone, rednote_style)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/niches")
async def get_niches():
    return JSONResponse(niche_store.list_niches())


@app.post("/niches")
async def create_niche(topic: str = Form(...), job_id: str = Form(...)):
    job = jobs.get(job_id)
    if not job or job.get("status") != "done" or not job.get("result"):
        return JSONResponse({"error": "Job not found or not complete"}, status_code=400)
    niche = niche_store.save_niche(topic, job["result"])
    return JSONResponse(niche)


@app.get("/niches/{niche_id}/result")
async def get_niche_result(niche_id: str):
    result = niche_store.get_niche_result(niche_id)
    if result is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(result)


# Must be defined BEFORE /{niche_id} routes to avoid path conflict
@app.patch("/niches/reorder")
async def reorder_niches(request: Request):
    body = await request.json()
    niche_store.reorder_niches(body.get("ids", []))
    return JSONResponse({"ok": True})


@app.patch("/niches/{niche_id}")
async def rename_niche(niche_id: str, request: Request):
    body = await request.json()
    try:
        niche = niche_store.rename_niche(niche_id, body.get("name", ""))
        return JSONResponse(niche)
    except KeyError:
        return JSONResponse({"error": "Not found"}, status_code=404)


@app.delete("/niches/{niche_id}")
async def delete_niche(niche_id: str):
    try:
        niche_store.delete_niche(niche_id)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/niches/{niche_id}/refresh")
async def refresh_niche(niche_id: str):
    niche = niche_store.get_niche(niche_id)
    if not niche:
        return JSONResponse({"error": "Not found"}, status_code=404)
    niche_store.set_refreshing(niche_id, True)
    thread = threading.Thread(target=_refresh_niche_pipeline, args=(niche_id, niche["name"]), daemon=True)
    thread.start()
    return JSONResponse({"status": "refreshing"})


@app.get("/niche-report/{niche_id}", response_class=HTMLResponse)
async def niche_report_page(request: Request, niche_id: str):
    niche = niche_store.get_niche(niche_id)
    topic = niche["name"] if niche else ""
    return templates.TemplateResponse(
        "report.html", {"request": request, "job_id": "", "niche_id": niche_id, "topic": topic}
    )


_INSTAGRAM_TONES = ["Aesthetic", "Engagement", "Casual"]
_REDNOTE_STYLES  = ["图文", "种草"]


@app.post("/generate-variants")
async def generate_variants_route(
    photos: List[UploadFile] = File(...),
    ideas: str = Form(""),
    platform: str = Form(...),
    video_titles: str = Form("[]"),
):
    """Generate all caption variants in parallel (3 for Instagram, 2 for RedNote)."""
    if not photos:
        return JSONResponse({"error": "At least one photo is required"}, status_code=400)

    from generate_post import main as generate_post

    titles = json.loads(video_titles)
    photos_b64 = [base64.b64encode(await p.read()).decode() for p in photos]

    if platform == "instagram":
        configs = [("instagram", tone, "") for tone in _INSTAGRAM_TONES]
    else:
        configs = [("rednote", "", style) for style in _REDNOTE_STYLES]

    def call(cfg):
        plat, tone, rn_style = cfg
        result = generate_post(photos_b64, titles, ideas, plat, tone, rn_style)
        result["tone"] = tone if plat == "instagram" else rn_style
        return result

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        tasks = [loop.run_in_executor(pool, call, cfg) for cfg in configs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    out = [{"error": str(v)} if isinstance(v, Exception) else v for v in results]
    return JSONResponse(out)


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _run_pipeline(topic: str, job_id: str):
    from web_pipeline import run_web_pipeline

    def progress_callback(step: str, message: str):
        jobs[job_id]["progress"].append({"step": step, "message": message})

    try:
        result = run_web_pipeline(topic, job_id, progress_callback)
        jobs[job_id]["status"] = "done"
        jobs[job_id]["result"] = result
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


def _refresh_niche_pipeline(niche_id: str, topic: str):
    from web_pipeline import run_web_pipeline

    try:
        result = run_web_pipeline(topic, f"niche_{niche_id}", lambda *_: None)
        niche_store.update_niche(niche_id, result)
    except Exception:
        niche_store.set_refreshing(niche_id, False)
