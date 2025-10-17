# PDF Conversion Service

Servicio FastAPI para convertir documentos a PDF usando WeasyPrint (HTML) y LibreOffice (DOCX, ODT, etc.) con procesamiento asíncrono mediante Redis y RQ.

## Características

- **Conversión síncrona**: Para HTML pequeño, respuesta inmediata
- **Conversión asíncrona**: Para archivos grandes o múltiples conversiones
- **Formatos soportados**: HTML, DOCX, ODT, ODP, XLS, XLSX, y más
- **Cola de trabajos**: Redis + RQ para procesamiento en background
- **Health checks**: Monitoreo del estado del servicio

## Iniciar el servicio

```bash
docker-compose up --build
```

Esto inicia:
- Redis en puerto `6380` (mapeado desde 6379 interno)
- API FastAPI en puerto `8200`
- Worker RQ para procesamiento asíncrono

## Endpoints

### 1. Health Check

```bash
curl http://localhost:8200/health
```

### 2. Conversión síncrona (HTML)

Convierte HTML a PDF inmediatamente:

```bash
curl -X POST http://localhost:8200/generate-pdf \
  -H "Content-Type: application/json" \
  -d '{"html": "<h1>Hello World</h1><p>This is a test PDF</p>"}' \
  --output document.pdf
```

### 3. Conversión asíncrona (cualquier formato)

**Subir un archivo HTML:**

```bash
curl -X POST http://localhost:8200/generate-pdf-async \
  -F "file=@documento.html" \
  -F "as_base64=false"
```

**Subir un archivo DOCX:**

```bash
curl -X POST http://localhost:8200/generate-pdf-async \
  -F "file=@documento.docx" \
  -F "as_base64=false"
```

Respuesta:
```json
{
  "message": "Job encolado exitosamente",
  "job_id": "abc123-def456",
  "filename": "documento.docx",
  "status_url": "/job-status/abc123-def456",
  "result_url": "/job-result/abc123-def456"
}
```

### 4. Consultar estado del job

```bash
curl http://localhost:8200/job-status/{job_id}
```

Respuestas posibles:
- `{"status": "processing"}` - Todavía procesando
- `{"status": "done", "filename": "...", "size_bytes": 12345}` - Completado
- `{"status": "failed", "error": "...", "trace": "..."}` - Error

### 5. Descargar resultado

```bash
curl http://localhost:8200/job-result/{job_id} --output resultado.pdf
```

Si se solicitó `as_base64=true`:
```bash
curl http://localhost:8200/job-result/{job_id}
```
Devuelve JSON:
```json
{
  "job_id": "abc123",
  "filename": "documento.pdf",
  "pdf_base64": "JVBERi0xLjQKJeLjz9...",
  "status": "completed"
}
```

### 6. Eliminar job

```bash
curl -X DELETE http://localhost:8200/job/{job_id}
```

## Variables de entorno

En `.env` puedes configurar:

```env
REDIS_URL=redis://redis:6379/0
JOB_TTL_SECONDS=3600           # Tiempo de vida de jobs (1 hora)
MAX_FILE_SIZE=5242880          # Tamaño máximo de archivo (5MB)
```

## Ejemplo con Python

```python
import requests
import time

# 1. Subir archivo para conversión asíncrona
with open("documento.docx", "rb") as f:
    response = requests.post(
        "http://localhost:8200/generate-pdf-async",
        files={"file": f},
        data={"as_base64": "false"}
    )
    
job_info = response.json()
job_id = job_info["job_id"]
print(f"Job ID: {job_id}")

# 2. Polling del estado
while True:
    status_response = requests.get(f"http://localhost:8200/job-status/{job_id}")
    status = status_response.json()
    
    print(f"Estado: {status['status']}")
    
    if status["status"] == "done":
        break
    elif status["status"] == "failed":
        print(f"Error: {status['error']}")
        exit(1)
    
    time.sleep(2)  # Esperar 2 segundos antes de consultar de nuevo

# 3. Descargar PDF
result_response = requests.get(f"http://localhost:8200/job-result/{job_id}")
with open("resultado.pdf", "wb") as f:
    f.write(result_response.content)

print("PDF descargado exitosamente")
```

## Ejemplo con JavaScript/Node.js

```javascript
const FormData = require('form-data');
const fs = require('fs');
const fetch = require('node-fetch');

async function convertToPDF() {
  // 1. Subir archivo
  const form = new FormData();
  form.append('file', fs.createReadStream('documento.docx'));
  form.append('as_base64', 'false');
  
  const uploadResponse = await fetch('http://localhost:8200/generate-pdf-async', {
    method: 'POST',
    body: form
  });
  
  const jobInfo = await uploadResponse.json();
  const jobId = jobInfo.job_id;
  console.log(`Job ID: ${jobId}`);
  
  // 2. Polling del estado
  while (true) {
    const statusResponse = await fetch(`http://localhost:8200/job-status/${jobId}`);
    const status = await statusResponse.json();
    
    console.log(`Estado: ${status.status}`);
    
    if (status.status === 'done') break;
    if (status.status === 'failed') {
      console.error(`Error: ${status.error}`);
      return;
    }
    
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  
  // 3. Descargar PDF
  const resultResponse = await fetch(`http://localhost:8200/job-result/${jobId}`);
  const pdfBuffer = await resultResponse.buffer();
  fs.writeFileSync('resultado.pdf', pdfBuffer);
  
  console.log('PDF descargado exitosamente');
}

