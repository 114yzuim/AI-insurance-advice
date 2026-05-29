from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import chat, products, translate, needs_assessment, claims

app = FastAPI(title="AI Insurance B2C API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(translate.router, prefix="/translate", tags=["translate"])
app.include_router(needs_assessment.router, prefix="/needs-assessment", tags=["needs-assessment"])
app.include_router(claims.router, prefix="/claims", tags=["claims"])


@app.get("/")
def health_check():
    import os
    return {"status": "ok", "api_key_set": bool(os.getenv("CLAUDE_API_KEY"))}
