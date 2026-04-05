from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from app.database import Base, engine
from app.models.file import File as FileModel
from app.database import SessionLocal
from sqlalchemy.orm import Session
from fastapi import Depends
from datetime import datetime
import secrets
from datetime import datetime, timedelta

import os
import uuid
import pathlib
import secrets

# crear bd
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

FILE_STORE = {}

# Configuración de seguridad
ALLOWED_TYPES = ["image/png", "image/jpeg", "image/gif", "application/pdf"]
MAX_SIZE = 5 * 1024 * 1024  # 5MB

## HOME 
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )

## UPLOAD FILE ENDPOINT
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Validar tipo
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Tipo no permitido")

    # Nombre seguro
    safe_name = pathlib.Path(file.filename).name
    unique_name = f"{uuid.uuid4()}_{safe_name}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    # Guardar archivo (streaming)
    size = 0
    chunk_size = 1024 * 1024

    with open(file_path, "wb") as buffer:
        while chunk := await file.read(chunk_size):
            size += len(chunk)
            if size > MAX_SIZE:
                buffer.close()
                os.remove(file_path)
                raise HTTPException(400, "Archivo demasiado grande")
            buffer.write(chunk)

    # Generar token
    token = secrets.token_urlsafe(16)

    # Guardar en DB
    db_file = FileModel(
        filename=safe_name,
        filepath=file_path,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )

    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    return HTMLResponse(f"""
        <h2>Archivo subido</h2>
        <a href="/download/{token}">Descargar archivo</a>
    """)

## DOWNLOAD FILE ENDPOINT
@app.get("/download/{token}")
async def download_file(token: str, db: Session = Depends(get_db)):

    db_file = db.query(FileModel).filter(FileModel.token == token).first()

    if not db_file:
        raise HTTPException(404, "Archivo no encontrado")

    # Validar expiración
    if db_file.expires_at < datetime.utcnow():
        raise HTTPException(410, "Archivo expirado")

    if not os.path.exists(db_file.filepath):
        raise HTTPException(404, "Archivo no disponible")

    return FileResponse(
        path=db_file.filepath,
        filename=db_file.filename,
        media_type="application/octet-stream"
    )