convertToPDF();
```

## Arquitectura

```
┌─────────────┐
│   Cliente   │
└──────┬──────┘
       │
       │ HTTP Request
       ▼
┌─────────────────┐
│   FastAPI Web   │
│   (Port 8200)   │
└────────┬────────┘
         │
         │ Enqueue Job
         ▼
┌─────────────────┐
│   Redis Queue   │
│   (Port 6379)   │
└────────┬────────┘
         │
         │ Process Job
         ▼
┌─────────────────┐
│   RQ Worker     │
│  (Background)   │
└─────────────────┘
```

## Logs

Para ver los logs del worker:

```bash
docker-compose logs -f worker
```

Para ver los logs de la API:

```bash
docker-compose logs -f web
```

## Scripts de prueba

### Test completo
```bash
python test_service.py
```

### Test rápido
```bash
chmod +x quick_test.sh
./quick_test.sh
```

### Usando Makefile
```bash
make help      # Ver comandos disponibles
make up        # Iniciar servicios
make test      # Ejecutar tests
make logs      # Ver logs
make clean     # Limpiar todo
```

## Troubleshooting

### El worker no procesa jobs

**Síntomas:**
- Los jobs se quedan en estado "processing" indefinidamente
- No hay logs del worker procesando el job

**Soluciones:**
```bash
# 1. Verificar que el worker está corriendo
docker-compose ps

# 2. Ver logs del worker
docker-compose logs -f worker

# 3. Verificar que Redis está accesible
docker exec pdf_redis redis-cli ping

# 4. Ver jobs en la cola
docker exec pdf_redis redis-cli LLEN rq:queue:pdf_jobs

# 5. Reiniciar el worker
docker-compose restart worker
```

### Conversión de DOCX/ODT falla

**Síntomas:**
- Job pasa a estado "failed"
- Error relacionado con LibreOffice en los logs

**Soluciones:**
```bash
# 1. Ver el error específico
curl http://localhost:8200/job-status/{job_id}

# 2. Verificar que LibreOffice está instalado
docker exec pdf_worker libreoffice --version

# 3. Probar conversión manualmente
docker exec pdf_worker libreoffice --headless --convert-to pdf /path/to/file.docx

# 4. Aumentar timeout si el archivo es grande
# Editar app/converter.py y cambiar timeout=120 a un valor mayor
```

### Job no encontrado (404)

**Causa:** Los jobs expiran después de `JOB_TTL_SECONDS` (default: 3600s = 1 hora)

**Soluciones:**
```bash
# Aumentar TTL en .env
echo "JOB_TTL_SECONDS=7200" >> .env  # 2 horas
docker-compose restart
```

### Error de memoria o disco

**Síntomas:**
- Conversiones fallan con archivos grandes
- Error "No space left on device"

**Soluciones:**
```bash
# 1. Aumentar límite de tamaño de archivo
echo "MAX_FILE_SIZE=10485760" >> .env  # 10MB
docker-compose restart

# 2. Limpiar archivos temporales de Docker
docker system prune -a

# 3. Aumentar memoria del contenedor (docker-compose.yml)
# Añadir bajo cada servicio:
#   deploy:
#     resources:
#       limits:
#         memory: 1G
```

### Puerto ya en uso

**Síntomas:**
- Error al iniciar: "port is already allocated"

**Soluciones:**
```bash
# Cambiar puerto en docker-compose.yml
# Cambiar "8200:8200" a "8201:8200" (o cualquier puerto libre)

# O detener el servicio que usa el puerto
lsof -ti:8200 | xargs kill -9
```

### Redis connection refused

**Síntomas:**
- Error "Connection refused" al conectar con Redis

**Soluciones:**
```bash
# 1. Verificar que Redis está corriendo
docker-compose ps redis

# 2. Verificar logs de Redis
docker-compose logs redis

# 3. Reiniciar Redis
docker-compose restart redis

# 4. Si persiste, verificar URL de Redis
docker exec pdf_web env | grep REDIS_URL
```

### Debug modo interactivo

Para depurar problemas en el worker:
```bash
# 1. Detener el worker
docker-compose stop worker

# 2. Ejecutar worker en modo interactivo
docker-compose run --rm worker python worker/worker.py

# Ahora verás todos los logs en tiempo real
```

## Monitoreo

### Ver estado de Redis
```bash
# Conectar a Redis CLI
docker exec -it pdf_redis redis-cli

# Comandos útiles:
> INFO                              # Información del servidor
> DBSIZE                           # Número de keys
> KEYS pdf_meta:*                  # Ver metadata de jobs
> GET pdf_meta:{job_id}            # Ver estado de un job específico
> LLEN rq:queue:pdf_jobs           # Jobs pendientes en cola
> KEYS rq:job:*                    # Ver todos los jobs RQ
```

### Logs en tiempo real
```bash
# Todos los servicios
docker-compose logs -f

# Solo web
docker-compose logs -f web

# Solo worker
docker-compose logs -f worker

# Últimas 100