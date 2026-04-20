## Para manejo de archivos local, despliegue de la pagina
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import Depends
from fastapi.staticfiles import StaticFiles

## manejo de la base de datos postgresql
from app.database import Base, engine
from app.models.file import File as FileModel
from app.database import SessionLocal
from sqlalchemy.orm import Session

## for uploading
from app.supabase_client import supabase

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
# Base.metadata.create_all(bind=engine)

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
                supabase.storage.from_("files").remove([file.filepath])
                # log
                log_action("delete", file.filename, file.token, request=None)

                db.delete(file)

            db.commit()

        except Exception as e:
            print("Error en cleanup:", e)

        finally:
            db.close()

        await asyncio.sleep(60)


## desplegar pagina
app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

# montar archivos estaticos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# para archivos locales 
#UPLOAD_DIR = "uploads"
#os.makedirs(UPLOAD_DIR, exist_ok=True)
#FILE_STORE = {}

# Configuración de seguridad
ALLOWED_TYPES = ["image/png", "image/jpeg", "image/gif", "application/pdf"]
MAX_SIZE = 20 * 1024 * 1024  # 20MB

# 
@app.on_event("startup")
async def start_cleanup_task():
    asyncio.create_task(cleanup_expired_files())

def upload_to_supabase(file_bytes: bytes, filename: str):
    try:
        response = supabase.storage.from_("files").upload(
            path=filename,
            file=file_bytes,
            file_options={"content-type": "application/octet-stream"}
        )
        print("Supabase response:", response) 
        return response
    except Exception as e:
        print("Error", repr(e))  
        return None

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

    # Leer archivo completo
    contents = await file.read()

    if len(contents) > MAX_SIZE:
        raise HTTPException(400, "Archivo demasiado grande")

    # Nombre seguro
    safe_name = pathlib.Path(file.filename).name
    unique_name = f"{uuid.uuid4()}_{safe_name}"

    # Subir a Supabase
    response = upload_to_supabase(contents, unique_name)

    if not response:
        raise HTTPException(500, "Error subiendo archivo")

    # Generar token
    token = secrets.token_urlsafe(16)

    # Guardar en DB
    db_file = FileModel(
        filename=safe_name,
        filepath=unique_name,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )

    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    # Log
    log_action("upload", safe_name, token, request)

    return HTMLResponse(f"""
    <html>
    <head><link rel="stylesheet" href="/static/style.css"></head>
    <body>
        <div class="container">
            <h2>Archivo subido</h2>
            <a href="/download/{token}">Descargar</a>
            <br><br>
            <a href="/">Volver</a>
        </div>
    </body>
    </html>
    """)

## DOWNLOAD FILE ENDPOINT
@app.get("/download/{token}")
async def download_file(
    request: Request,
    token: str,
    db: Session = Depends(get_db)
):
    db_file = db.query(FileModel).filter(FileModel.token == token).first()

    if not db_file:
        raise HTTPException(404, "Archivo no encontrado")

    if db_file.expires_at < datetime.utcnow():
        raise HTTPException(410, "Archivo expirado")

    # Log
    log_action("download", db_file.filename, token, request)
    # test
    print("PATH GUARDADO:", repr(db_file.filepath))
    # 🔐 Generar URL firmada (expira en 60 segundos)
    signed_url = supabase.storage.from_("files").create_signed_url(
        path=db_file.filepath,
        expires_in=60
    )

    return RedirectResponse(signed_url["signedURL"])