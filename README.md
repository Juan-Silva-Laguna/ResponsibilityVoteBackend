# Backend PicaRico

API REST construida con FastAPI y PostgreSQL/Supabase para el Sistema Responsabilidades PicaRico.

## Responsabilidades

- Autenticación por nombre y PIN.
- Generación automática de calendarios mensuales con fechas reales.
- Asignación de tareas y puntos por día.
- Votación de cumplimiento entre compañeras.
- Reportes por semana, mes y año.

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

## Ejecutar

Desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

La documentación interactiva queda disponible en `http://127.0.0.1:8000/docs`.

## Endpoints principales

- `POST /auth/login`: inicia sesión con `name` y `pin`.
- `GET /calendar?month=AAAA-MM`: obtiene las semanas reales de un mes.
- `GET /schedule?month=AAAA-MM&work_date=AAAA-MM-DD`: consulta tareas de una fecha.
- `POST /evaluations`: crea o actualiza una evaluación.
- `GET /reports/week?month=AAAA-MM&week_no=N`: reporte semanal.
- `GET /reports/month?month=AAAA-MM`: reporte mensual.
- `GET /reports/year?year=AAAA`: reporte anual.

## Datos iniciales

- Alexa: PIN `1508`.
- Michell: PIN `1515`.

## Distribución recurrente

- Michell tiene la tarea de video todos los lunes.
- La preparación para la empleada se realiza el mismo viernes o domingo, nunca de forma anticipada jueves o sábado.
- Los viernes Alexa cubre domicilios, comandas, cuentas y loza. Michell sólo asume la preparación para la empleada en semanas alternas.
- Los domingos Michell cubre domicilios, comandas, cuentas y loza. Alexa asume la preparación cuando Michell la realizó el viernes.
