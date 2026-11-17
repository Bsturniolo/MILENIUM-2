# Servidor de Milenium 2 (módulos de máquinas + la app en /app/).
# Se construye desde la raíz del repo:  docker build -t milenium2 .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MILENIUM_DB=/datos/milenium.db

WORKDIR /srv
COPY modulos/servidor/requirements.txt modulos/servidor/requirements.txt
RUN pip install --no-cache-dir -r modulos/servidor/requirements.txt

COPY modulos/servidor/app.py modulos/servidor/firmas.py modulos/servidor/
COPY index.html ./

# Corre sin permisos de administrador; la base vive en /datos (un volumen que no se borra).
RUN useradd --system --uid 10001 milenium && mkdir -p /datos && chown milenium /datos
USER milenium
VOLUME ["/datos"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/salud', timeout=4)"

WORKDIR /srv/modulos/servidor
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
