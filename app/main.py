import os
import base64
import json
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import StreamingResponse, JSONResponse
from io import BytesIO
from weasyprint import HTML
import redis
from rq import Queue
from typing import Optional

app = FastAPI(title="PDF Service")

# Configuración desde variables de entorno
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", "5242880"))  # 5MB por defecto

# Conexión a Redis para cola de jobs
r = redis.Redis.from_url(REDIS_URL)
q = Queue("pdf_jobs", connection=r)


@app.get("/")
async def root():
    """Endpoint raíz con información del servicio."""
    return {
        "service": "PDF Conversion Service",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "sync_conversion": "/generate-pdf",
            "async_conversion": "/generate-pdf-async",
            "job_status": "/job-status/{job_id}",
            "job_result": "/job-result/{job_id}"
        }
    }


@app.get("/health")
async def health_check():
    """Endpoint de salud para verificar que el servicio está funcionando."""
    try:
        r.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "redis": "disconnected", "error": str(e)}
        )


@app.post("/generate-pdf")
async def generate_pdf(payload: dict):
    """
    Genera un PDF síncronamente desde HTML y lo devuelve directamente.
    Útil para conversiones rápidas y pequeñas.
    """
    html_content = payload.get("html", "<p>No HTML provided</p>")
    pdf_file = BytesIO()
    HTML(string=html_content).write_pdf(target=pdf_file)
    pdf_file.seek(0)
    return StreamingResponse(
        pdf_file,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=document.pdf"}
    )


@app.post("/generate-pdf-async")
async def generate_pdf_async(
    file: UploadFile = File(...),
    as_base64: bool = Form(False)
):
    """
    Envía la conversión PDF a la cola Redis para procesar con RQ worker.
    Soporta HTML, DOCX, ODT, y otros formatos compatibles con LibreOffice.
    """
    # Validar tamaño del archivo
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande. Máximo permitido: {MAX_FILE_SIZE} bytes"
        )
    
    # Preparar payload para el worker
    payload = {
        "filename": file.filename,
        "content_b64": base64.b64encode(content).decode(),
        "as_base64": as_base64
    }
    
    # Encolar job en Redis
    job = q.enqueue(
        'worker.worker.process_job',
        payload,
        job_id=None,
        result_ttl=int(os.environ.get("JOB_TTL_SECONDS", "3600")),
        failure_ttl=int(os.environ.get("JOB_TTL_SECONDS", "3600"))
    )
    
    return {
        "message": "Job encolado exitosamente",
        "job_id": job.get_id(),
        "filename": file.filename,
        "status_url": f"/job-status/{job.get_id()}",
        "result_url": f"/job-result/{job.get_id()}"
    }


@app.get("/job-status/{job_id}")
async def get_job_status(job_id: str):
    """
    Consulta el estado de un job asíncrono.
    """
    meta_key = f"pdf_meta:{job_id}"
    meta_data = r.get(meta_key)
    
    if not meta_data:
        raise HTTPException(
            status_code=404,
            detail="Job no encontrado o expirado"
        )
    
    meta = json.loads(meta_data)
    return meta


@app.get("/job-result/{job_id}")
async def get_job_result(job_id: str):
    """
    Obtiene el resultado de un job completado.
    Si el job solicitó base64, devuelve JSON con el PDF en base64.
    Si no, devuelve el PDF directamente.
    """
    meta_key = f"pdf_meta:{job_id}"
    result_key = f"pdf_result:{job_id}"
    
    meta_data = r.get(meta_key)
    if not meta_data:
        raise HTTPException(
            status_code=404,
            detail="Job no encontrado o expirado"
        )
    
    meta = json.loads(meta_data)
    
    if meta["status"] == "processing":
        raise HTTPException(
            status_code=202,
            detail="Job todavía en proceso"
        )
    
    if meta["status"] == "failed":
        raise HTTPException(
            status_code=500,
            detail={
                "error": meta.get("error", "Error desconocido"),
                "trace": meta.get("trace", "")
            }
        )
    
    # El job está completado
    result_data = r.get(result_key)
    if not result_data:
        raise HTTPException(
            status_code=404,
            detail="Resultado no encontrado"
        )
    
    pdf_b64 = result_data.decode()
    
    # Si se solicitó base64, devolver JSON
    if meta.get("as_base64", False):
        return {
            "job_id": job_id,
            "filename": meta.get("filename", "document.pdf"),
            "pdf_base64": pdf_b64,
            "status": "completed"
        }
    
    # Si no, devolver el PDF directamente
    pdf_bytes = base64.b64decode(pdf_b64)
    filename = meta.get("filename", "document.pdf")
    # Cambiar extensión a .pdf si no lo es
    if not filename.lower().endswith('.pdf'):
        filename = os.path.splitext(filename)[0] + '.pdf'
    
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """
    Elimina un job y sus resultados de Redis.
    """
    meta_key = f"pdf_meta:{job_id}"
    result_key = f"pdf_result:{job_id}"
    
    deleted = r.delete(meta_key, result_key)
    
    if deleted == 0:
        raise HTTPException(
            status_code=404,
            detail="Job no encontrado"
        )
    
    return {"message": "Job eliminado exitosamente", "job_id": job_id}