# FlopBox
Aplicación de transferencia de archivos para la clase de Desarrollo Backend II

## Features
Subida de archivos.
Generación de enlaces de descarga para los archivos.
Tamaño máximo de 5 MB.
Archivos se borran automáticamente despues de 24 Hrs.
Archivos de tipo png, jpeg, gif y pdfs.
Guardar logs en base de datos Postgresql y en Supabase


uvicorn app.main:app --reload
