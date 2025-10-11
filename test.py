import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def send_email(to_email: str, subject: str, body: str):
    from_email = "contact@tsisy.com"
    password = os.environ.get("OVH_PASSWORD")
    print(password)
    if not password:
        raise ValueError("Mot de passe OVH non configuré")

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    port = 5025
    smtp_server = "ssl0.ovh.net"
    server = smtplib.SMTP(smtp_server, port)  # Port 465 pour SSL
    server.starttls()  # Active TLS (même sur 465, OVH le gère)
    server.login(from_email, password)
    server.sendmail(from_email, to_email, msg.as_string())
    server.quit()
    return {"message": "Email envoyé"}

# Test
if __name__ == "__main__":
    send_email("hrivonandrasana@gmail.com", "Test", "Ceci est un essai.")