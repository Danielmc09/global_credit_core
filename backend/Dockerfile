# ============================================
# Stage 1: Builder - Instalar dependencias
# ============================================
FROM python:3.11-slim as builder

WORKDIR /app

# Instalar dependencias del sistema necesarias para compilar
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements y instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================
# Stage 2: Runtime - Imagen final optimizada
# ============================================
FROM python:3.11-slim

WORKDIR /app

# Instalar solo dependencias de runtime (sin compiladores)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependencias instaladas desde el builder
COPY --from=builder /root/.local /root/.local

# Copiar el código de la aplicación
COPY . .

# Crear usuario no-root para seguridad
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Copiar paquetes a un directorio accesible por appuser
RUN cp -r /root/.local /home/appuser/.local && \
    chown -R appuser:appuser /home/appuser/.local

# Asegurar que los scripts estén en el PATH
ENV PATH=/home/appuser/.local/bin:$PATH

USER appuser

# Exponer puerto
EXPOSE 8000

# El comando se define en docker-compose.yml
