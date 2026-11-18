import os
import shutil
import tempfile
import threading
from typing import Annotated
from slice import FILAMENTS, LAYER_HEIGHT, slice_model
from fastapi import FastAPI,File,Form,UploadFile,HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
slice_lock = threading.Lock()

app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["POST"],
        )

@app.post("/slice")
def slice_endpoint(
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

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp,"model"+ext)
        with open(path,"wb") as f:
            shutil.copyfileobj(model.file, f)
        try:
            with slice_lock:
                grams,seconds = slice_model(path, filament,layer_height,infill)
                return {"grams": grams, "seconds":seconds}
        except RuntimeError as e:
            raise HTTPException(status_code=500,detail=str(e))
