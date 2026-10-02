# Ruta de IA para desarrolladores — FastAPI + PostgreSQL

Frontend (un solo HTML) + API FastAPI + PostgreSQL. Listo para Render y Railway.

## Estructura
```
app/
  main.py        rutas de la API y entrega del frontend
  models.py      tablas (SQLAlchemy)
  schemas.py     validación de datos
  security.py    tokens, contraseña de admin, límite de intentos
  database.py    conexión (Postgres en Railway, SQLite en local)
  config.py      variables de entorno
static/index.html   la capacitación (frontend)
schema.sql          esquema SQL de referencia
render.yaml         Blueprint de Render (app + Postgres)
railway.json        comando de arranque y healthcheck (Railway)
tests/              pruebas automáticas
```

## Desplegar en Render (≈5 minutos)

1. Sube esta carpeta a un repositorio de GitHub (el `.env` NO se sube).
2. En [dashboard.render.com](https://dashboard.render.com): **New + → Blueprint**, conecta el repositorio y elige la rama.
3. Render lee `render.yaml`, te muestra la app web y la base PostgreSQL, y te pide `ADMIN_PASSWORD` (la contraseña del panel de superadmin). `SECRET_KEY` y `DATABASE_URL` se configuran solas.
4. Pulsa **Deploy Blueprint**. Cuando el servicio esté en verde, abre la URL `https://ruta-ia.onrender.com` (o la que te asigne).
5. Los participantes se registran; tú entras con el botón **Admin**.

Costos y rendimiento: el Blueprint usa **Starter** para la app y **Basic-256mb** para Postgres (planes de pago). Con el plan gratis la app se duerme tras 15 minutos sin tráfico (el primer usuario espera cerca de un minuto) y la base de datos expira a los 30 días, por eso no se recomienda para una capacitación real. Verifica los precios vigentes en Render antes de desplegar.
Para más usuarios, sube el plan de la app (Standard) o agrega instancias desde **Scaling**.
Si cambias la región, mantén app y base en la **misma** región.

## Desplegar en Railway (≈5 minutos)

1. Sube esta carpeta a un repositorio de GitHub (el `.env` NO se sube; ya está en `.gitignore`).
2. En [railway.com](https://railway.com): **New Project → Deploy from GitHub repo** y elige el repositorio.
3. En el mismo proyecto: **+ New → Database → Add PostgreSQL**.
4. Entra al servicio de tu app → **Variables** y agrega:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (referencia al Postgres; ajusta el nombre si tu base se llama distinto)
   - `SECRET_KEY` = una clave larga aleatoria (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
   - `ADMIN_PASSWORD` = la contraseña del panel de superadmin
5. **Settings → Networking → Generate Domain** para obtener tu URL pública.
6. Abre la URL: los participantes se registran; tú entras con el botón **Admin**.

Las tablas se crean solas al primer arranque.

## Escalar sin lentitud
- Aumenta réplicas en **Settings → Deploy → Replicas** o sube recursos del servicio; todas comparten el mismo Postgres.
- Cada instancia corre 2 workers (`--workers 2` en `railway.json`) con pool de conexiones a la base.
- El frontend guarda con *debounce* (1,5 s), así que cada persona genera pocas escrituras.
- Respuestas comprimidas con gzip y HTML con revalidación (304).
- Nota: el límite de intentos de login/registro es en memoria por proceso. Es suficiente como freno básico; si necesitas límites estrictos entre réplicas, usa Redis.

## Desarrollo local
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest httpx
cp .env.example .env        # edita SECRET_KEY y ADMIN_PASSWORD
uvicorn app.main:app --reload
pytest
```
Sin `DATABASE_URL` usa SQLite en `data/ruta_ia.db`.

## Modelo de datos
| Tabla | Contenido |
|---|---|
| `participants` | perfil (nombre, área, cargo, nivel), hash del token, paso actual, fechas |
| `module_progress` | módulos completados por persona |
| `self_assessments` | autoevaluación 1–5 por habilidad, antes (`pre`) y después (`post`) |
| `result_scores` | aciertos de mitos, datos compartibles, comprobaciones y rúbrica |
| `participant_state` | estado completo y **privado** (prompts, notas, plan); el admin no lo ve |

## Acceso y seguridad
- Cada participante recibe un token aleatorio al registrarse (solo se guarda su hash). Lo ve en «Mi registro» como **código de acceso** para continuar desde otro dispositivo.
- El admin entra con `ADMIN_PASSWORD`; la sesión dura `ADMIN_TOKEN_HOURS` (12 por defecto).
- Los endpoints de admin exigen token firmado; `/docs` está desactivado salvo `DEBUG=1`.
- Haz respaldos periódicos desde Railway (pestaña de Postgres → Backups) si guardas datos importantes.

## API
`POST /api/register` · `GET/PUT /api/me` · `PUT /api/state` · `POST /api/admin/login` · `GET /api/admin/participants` · `DELETE /api/admin/participants/{id}` · `GET /health`
