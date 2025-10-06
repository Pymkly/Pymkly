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
from config import config
from api.agent.usualagent import answer
from api.calendar.calendar_utils import CREDENTIALS_FILE, SCOPES
from api.db.conn import get_con

logging.basicConfig(level=logging.INFO)
SECRET_KEY = "1terces3_repus2"
ALGORITHM = "HS256"
FRONTEND_URL = config["FRONTEND_URL"]
BACKEND_URL = config["BACKEND_URL"]
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

class ThreadCreate(BaseModel):
    label: str


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
    next_step = f"/auth/google?user_uuid={uuid}&prompt=connect_google" if not has_google_auth(uuid, db) else None
    db.close()
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token({"sub": user.email, "uuid": uuid}, access_token_expires)
    # Proposer le consentement si pas de Google Auth (par défaut pas encore lié)
    return {
        "message": "Utilisateur créé et connecté",
        "uuid": uuid,
        "access_token": access_token,
        "token_type": "bearer",
        "next_step": next_step
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
        db.close()
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "message": "Connecté ! Voulez-vous lier votre Google Calendar ?",
            "next_step": f"/auth/google?user_uuid={user['uuid']}&prompt=connect_google",
            "uuid": user["uuid"]  # Ajout de l'UUID
        }
    db.close()
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
        redirect_uri=f"{BACKEND_URL}/auth/callback"  # Remplace par ton IP
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
        redirect_uri=f"{BACKEND_URL}/auth/callback"  # Remplace par ton IP
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
    db.close()
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token({"sub": state, "uuid": state}, access_token_expires)
    # Rediriger vers le frontend avec le token en paramètre
    redirect_url = f"{FRONTEND_URL}?token={access_token}&message=Auth%20Google%20réussie"
    return RedirectResponse(redirect_url)

def save_message(thread_id: str, role: str, content: str, cursor):
    _id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO discussion_messages (id, thread_id, role, content) VALUES (?, ?, ?, ?)",
        (_id, thread_id, role, content)
    )
@app.post("/answer")
def get_answer(request: AnswerRequest = Body(...), current_user: str = Depends(get_current_user)):
    try:
        user = request.thread_id
        print(user)
        logger.info(f"Requête reçue : text='{request.text}', thread_id={user}")
        user, result = answer(request.text, user, current_user)
        logger.info("Réponse générée avec succès")
        db = get_con()
        cursor = db.cursor()
        save_message(user, "user", request.text, cursor)
        save_message(user, "bot", result, cursor)
        db.commit()
        db.close()
        return {"result": result, "thread_id": user}
    except Exception as e:
        logger.error(f"Erreur lors du traitement : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/discussions")
def get_discussions(thread_id: str = Query(...)):
    try:
        db = get_con(row=True)
        cursor = db.cursor()
        cursor.execute("SELECT role, content FROM discussion_messages WHERE thread_id = ? ORDER BY created_at ASC", (thread_id,))
        messages = cursor.fetchall()
        db.close()
        return {
            "messages": [{"id" : str(uuid.uuid4()), "timestamp" : None, "content": msg["content"], "isUser" : True if msg['role']== 'user' else False} for msg in messages],
        }
    except Exception as e :
        logger.error(f"Erreur lors de la recuperation de la discusion : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/threads")
async def create_thread(thread: ThreadCreate, current_user: str = Depends(get_current_user)):
    db = get_con()
    thread_id = str(uuid.uuid4())
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO threads (id, user_uuid, label) VALUES (?, ?, ?)",
        (thread_id, current_user, thread.label)
    )
    db.commit()
    db.close()
    return {"id": thread_id, "label": thread.label, "user_uuid": current_user}

@app.get("/threads")
async def get_threads(current_user: str = Depends(get_current_user)):
    db = get_con()
    cursor = db.cursor()
    cursor.execute("SELECT id, label FROM threads WHERE user_uuid = ?", (current_user,))
    threads = [{"id": row[0], "title": row[1], "lastMessage" : "", "category": "note", "timestamp": None, "isActive":False} for row in cursor.fetchall()]
    if len(threads) > 0:
        threads[0]["isActive"] = True
    db.close()
    return {"threads": threads}
# Root endpoint pour tester l'API
@app.get("/")
def root():
    return {"message": "Bienvenue sur l'API Deep Rice Bot ! Endpoint principal : /answer (POST)"}

# Lancement : uvicorn api.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)