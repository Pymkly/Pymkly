import logging
import uuid
from datetime import timedelta

from fastapi import FastAPI, HTTPException, Body, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel

from api.agent.usualagent import answer
from api.auth.auth import create_access_token, register_user, has_google_auth, \
    get_current_user, login_user, add_credentials
from api.calendar.calendar_utils import CREDENTIALS_FILE, SCOPES
from api.db.conn import get_con
from api.threads.threads import save_message, create_message, get_all_threads, get_one_threads
from config import config

logging.basicConfig(level=logging.INFO)
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
    clientTime : str
    timeZone: str

class ThreadCreate(BaseModel):
    label: str

@app.post("/register")
async def register(user: UserCreate):
    next_step = register_user(user)
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
    print(form_data)
    user = login_user(form_data.username, form_data.password, db)
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
    add_credentials(state, credentials.refresh_token)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token({"sub": state, "uuid": state}, access_token_expires)
    # Rediriger vers le frontend avec le token en paramètre
    redirect_url = f"{FRONTEND_URL}?token={access_token}&message=Auth%20Google%20réussie"
    return RedirectResponse(redirect_url)



@app.post("/answer")
def get_answer(request: AnswerRequest = Body(...), current_user: str = Depends(get_current_user)):
    try:
        user = request.thread_id
        print(user)
        logger.info(f"Requête reçue : text='{request.text}', thread_id={user}")
        _id_discussion = str(uuid.uuid4())
        user, result, suggestions = answer(request.text, user, current_user, request.clientTime, request.timeZone, _id_discussion)
        logger.info("Réponse générée avec succès")
        db = get_con()
        cursor = db.cursor()
        _id = str(uuid.uuid4())
        save_message(_id, user, "user", request.text, cursor)
        save_message(_id_discussion, user, "bot", result, cursor)
        db.commit()
        db.close()
        return {"result": result, "thread_id": user, "suggestions": suggestions}
    except Exception as e:
        logger.error(f"Erreur lors du traitement : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/discussions")
def get_discussions(thread_id: str = Query(...)):
    try:
        messages = get_one_threads(thread_id)
        return {
            "messages": messages,
        }
    except Exception as e :
        logger.error(f"Erreur lors de la recuperation de la discusion : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/threads")
async def create_thread(thread: ThreadCreate, current_user: str = Depends(get_current_user)):
    thread_id = create_message(thread, current_user)
    return {"id": thread_id, "label": thread.label, "user_uuid": current_user}

@app.get("/threads")
async def get_threads(current_user: str = Depends(get_current_user)):
    threads = get_all_threads(current_user)
    return {"threads": threads}

# Root endpoint pour tester l'API
@app.get("/")
def root():
    return {"message": "Bienvenue sur l'API Deep Rice Bot ! Endpoint principal : /answer (POST)"}

# Lancement : uvicorn api.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)