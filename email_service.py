import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")


def send_verification_email(to_email: str, code: str) -> bool:
    """Отправляет email с кодом подтверждения"""
    if not SMTP_USER or not SMTP_PASSWORD:
        raise Exception("SMTP credentials not configured in environment")

    msg = MIMEMultipart("alternative")
    msg["From"] = f"RIZQ <{SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = "Код подтверждения RIZQ"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
    </head>
    <body style="font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; margin: 0;">
        <div style="max-width: 500px; margin: 0 auto; background: white; border-radius: 12px; padding: 40px; text-align: center;">
            
            <h1 style="color: #F26522; margin: 0; font-size: 32px;">RIZQ</h1>
            <p style="color: #666; font-size: 14px; margin: 5px 0 0 0;">Доставка еды в Душанбе</p>
            
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            
            <h2 style="color: #222; font-size: 20px; margin: 0 0 10px 0;">Код подтверждения</h2>
            <p style="color: #666; font-size: 14px; margin: 0;">Введите этот код в приложении:</p>
            
            <div style="background: #FFF5EE; border: 2px dashed #F26522; border-radius: 12px; padding: 24px; margin: 24px 0;">
                <h1 style="color: #F26522; letter-spacing: 8px; margin: 0; font-size: 40px; font-weight: bold;">{code}</h1>
            </div>
            
            <p style="color: #999; font-size: 13px; margin: 8px 0;">Код действителен 10 минут</p>
            <p style="color: #999; font-size: 12px; margin: 8px 0;">Если вы не запрашивали код, просто игнорируйте это письмо</p>
            
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            
            <p style="color: #999; font-size: 11px; margin: 0; line-height: 1.6;">
                <strong style="color: #F26522;">RIZQ</strong> — доставка еды в Душанбе<br>
                rizqgo.tj@gmail.com
            </p>
            
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Email send error: {e}")
        raise e