import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.config import get_settings

OUTPUT_DIR = (
    Path("/tmp/emails")
    if os.environ.get("VERCEL")
    else Path(__file__).resolve().parent.parent.parent / "output" / "emails"
)


def send_report_email(to_email: str, keyword: str, report: str) -> str:
    """생성된 보고서를 이메일로 발송합니다. SMTP 미설정 시 로컬 파일로 저장합니다."""
    settings = get_settings()

    if all([settings.smtp_user, settings.smtp_password, settings.email_from]):
        _send_via_smtp(to_email, keyword, report, settings)
        return "발송이 완료되었습니다"

    return _save_to_file(to_email, keyword, report)


def _send_via_smtp(to_email: str, keyword: str, report: str, settings) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[AI 뉴스 리포터] '{keyword}' 보고서"
    msg["From"] = settings.email_from
    msg["To"] = to_email

    html_body = _markdown_to_html(report)
    msg.attach(MIMEText(report, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise ValueError(
            "SMTP 인증에 실패했습니다. Gmail은 앱 비밀번호 사용이 필요합니다."
        ) from exc
    except smtplib.SMTPException as exc:
        raise ValueError(f"이메일 발송 실패: {exc}") from exc


def _save_to_file(to_email: str, keyword: str, report: str) -> str:
    """SMTP 미설정 시 보고서를 로컬 파일로 저장합니다."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_keyword = re.sub(r'[^\w가-힣-]', '_', keyword)[:30]
    filename = OUTPUT_DIR / f"{timestamp}_{safe_keyword}.txt"

    content = (
        f"수신: {to_email}\n"
        f"제목: [AI 뉴스 리포터] '{keyword}' 보고서\n"
        f"발송 시각: {datetime.now().isoformat()}\n"
        f"{'=' * 50}\n\n"
        f"{report}\n"
    )
    filename.write_text(content, encoding="utf-8")
    return "발송이 완료되었습니다"


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
