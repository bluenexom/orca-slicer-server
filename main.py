import os
import time
import uuid
import shutil
import tempfile
import threading
from typing import Annotated
from slice import FILAMENTS, LAYER_HEIGHT, slice_model
from fastapi import FastAPI,File,Form,UploadFile,HTTPException,BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

# Finished jobs are kept this long so the webapp can still read the result, then forgotten
JOB_TTL_SECONDS = 60 * 60

app = FastAPI()

# Only one Orca at a time: one slice already uses every CPU core, so two at once would each take twice as long
slice_lock = threading.Lock()

# job_id → {"status": "queued" | "running" | "done" | "failed", "created": time, + "grams"/"seconds" or "error"}
# Kept in memory only: a restart forgets all jobs (fine for the demo; the real backend will store them).
jobs = {}
# The background slices and the requests both change `jobs`, from different threads
jobs_lock = threading.Lock()

app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "POST"],
        )

def forget_old_jobs():
    now = time.time()
    with jobs_lock:
        for job_id, job in list(jobs.items()):
            if job["status"] in ("done", "failed") and now - job["created"] > JOB_TTL_SECONDS:
                del jobs[job_id]

def update_job(job_id, **changes):
    with jobs_lock:
        jobs[job_id].update(changes)

# Runs after POST /slice has already answered, so a long slice never keeps a request open
# (Cloudflare cuts requests off after ~100 s)
def run_job(job_id, folder, path, filament, layer_height, infill):
    try:
        with slice_lock:
            update_job(job_id, status="running")
            grams, seconds = slice_model(path, filament, layer_height, infill)
        update_job(job_id, status="done", grams=grams, seconds=seconds)
    except Exception as e:
        # Any error, not only Orca's: otherwise the job would stay "running" forever and the webapp would wait for nothing
        update_job(job_id, status="failed", error=str(e))
    finally:
        # The upload is only needed for the slice
        shutil.rmtree(folder, ignore_errors=True)

# Starts a slice and answers right away with the job's id; the webapp then asks GET /slice/{id} until it's done
@app.post("/slice", status_code=202)
def slice_endpoint(
        background_tasks: BackgroundTasks,
        model: Annotated[UploadFile,File()],
        filament: Annotated[str, Form()],
        infill: Annotated[int, Form(ge=0,le=100)],
        layer_height: Annotated[str, Form()],
        ):

    if filament not in FILAMENTS:
        raise HTTPException(status_code=422, detail="Unsupported filament")

    if layer_height not in LAYER_HEIGHT:
        raise HTTPException(status_code=422, detail="Unsupported layer height")

    ext = os.path.splitext(model.filename or "")[1].lower()

    if ext not in [".stl",".3mf"]:
        raise HTTPException(status_code=422, detail="Unsupported file format")

    forget_old_jobs()

    # Not TemporaryDirectory: the folder must outlive this request, run_job deletes it when the slice is done
    folder = tempfile.mkdtemp()
    path = os.path.join(folder,"model"+ext)
    with open(path,"wb") as f:
        shutil.copyfileobj(model.file, f)

    job_id = uuid.uuid4().hex   # random, so nobody can guess another customer's job
    with jobs_lock:
        jobs[job_id] = {"status": "queued", "created": time.time()}
    background_tasks.add_task(run_job, job_id, folder, path, filament, layer_height, infill)
    return {"id": job_id}

# The job's status; "grams" and "seconds" once it's done, "error" if it failed
@app.get("/slice/{job_id}")
def job_status(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            # Unknown, forgotten after JOB_TTL_SECONDS, or lost in a server restart
            raise HTTPException(status_code=404, detail="Unknown job")
        return {key: value for key, value in job.items() if key != "created"}
