import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.config import get_settings


async def send_report_email(to_email: str, keyword: str, report: str) -> str:
    """생성된 보고서를 이메일로 발송합니다."""
    settings = get_settings()

    if settings.resend_api_key:
        await _send_via_resend(to_email, keyword, report, settings)
        return "발송이 완료되었습니다"

    if all([settings.smtp_user, settings.smtp_password, settings.email_from]):
        await _send_via_smtp(to_email, keyword, report, settings)
        return "발송이 완료되었습니다"

    await _send_via_formsubmit(to_email, keyword, report)
    return "발송이 완료되었습니다"


async def _send_via_resend(to_email: str, keyword: str, report: str, settings) -> None:
    html_body = _markdown_to_html(report)
    sender = settings.email_from or "AI 뉴스 리포터 <onboarding@resend.dev>"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": sender,
                "to": [to_email],
                "subject": f"[AI 뉴스 리포터] '{keyword}' 보고서",
                "html": html_body,
                "text": report,
            },
        )

    if response.status_code >= 400:
        detail = response.text[:200]
        raise ValueError(f"Resend 이메일 발송 실패: {detail}")


async def _send_via_smtp(to_email: str, keyword: str, report: str, settings) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[AI 뉴스 리포터] '{keyword}' 보고서"
    msg["From"] = settings.email_from
    msg["To"] = to_email

    html_body = _markdown_to_html(report)
    msg.attach(MIMEText(report, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    def _send() -> None:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

    try:
        import asyncio

        await asyncio.to_thread(_send)
    except smtplib.SMTPAuthenticationError as exc:
        raise ValueError(
            "SMTP 인증에 실패했습니다. Gmail은 앱 비밀번호 사용이 필요합니다."
        ) from exc
    except smtplib.SMTPException as exc:
        raise ValueError(f"이메일 발송 실패: {exc}") from exc


async def _send_via_formsubmit(to_email: str, keyword: str, report: str) -> None:
    """FormSubmit HTTP API로 실제 이메일을 발송합니다 (API 키 불필요)."""
    import os

    html_body = _markdown_to_html(report)
    site_url = os.environ.get("VERCEL_URL", "20260622mission.vercel.app")
    if not site_url.startswith("http"):
        site_url = f"https://{site_url}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://formsubmit.co/ajax/{to_email}",
            headers={
                "Accept": "application/json",
                "Origin": site_url,
                "Referer": f"{site_url}/",
            },
            json={
                "_subject": f"[AI 뉴스 리포터] '{keyword}' 보고서",
                "_captcha": "false",
                "_template": "box",
                "message": report,
                "html_report": html_body,
            },
        )

    if response.status_code >= 400:
        raise ValueError(f"이메일 발송 실패 (HTTP {response.status_code})")

    try:
        data = response.json()
    except ValueError as exc:
        raise ValueError("이메일 발송 응답을 확인할 수 없습니다.") from exc

    if str(data.get("success", "")).lower() == "true":
        return

    message = data.get("message", "")
    if "activat" in message.lower():
        raise ValueError(
            "처음 사용하는 이메일입니다. 수신함에서 FormSubmit 활성화 링크를 "
            "클릭한 후 다시 [발송]을 눌러 주세요."
        )
    raise ValueError(message or "이메일 발송에 실패했습니다.")


def _markdown_to_html(markdown: str) -> str:
    """간단한 마크다운을 HTML로 변환합니다."""
    html = markdown
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"(<li>.*</li>\n?)+", r"<ul>\g<0></ul>", html)
    html = html.replace("\n\n", "<br><br>").replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"></head>
<body style="font-family: sans-serif; line-height: 1.6; max-width: 720px; margin: 0 auto; padding: 20px;">
{html}
<hr>
<p style="color: #888; font-size: 12px;">AI 뉴스 리포터에서 자동 발송된 메일입니다.</p>
</body>
</html>"""
