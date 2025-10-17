import os
import base64
import json
import traceback
import sys
from redis import Redis
from rq import Worker, Queue, Connection

# Asegurar que el path está configurado
sys.path.insert(0, '/app')

from app.converter import html_to_pdf_bytes, libreoffice_convert_bytes

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
redis_conn = Redis.from_url(REDIS_URL)
RESULT_TTL = int(os.environ.get("JOB_TTL_SECONDS", "3600"))


def process_job(payload, job_id=None):
    """
    Procesa un job de conversión a PDF.
    
    Args:
        payload: Dict con 'filename', 'content_b64', y opcionalmente 'as_base64'
        job_id: ID del job (opcional, lo obtiene RQ automáticamente)
    """
    # Si job_id no se pasa, intentar obtenerlo del contexto RQ
    if job_id is None:
        from rq import get_current_job
        job = get_current_job()
        job_id = job.id if job else "unknown"
    
    meta_key = f"pdf_meta:{job_id}"
    result_key = f"pdf_result:{job_id}"
    
    try:
        # Actualizar estado a "processing"
        redis_conn.set(
            meta_key,
            json.dumps({"status": "processing"}),
            ex=RESULT_TTL
        )
        
        # Extraer información del payload
        filename = payload.get("filename", "document")
        content_b64 = payload.get("content_b64")
        as_base64 = payload.get("as_base64", False)
        
        if not content_b64:
            raise ValueError("Falta 'content_b64' en el payload")
        
        # Decodificar contenido
        content = base64.b64decode(content_b64)
        
        # Determinar tipo de conversión según extensión
        ext = os.path.splitext(filename)[1].lower()
        
        print(f"[Worker] Procesando archivo: {filename} (extensión: {ext})")
        
        if ext in (".html", ".htm"):
            # Conversión HTML a PDF con WeasyPrint
            html_string = content.decode("utf-8", errors="ignore")
            pdf_bytes = html_to_pdf_bytes(html_string)
        else:
            # Conversión con LibreOffice para DOCX, ODT, etc.
            pdf_bytes = libreoffice_convert_bytes(content, filename)
        
        # Guardar resultado en Redis como base64
        pdf_b64 = base64.b64encode(pdf_bytes).decode()
        redis_conn.set(result_key, pdf_b64, ex=RESULT_TTL)
        
        # Actualizar metadata a "done"
        redis_conn.set(
            meta_key,
            json.dumps({
                "status": "done",
                "filename": filename,
                "as_base64": as_base64,
                "size_bytes": len(pdf_bytes)
            }),
            ex=RESULT_TTL
        )
        
        print(f"[Worker] Job {job_id} completado exitosamente")
        
    except Exception as e:
        # Capturar traceback completo
        tb = traceback.format_exc()
        error_msg = str(e)
        
        print(f"[Worker] Error en job {job_id}: {error_msg}")
        print(tb)
        
        # Guardar error en Redis
        redis_conn.set(
            meta_key,
            json.dumps({
                "status": "failed",
                "error": error_msg,
                "trace": tb
            }),
            ex=RESULT_TTL
        )
        
        # Re-lanzar la excepción para que RQ la registre
        raise


if __name__ == "__main__":
    print(f"[Worker] Iniciando worker conectado a {REDIS_URL}")
    print(f"[Worker] TTL de resultados: {RESULT_TTL} segundos")
    
    try:
        with Connection(redis_conn):
            q = Queue("pdf_jobs")
            worker = Worker([q], connection=redis_conn)
            print("[Worker] Worker listo para procesar jobs")
            print(f"[Worker] Escuchando cola: pdf_jobs")
            worker.work(with_scheduler=True)
    except KeyboardInterrupt:
        print("\n[Worker] Cerrando worker...")
    except Exception as e:
        print(f"[Worker] Error fatal: {e}")
        traceback.print_exc()
        sys.exit(1)