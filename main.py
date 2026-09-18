import os

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from .database import (
        add_evaluation,
        authenticate_user,
        business_today,
        close_overdue_evaluations,
        get_assignments_for_day,
        get_calendar,
        get_daily_validations,
        get_tasks,
        get_user_dashboard,
        get_users,
        report_for_month,
        report_for_week,
        report_for_year,
        init_db,
        save_push_subscription,
        delete_push_subscription,
    )
    from .notifications import send_pending_reminders
except ImportError:
    from database import (
        add_evaluation,
        authenticate_user,
        business_today,
        close_overdue_evaluations,
        get_assignments_for_day,
        get_calendar,
        get_daily_validations,
        get_tasks,
        get_user_dashboard,
        get_users,
        report_for_month,
        report_for_week,
        report_for_year,
        init_db,
        save_push_subscription,
        delete_push_subscription,
    )
    from notifications import send_pending_reminders

app = FastAPI(title="Sistema Responsabilidades PicaRico", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    name: str
    pin: str


class EvaluationRequest(BaseModel):
    work_date: str
    task_id: int
    assigned_user_id: int
    evaluator_user_id: int
    completed: bool


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionRequest(BaseModel):
    user_id: int
    endpoint: str
    keys: PushKeys


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


@app.on_event("startup")
def start_db() -> None:
    init_db()
    close_overdue_evaluations()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/auth/login")
def login(payload: LoginRequest) -> dict:
    user = authenticate_user(payload.name, payload.pin)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return {"user": user}


@app.get("/users")
def users() -> dict:
    return {"users": get_users()}


@app.get("/tasks")
def tasks() -> dict:
    return {"tasks": get_tasks()}


@app.get("/calendar")
def calendar_view(month: str = Query(...)) -> dict:
    try:
        return get_calendar(month)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/schedule")
def schedule(month: str = Query(...), work_date: str = Query(...)) -> dict:
    return {
        "month": month,
        "work_date": work_date,
        "can_vote": work_date == business_today().isoformat(),
        "assignments": get_assignments_for_day(month, work_date),
    }


@app.get("/dashboard")
def dashboard(user_id: int = Query(...), month: str = Query(...), week_no: int = Query(...)) -> dict:
    return get_user_dashboard(month, user_id, week_no)


@app.get("/reports/week")
def week_report(month: str = Query(...), week_no: int = Query(...)) -> dict:
    return report_for_week(month, week_no)


@app.get("/reports/month")
def month_report(month: str = Query(...)) -> dict:
    return report_for_month(month)


@app.get("/reports/year")
def year_report(year: int = Query(...)) -> dict:
    try:
        return report_for_year(year)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/evaluations")
def evaluations(work_date: str = Query(...)) -> dict:
    return {"work_date": work_date, "evaluations": get_daily_validations(work_date)}


@app.post("/evaluations")
def create_evaluation(payload: EvaluationRequest) -> dict:
    try:
        return {"evaluation": add_evaluation(**payload.model_dump())}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/push/public-key")
def push_public_key() -> dict:
    public_key = os.getenv("VAPID_PUBLIC_KEY")
    if not public_key:
        raise HTTPException(status_code=503, detail="Web Push no está configurado.")
    return {"public_key": public_key}


@app.post("/push/subscriptions")
def subscribe_push(payload: PushSubscriptionRequest) -> dict:
    subscription = save_push_subscription(
        user_id=payload.user_id,
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
    )
    return {"subscription": subscription}


@app.delete("/push/subscriptions")
def unsubscribe_push(payload: PushUnsubscribeRequest) -> dict:
    return {"deleted": delete_push_subscription(payload.endpoint)}


@app.post("/notifications/send-reminders")
def send_reminders(authorization: str | None = Header(default=None)) -> dict:
    cron_secret = os.getenv("CRON_SECRET")
    if not cron_secret or authorization != f"Bearer {cron_secret}":
        raise HTTPException(status_code=401, detail="No autorizado.")
    try:
        return send_pending_reminders()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
