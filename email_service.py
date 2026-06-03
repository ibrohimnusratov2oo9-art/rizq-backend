import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# ВАЖНО: Замени на свой Gmail!
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "your-email@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "your-app-password")

def send_verification_email(to_email: str, code: str):
    """Отправляем код верификации на email"""
    
    subject = "RIZQ - Код подтверждения"
    
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #FF6B35, #E55A2B); padding: 30px; border-radius: 20px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 36px;">RIZQ</h1>
                <p style="color: white; margin: 10px 0 0 0;">Доставка еды в Душанбе</p>
            </div>
            
            <div style="background: white; padding: 30px; margin-top: 20px; border-radius: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h2 style="color: #1A1A2E; margin-top: 0;">Здравствуйте!</h2>
                <p style="color: #6C757D; font-size: 16px; line-height: 1.6;">
                    Спасибо за регистрацию в RIZQ! Для подтверждения вашего email используйте этот код:
                </p>
                
                <div style="background: #FFF8F5; border: 2px dashed #FF6B35; padding: 20px; text-align: center; border-radius: 12px; margin: 20px 0;">
                    <div style="font-size: 42px; font-weight: bold; color: #FF6B35; letter-spacing: 8px;">
                        {code}
                    </div>
                    <p style="color: #6C757D; margin: 10px 0 0 0; font-size: 14px;">
                        Код действителен 10 минут
                    </p>
                </div>
                
                <p style="color: #6C757D; font-size: 14px; line-height: 1.6;">
                    Если вы не регистрировались в RIZQ, просто игнорируйте это письмо.
                </p>
                
                <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 20px 0;">
                
                <p style="color: #9CA3AF; font-size: 12px; text-align: center; margin: 0;">
                    © 2025 RIZQ. Все права защищены.
                </p>
            </div>
        </body>
    </html>
    """
    
    # Создаём письмо
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"RIZQ <{SENDER_EMAIL}>"
    message["To"] = to_email
    
    html_part = MIMEText(html_body, "html")
    message.attach(html_part)
    
    # Отправляем через Gmail SMTP
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(message)
        return True
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        raise e