from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).with_name(".env"))

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import chat, clauses, companies, policies, products, translate, needs_assessment, claims, simulator
from routers import clients, balance_sheet, questionnaire
from allocation.router import router as allocation_router
from db_init import init_db
from services.llm_service import get_model, get_provider, is_api_key_configured

init_db()

app = FastAPI(title="AI-insurance-advice API")

frontend_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_URL", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", *frontend_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(companies.router, prefix="/companies", tags=["companies"])
app.include_router(clauses.router, prefix="/clauses", tags=["clauses"])
app.include_router(policies.router, prefix="/policies", tags=["policies"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(translate.router, prefix="/translate", tags=["translate"])
app.include_router(needs_assessment.router, prefix="/needs-assessment", tags=["needs-assessment"])
app.include_router(claims.router, prefix="/claims", tags=["claims"])
app.include_router(allocation_router, prefix="/api/allocation", tags=["allocation"])
app.include_router(simulator.router, prefix="/api/simulator", tags=["simulator"])
app.include_router(clients.router, prefix="/api/advisor/clients", tags=["advisor-clients"])
app.include_router(balance_sheet.router, prefix="/api/advisor/clients", tags=["advisor-balance-sheet"])
app.include_router(questionnaire.router, prefix="/api/advisor/questionnaires", tags=["advisor-questionnaire"])


@app.get("/")
def health_check():
    return {
        "status": "ok", "api_key_set": is_api_key_configured(),
        "ai_provider": get_provider(), "ai_model": get_model(),
        "ai_fast_model": get_model("fast"),
    }
