from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import (
    add_evaluation,
    authenticate_user,
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
)

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


@app.on_event("startup")
def start_db() -> None:
    init_db()


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
    return {"month": month, "work_date": work_date, "assignments": get_assignments_for_day(month, work_date)}


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
