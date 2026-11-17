# Subir el servidor a la nube (cuando llegue el momento)

> **Estado al 17/11/2026:** todavía no se contrató ni se subió nada. Todo lo necesario ya está en el repo y probado en la compu, así que el día que se decida son unos 30 minutos.

## Qué se sube y qué no

- **Se sube:** el servidor de módulos, que además sirve la app en `https://tu-dominio/app/`.
- **No hace falta subir:** la app en GitHub Pages sigue funcionando igual y se conecta a este servidor.
- **HTTPS:** lo saca y lo renueva solo Caddy, gratis, con Let's Encrypt.
- **Datos:** la base queda en un volumen de Docker que no se borra al reiniciar o actualizar.

## Qué hay que contratar

| Qué | Para qué | Comentario |
| --- | --- | --- |
| Un servidor virtual (VPS) con Linux (Ubuntu 24.04), 1 GB de RAM | Que el servidor esté prendido las 24 horas | Cualquier proveedor sirve: DigitalOcean, Vultr, Hetzner, Contabo o uno argentino. Es lo único con costo mensual |
| Un dominio o subdominio | La dirección del servidor, por ejemplo `maquinas.midominio.com.ar` | Un `.com.ar` se registra en NIC Argentina |

## Paso a paso

1. **Crear el VPS** con Ubuntu 24.04. Anotar su dirección IP.
2. **Apuntar el dominio:** en el panel del dominio, crear un registro **A** con el subdominio (por ejemplo `maquinas`) apuntando a la IP del VPS. Puede tardar unos minutos en propagarse.
3. **Entrar al VPS** desde la compu: `ssh root@IP-DEL-VPS`.
4. **Instalar Docker:**
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```
5. **Bajar el proyecto:**
   ```bash
   git clone https://github.com/Bsturniolo/MILENIUM-2.git
   cd MILENIUM-2/deploy
   ```
6. **Configurar:**
   ```bash
   cp .env.ejemplo .env
   openssl rand -hex 24      # copiar lo que muestra: es la clave de administrador
   nano .env                 # completar DOMINIO y MILENIUM_ADMIN_TOKEN; guardar con Ctrl+O y salir con Ctrl+X
   ```
7. **Prender todo:**
   ```bash
   docker compose up -d --build
   ```
8. **Probar:** abrir `https://tu-dominio/salud` (tiene que decir `{"ok":true}`) y después `https://tu-dominio/app/`.
9. **Conectar la app:** en **Equipos → Servidor**, poner `https://tu-dominio` y la clave de administrador.

## Después de subirlo

- **Firmware de los módulos:** el certificado de Let's Encrypt usa la raíz **ISRG Root X1**. Pegar ese certificado en `CA_RAIZ` del firmware antes de cargarlo en las placas, y configurar cada módulo con `servidor https://tu-dominio`.
- **Firewall:** dejar abiertos solo los puertos 22 (SSH), 80 y 443:
  ```bash
  ufw allow 22 && ufw allow 80 && ufw allow 443 && ufw enable
  ```
- **Actualizar** cuando haya cambios en GitHub:
  ```bash
  cd MILENIUM-2 && git pull && cd deploy && docker compose up -d --build
  ```
- **Copia de seguridad** de la base, por ejemplo una vez por día:
  ```bash
  docker compose exec servidor python -c "import sqlite3; sqlite3.connect('/datos/milenium.db').backup(sqlite3.connect('/datos/copia.db'))"
  docker compose cp servidor:/datos/copia.db ./copia-$(date +%F).db
  ```
- **Ver qué pasa** si algo falla: `docker compose logs -f servidor`.

## Lo que sigue faltando aunque esté subido

- Mercado Pago real: hoy el cobro con QR está simulado. Cuando se conecte, el aviso de pago llega a este mismo servidor.
- El módulo físico: ver [`modulos/FALTA-PARTE-FISICA.md`](../modulos/FALTA-PARTE-FISICA.md).

## Archivos que usa

| Archivo | Qué es |
| --- | --- |
| `Dockerfile` | Arma el servidor con la app incluida |
| `deploy/docker-compose.yml` | Prende el servidor y Caddy (HTTPS) juntos |
| `deploy/Caddyfile` | Configuración de HTTPS |
| `deploy/.env.ejemplo` | Plantilla de la configuración (la real, `.env`, no se sube a GitHub) |
