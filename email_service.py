import os
import requests

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_API_URL = "https://api.resend.com/emails"


def send_verification_email(to_email: str, code: str) -> bool:
    """Отправляет email с кодом подтверждения через Resend API"""
    
    if not RESEND_API_KEY:
        raise Exception("RESEND_API_KEY not configured in environment")

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

    payload = {
        "from": "RIZQ <onboarding@resend.dev>",
        "to": [to_email],
        "subject": "Код подтверждения RIZQ",
        "html": html_body
    }

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            RESEND_API_URL,
            json=payload,
            headers=headers,
            timeout=30
        )

        if response.status_code in [200, 201, 202]:
            print(f"✅ Email sent to {to_email}")
            return True
        else:
            error_msg = f"Resend API error {response.status_code}: {response.text}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)

    except requests.exceptions.RequestException as e:
        print(f"❌ Email send error: {e}")
        raise e