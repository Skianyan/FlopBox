## Para manejo de archivos local, despliegue de la pagina
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi import Depends
from fastapi.staticfiles import StaticFiles

## manejo de la base de datos postgresql
from app.database import Base, engine
from app.models.file import File as FileModel
from app.database import SessionLocal
from sqlalchemy.orm import Session

## funcion de log
from app.services.logs import log_action

import asyncio
import secrets
from datetime import datetime, timedelta

import os
import uuid
import pathlib
import secrets

# manejo de bd.
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

## limpieza de archivos expirados

async def cleanup_expired_files():
    while True:
        print("Revisando archivos expirados...")

        db = SessionLocal()

        try:
            expired_files = db.query(FileModel).filter(
                FileModel.expires_at < datetime.utcnow()
            ).all()

            for file in expired_files:
                # Eliminar archivo físico
                if os.path.exists(file.filepath):
                    os.remove(file.filepath)
                    print(f"Eliminado archivo: {file.filepath}")

                # Eliminar de DB
                db.delete(file)

            db.commit()

        except Exception as e:
            print("Error en cleanup:", e)

        finally:
            log_action("delete", file.filename, file.token, request=None)
            db.close()

        # Esperar 60 segundos
        await asyncio.sleep(60)


## desplegar pagina
app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

# montar archivos estaticos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

FILE_STORE = {}

# Configuración de seguridad
ALLOWED_TYPES = ["image/png", "image/jpeg", "image/gif", "application/pdf"]
MAX_SIZE = 5 * 1024 * 1024  # 5MB

# 
@app.on_event("startup")
async def start_cleanup_task():
    asyncio.create_task(cleanup_expired_files())

#### ENDPOINTS ####

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
    request: Request,
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

    # Guardar Log
    log_action("upload", safe_name, token, request)

    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    return HTMLResponse(f"""
        <html>
        <head>
        <link rel="stylesheet" href="/static/style.css">
        </head>
        <body>
            <div class="container">
                <h2>Archivo subido de manera exitosa</h2>
                <p>Tu enlace de descarga:</p>
                <a class="download" href="/download/{token}" target="_blank">
                    Descargar
                </a>
                <br><br><br>
                <a class="download" href="/">⬅ Volver</a>
            </div>
        </body>
        </html>
    """)

## DOWNLOAD FILE ENDPOINT
@app.get("/download/{token}")
async def download_file(
    request: Request,
    token: str, 
    db: Session = Depends(get_db)):

    db_file = db.query(FileModel).filter(FileModel.token == token).first()

    if not db_file:
        raise HTTPException(404, "Archivo no encontrado")

    # Validar expiración
    if db_file.expires_at < datetime.utcnow():
        raise HTTPException(410, "Archivo expirado")

    if not os.path.exists(db_file.filepath):
        raise HTTPException(404, "Archivo no disponible")

    ## Mandar Log
    log_action("download", db_file.filename, token, request)

    return FileResponse(
        path=db_file.filepath,
        filename=db_file.filename,
        media_type="application/octet-stream"
    )