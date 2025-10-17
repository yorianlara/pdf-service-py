# ----------------------------
# Dockerfile para FastAPI + Worker PDF
# ----------------------------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev libxml2 libxslt1.1 \
    ca-certificates fonts-dejavu-core fonts-dejavu-extra \
    build-essential wget unzip \
 && rm -rf /var/lib/apt/lists/*

# Crear directorio de la app
WORKDIR /app

# Copiar requirements y instalar
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copiar toda la aplicación
COPY . /app

# Variables de entorno para worker
ENV PYTHONPATH=/app

# Exponer puerto de la API
EXPOSE 8200

# CMD por defecto (puedes sobreescribirlo en docker-compose para web/worker)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8200", "--proxy-headers"]

