from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

from app.services.email_service import send_report_email
from app.services.gemini_service import search_and_generate_report

app = FastAPI(title="AI 뉴스 리포터")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class GenerateReportRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=100)


class GenerateReportResponse(BaseModel):
    keyword: str
    report: str
    article_count: int
    articles: list[dict]


class SendEmailRequest(BaseModel):
    email: EmailStr
    keyword: str
    report: str = Field(..., min_length=1)


class SendEmailResponse(BaseModel):
    success: bool
    message: str


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/generate-report", response_model=GenerateReportResponse)
async def api_generate_report(body: GenerateReportRequest):
    keyword = body.keyword.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="키워드를 입력해 주세요.")

    try:
        report, articles = await search_and_generate_report(keyword)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"뉴스 검색 및 보고서 생성 중 오류가 발생했습니다: {exc}",
        ) from exc

    if not report.strip():
        raise HTTPException(
            status_code=404,
            detail=f"'{keyword}' 관련 최근 2일 내 기사를 찾지 못했습니다.",
        )

    return GenerateReportResponse(
        keyword=keyword,
        report=report,
        article_count=len(articles),
        articles=articles,
    )


@app.post("/api/send-email", response_model=SendEmailResponse)
async def api_send_email(body: SendEmailRequest):
    try:
        message = send_report_email(body.email, body.keyword, body.report)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"이메일 발송 중 오류가 발생했습니다: {exc}",
        ) from exc

    return SendEmailResponse(
        success=True,
        message=message,
    )
