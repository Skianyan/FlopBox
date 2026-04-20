# FlopBox
Aplicación de transferencia de archivos para la clase de Desarrollo Backend II

## Features
- Subida de archivos. <br>
- Generación de enlaces de descarga para los archivos. <br>
- Tamaño máximo de 5 MB. <br>
- Archivos se borran automáticamente despues de 24 Hrs. <br>
- Archivos de tipo png, jpeg, gif y pdfs. <br>
- Guardar logs en base de datos Postgresql y en Supabase. <br>

## Como correr el proyecto
- Crear base de datos postgres (flopbox) <br>

psql -U postgres <br>
CREATE DATABASE flopbox; <br>

- Crear venv para proyecto e instalar requerimientos. <br>

python -m venv venv <br>
pip install -r requirements.txt <br>

- Correr el proyecto <br>

uvicorn app.main:app --reload
