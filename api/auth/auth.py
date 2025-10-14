import uuid
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import bcrypt
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import sqlite3
from api.db.conn import get_con
from config import config

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
FRONTEND_URL = config["FRONTEND_URL"]
SECRET_KEY = "1terces3_repus2"
ALGORITHM = "HS256"

db = get_con()

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

def on_change_password(password: str, token: str):
    user_id = on_change_password_checking(token)
    hashed_password = hash_password(password)
    cursor = db.cursor()
    cursor.execute("UPDATE users SET mot_de_passe = ? WHERE uuid = ?", (hashed_password, user_id))
    cursor.execute("Delete from reset_password where token = ?", (token, ))
    db.commit()
    cursor.execute("select email from users where uuid = ?", (user_id, ))
    user_email = cursor.fetchone()[0]
    return user_email, user_id

def on_change_password_checking(token):
    cursor = db.cursor()
    cursor.execute("SELECT user_id FROM reset_password WHERE token = ? and expire_date > datetime('now')", (token,))
    user = cursor.fetchone()
    if user is None:
        raise HTTPException(status_code=404, detail="Token invalide")
    return user[0]

def on_forgot_password(email):
    cursor = db.cursor()
    cursor.execute("SELECT uuid,nom_complet FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Email non existent")
    reset_token = str(uuid.uuid4())
    _id = str(uuid.uuid4())
    _date = datetime.now() + timedelta(minutes=15)
    cursor.execute("insert into reset_password(id, user_id, token, expire_date) values (?, ?, ?, ?)", (_id, user[0], reset_token,_date))
    db.commit()
    _reset_link = f"{FRONTEND_URL}?reset-token={reset_token}"
    send_email(email, "Reset password",
               f"""Bonjour {user[1]},

Vous avez demandé la réinitialisation de votre mot de passe sur Tsisy.com. Pas de panique, on vous aide à reprendre le contrôle en un clic ! Cliquez sur le lien ci-dessous pour créer un nouveau mot de passe :

[{_reset_link}]

Ce lien est valide pendant 15 minutes. Si vous n’avez pas fait cette demande, ignorez simplement cet email – votre compte reste sécurisé.

L’équipe Tsisy.com est là pour vous accompagner dans une gestion quotidienne facile et efficace. N’hésitez pas à nous contacter à hitafa@tsisy.com si besoin !

Bonne journée,
L’équipe Tsisy.com""")

def add_credentials(state, refresh_token):
    cursor = db.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO user_credentials (uuid, user_uuid, refresh_token) VALUES (?, ?, ?)",
        (str(uuid.uuid4()), state, refresh_token)
    )
    db.commit()

def has_google_auth(user_id: str, db: sqlite3.Connection):
    cursor = db.cursor()
    cursor.execute("SELECT refresh_token FROM user_credentials WHERE user_uuid = ?", (user_id,))
    return cursor.fetchone() is not None

def login_user(username, password, conn):
    cursor = conn.cursor()
    cursor.execute("SELECT uuid, email, mot_de_passe FROM users WHERE email = ?", (username,))
    user = cursor.fetchone()
    if not user or not verify_password(password, user["mot_de_passe"]):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    return user

def register_user(user):
    cursor = db.cursor()
    cursor.execute("SELECT email FROM users WHERE email = ?", (user.email,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    hashed_password = hash_password(user.mot_de_passe)
    user_id = os.urandom(16).hex()
    cursor.execute(
        "INSERT INTO users (uuid, nom_complet, email, mot_de_passe) VALUES (?, ?, ?, ?)",
        (user_id, user.nom_complet, user.email, hashed_password)
    )
    db.commit()
    next_step = f"/auth/google?user_uuid={user_id}&prompt=connect_google" if not has_google_auth(user_id, db) else None
    return next_step, user_id

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uuid = payload.get("uuid")
        if not uuid:
            raise HTTPException(status_code=401, detail="Token invalide ou UUID manquant")
        return uuid
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)