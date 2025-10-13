import os
import uuid
from datetime import datetime, timedelta

import bcrypt
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import sqlite3
from api.db.conn import get_con

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

SECRET_KEY = "1terces3_repus2"
ALGORITHM = "HS256"

db = get_con()

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
    uuid = os.urandom(16).hex()
    cursor.execute(
        "INSERT INTO users (uuid, nom_complet, email, mot_de_passe) VALUES (?, ?, ?, ?)",
        (uuid, user.nom_complet, user.email, hashed_password)
    )
    db.commit()
    next_step = f"/auth/google?user_uuid={uuid}&prompt=connect_google" if not has_google_auth(uuid, db) else None
    return next_step

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