import logging
import os
import sqlite3
import uuid
from datetime import datetime, timedelta

import bcrypt
from fastapi import FastAPI, HTTPException, Body, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from google_auth_oauthlib.flow import Flow
from jose import jwt, JWTError
from pydantic import BaseModel

from api.agent.usualagent import answer
from api.calendar.calendar_utils import CREDENTIALS_FILE, SCOPES
from api.db.conn import get_con
from api.user.usermanager import insert_user

logging.basicConfig(level=logging.INFO)
SECRET_KEY = "1terces3_repus2"
ALGORITHM = "HS256"
FRONTEND_URL = "http://localhost:5173"
ACCESS_TOKEN_EXPIRE_MINUTES = 3600*7
logger = logging.getLogger(__name__)
app = FastAPI(title="H", description="API pour ton assistant personnel", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Ajuste pour ton frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class UserCreate(BaseModel):
    nom_complet: str
    email: str
    mot_de_passe: str

class Token(BaseModel):
    access_token: str
    token_type: str

class AnswerRequest(BaseModel):
    text: str
    thread_id: str = None


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

def has_google_auth(user_id: str, db: sqlite3.Connection):
    cursor = db.cursor()
    cursor.execute("SELECT refresh_token FROM user_credentials WHERE user_uuid = ?", (user_id,))
    return cursor.fetchone() is not None

from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uuid = payload.get("uuid")
        if not uuid:
            raise HTTPException(status_code=401, detail="Token invalide ou UUID manquant")
        return uuid
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

@app.post("/register")
async def register(user: UserCreate):
    db = get_con()
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
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token({"sub": user.email, "uuid": uuid}, access_token_expires)
    # Proposer le consentement si pas de Google Auth (par défaut pas encore lié)
    return {
        "message": "Utilisateur créé et connecté",
        "uuid": uuid,
        "access_token": access_token,
        "token_type": "bearer",
        "next_step": f"/auth/google?user_uuid={uuid}&prompt=connect_google" if not has_google_auth(uuid, db) else None
    }

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db = get_con(row=True)
    cursor = db.cursor()
    cursor.execute("SELECT uuid, email, mot_de_passe FROM users WHERE email = ?", (form_data.username,))
    user = cursor.fetchone()
    if not user or not verify_password(form_data.password, user["mot_de_passe"]):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token({"sub": user["email"], "uuid": user["uuid"]}, access_token_expires)
    # Proposer le consentement si pas de Google Auth
    if not has_google_auth(user["uuid"], db):
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "message": "Connecté ! Voulez-vous lier votre Google Calendar ?",
            "next_step": f"/auth/google?user_uuid={user['uuid']}&prompt=connect_google",
            "uuid": user["uuid"]  # Ajout de l'UUID
        }
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "message": "Connecté !",
        "uuid": user["uuid"]  # Ajout de l'UUID
    }

@app.get("/auth/google")
async def auth_google(user_uuid: str = Query(...)):
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri="http://localhost:8000/auth/callback"  # Remplace par ton IP
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=user_uuid,  # Passe user_uuid via state
        prompt="consent"
    )
    return RedirectResponse(authorization_url)


# Endpoint callback pour récupérer le token
@app.get("/auth/callback")
async def auth_callback(code: str = Query(...), state: str = Query(...)):
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        redirect_uri="http://localhost:8000/auth/callback"  # Remplace par ton IP
    )
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Stocker refresh_token dans SQLite
    db = get_con()
    cursor = db.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO user_credentials (uuid, user_uuid, refresh_token) VALUES (?, ?, ?)",
        (str(uuid.uuid4()), state, credentials.refresh_token)
    )
    db.commit()
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token({"sub": state, "uuid": state}, access_token_expires)
    # Rediriger vers le frontend avec le token en paramètre
    redirect_url = f"{FRONTEND_URL}?token={access_token}&message=Auth%20Google%20réussie"
    return RedirectResponse(redirect_url)

@app.post("/answer")
def get_answer(request: AnswerRequest = Body(...), current_user: str = Depends(get_current_user)):
    try:
        user = request.thread_id if request.thread_id else current_user
        print(current_user)
        if user is None:
            user = uuid.uuid4()
            conn = get_con()
            insert_user(user, conn)
            conn.close()
        logger.info(f"Requête reçue : text='{request.text}', thread_id={user}")
        user, result = answer(request.text, user)
        logger.info("Réponse générée avec succès")
        return {"result": result, "thread_id": user}
    except Exception as e:
        logger.error(f"Erreur lors du traitement : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Root endpoint pour tester l'API
@app.get("/")
def root():
    return {"message": "Bienvenue sur l'API Deep Rice Bot ! Endpoint principal : /answer (POST)"}

# Lancement : uvicorn api.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)