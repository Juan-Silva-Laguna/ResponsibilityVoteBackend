# Backend PicaRico

API REST construida con FastAPI y PostgreSQL/Supabase para el Sistema Responsabilidades PicaRico.

## Responsabilidades

- Autenticación por nombre y PIN.
- Generación automática de calendarios mensuales con fechas reales.
- Asignación de tareas y puntos por día.
- Votación de cumplimiento entre compañeras.
- Reportes por semana, mes y año.

## Regla de votación diaria

- Una usuaria sólo puede votar tareas de su compañera en la fecha actual de Colombia (`America/Bogota`).
- El backend rechaza votos de fechas pasadas o futuras, aunque se intente llamar la API directamente.
- Cuando una fecha queda atrás, cada tarea sin evaluación se registra automáticamente como cumplida.
- Por esta razón los días anteriores nunca permanecen pendientes y los reportes incluyen esos puntos como completados.

## Archivos

- `main.py`: define los endpoints de FastAPI.
- `database.py`: contiene el esquema PostgreSQL, generación del calendario y cálculos de reportes.
- `.env`: contiene `DATABASE_URL` para Supabase. No se versiona en Git.
- `.env.example`: plantilla segura de las variables necesarias.

## Configurar Supabase

1. Copia `.env.example` como `.env` dentro de esta carpeta.
2. En `.env`, reemplaza `TU_CONTRASENA` y `TU_PROYECTO` por la cadena de conexión de Supabase.
3. Nunca subas `.env` al repositorio ni publiques la contraseña.

El backend crea automáticamente las tablas y los datos iniciales al arrancar. Para producción, configura la misma variable `DATABASE_URL` en el panel de variables de entorno de tu proveedor de hosting; no hace falta subir el archivo `.env`.

Si tu red no dispone de IPv6, usa la cadena de conexión del apartado **Connect > Connection Pooler** de Supabase en lugar de la conexión directa. El host directo de Supabase puede resolver sólo a IPv6.

## Migrar datos locales de SQLite

El archivo `migrate_sqlite.py` transfiere los datos vigentes de `data/calendar.db` a Supabase. Migra usuarios, tareas, asignaciones por fecha y evaluaciones; no borra SQLite y puede ejecutarse varias veces sin duplicar registros.

```powershell
Set-Location "C:\Users\JuanIgnacioSilvaLagu\Music\calendario_app\backend"
.\.venv\Scripts\python.exe migrate_sqlite.py
```

Ejecuta la migración después de que `DATABASE_URL` conecte correctamente a Supabase.

## Notificaciones Web Push

Genera una sola vez las claves VAPID y el secreto del cron:

```powershell
.\.venv\Scripts\python.exe setup_notifications.py
```

El comando agrega a `.env` las variables que falten sin mostrar los secretos. Copia sus valores al servicio backend de Render:

- `VAPID_PUBLIC_KEY`
- `VAPID_PRIVATE_KEY`
- `VAPID_SUBJECT`
- `CRON_SECRET`
- `APP_TIMEZONE=America/Bogota`

Conserva siempre el mismo par de claves VAPID. Cambiarlo invalida las suscripciones existentes de los celulares.

### Configurar cron-job.org

1. Crea un cron job con URL `https://responsibilityvotebackend.onrender.com/notifications/send-reminders`.
2. Usa método `POST`.
3. Añade el encabezado `Authorization: Bearer TU_CRON_SECRET`.
4. Programa la ejecución diaria a las `03:00 UTC`, equivalente a las `10:00 p. m.` del día anterior en Colombia.
5. Ejecuta una prueba manual y confirma una respuesta HTTP `200`.

El backend sólo notifica a una usuaria si tiene tareas de su compañera pendientes de votar ese día. Los reintentos no generan avisos duplicados para la misma usuaria y fecha.

## Ejecutar

Desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

La documentación interactiva queda disponible en `http://127.0.0.1:8000/docs`.

## Deploy en Render

- `runtime.txt` fija Python a `3.11.10` para que Render use ruedas precompiladas compatibles con las dependencias actuales.
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Endpoints principales

- `POST /auth/login`: inicia sesión con `name` y `pin`.
- `GET /calendar?month=AAAA-MM`: obtiene las semanas reales de un mes.
- `GET /schedule?month=AAAA-MM&work_date=AAAA-MM-DD`: consulta tareas de una fecha.
- `POST /evaluations`: crea o actualiza una evaluación.
- `GET /reports/week?month=AAAA-MM&week_no=N`: reporte semanal.
- `GET /reports/month?month=AAAA-MM`: reporte mensual.
- `GET /reports/year?year=AAAA`: reporte anual.
- `GET /push/public-key`: clave pública VAPID.
- `POST /push/subscriptions`: registra un celular.
- `DELETE /push/subscriptions`: desactiva un celular.
- `POST /notifications/send-reminders`: envío protegido para cron-job.org.

## Datos iniciales

- Alexa: PIN `1508`.
- Michell: PIN `1515`.

## Distribución recurrente

- Michell tiene la tarea de video todos los lunes.
- La preparación para la empleada se realiza el mismo viernes o domingo, nunca de forma anticipada jueves o sábado.
- Los viernes Alexa cubre domicilios, comandas, cuentas y loza. Michell sólo asume la preparación para la empleada en semanas alternas.
- Los domingos Michell cubre domicilios, comandas, cuentas y loza. Alexa asume la preparación cuando Michell la realizó el viernes.
