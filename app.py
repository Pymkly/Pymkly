import logging
import uuid
from datetime import timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Body, Query, Depends , APIRouter
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
import json , uuid , time
from api.agent.usualagent import agent_app, get_last_messages, instruction
from langchain_core.messages import HumanMessage

from api.agent.usualagent import answer
from api.auth.auth import create_access_token, register_user, has_google_auth, \
    get_current_user, login_user, on_forgot_password, on_change_password_checking, on_change_password, \
    on_auth_callback, on_auth_google
from api.calendar.calendar_utils import SCOPES_CALENDAR, SCOPES_GMAIL, SCOPES_TASKS, SCOPES_DRIVE
from api.db.conn import get_con
from api.threads.threads import save_message, get_all_threads, get_one_threads, generate_conversation
from config import config
from api.historique.historique_utils import get_user_history, add_history_entry

logging.basicConfig(level=logging.INFO)
FRONTEND_URL = config["FRONTEND_URL"]
BACKEND_URL = config["BACKEND_URL"]
ACCESS_TOKEN_EXPIRE_MINUTES = 3600*7
CALENDAR_TYPE = {
    "value" : 1,
    "url" : f"{BACKEND_URL}/auth/callback/calendar",
    "credentials_file" : "credentials.json"
}
GMAIL_TYPE = {
    "value" : 50,
    "url" : f"{BACKEND_URL}/auth/callback/gmail",
    "credentials_file" : "credentials_gmail.json"
}


logger = logging.getLogger(__name__)
app = FastAPI(title="H", description="API pour ton assistant personnel", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Ajuste pour ton frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class UserChangePassword(BaseModel):
    token: str
    mot_de_passe: str


class UserCreate(BaseModel):
    nom_complet: str
    email: str
    mot_de_passe: str

class Token(BaseModel):
    access_token: str
    token_type: str

class AnswerRequest(BaseModel):
    text: str
    thread_id: Optional[str] = None
    clientTime : str
    timeZone: str

class ThreadCreate(BaseModel):
    label: str


@app.post("/change-password")
async def change_password(form: UserChangePassword):
    email, user_id = on_change_password(form.mot_de_passe, form.token)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token({"sub": email, "uuid": user_id}, access_token_expires)
    # Proposer le consentement si pas de Google Auth (par défaut pas encore lié)
    return {
        "email": email,
        "access_token": access_token
    }

@app.get("/token-password-checking")
async def token_password_checking(token: str = Query(...)):
    user_id = on_change_password_checking(token)
    return {"user_id": user_id}

@app.get("/forgot-password")
async def forgot_password(email: str = Query(...)):
    on_forgot_password(email)
    return "ok"
@app.post("/register")
async def register(user: UserCreate):
    next_step, user_id = register_user(user)
    print(next_step)
    print(user_id)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token({"sub": user.email, "uuid": user_id}, access_token_expires)
    # Proposer le consentement si pas de Google Auth (par défaut pas encore lié)
    return {
        "message": "Utilisateur créé et connecté",
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
            "next_step": f"/auth/calendar?user_uuid={user['uuid']}&prompt=connect_google",
            "uuid": user["uuid"]  # Ajout de l'UUID
        }
    db.close()
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "message": "Connecté !",
        "uuid": user["uuid"]  # Ajout de l'UUID
    }

@app.get("/auth/calendar")
async def auth_calendar(user_uuid: str = Query(...)):
    return on_auth_google(SCOPES_CALENDAR + SCOPES_TASKS + SCOPES_DRIVE, user_uuid, CALENDAR_TYPE)

# Endpoint callback pour récupérer le token
@app.get("/auth/callback/calendar")
async def auth_callback_calendar(code: str = Query(...), state: str = Query(...)):
    return on_auth_callback(SCOPES_CALENDAR + SCOPES_TASKS + SCOPES_DRIVE, code, state, CALENDAR_TYPE)

@app.get("/auth/gmail")
async def auth_gmail(user_uuid: str = Query(...)):
    return on_auth_google(SCOPES_GMAIL, user_uuid, GMAIL_TYPE)

# Endpoint callback pour récupérer le token
@app.get("/auth/callback/gmail")
async def auth_callback_gmail(code: str = Query(...), state: str = Query(...)):
    return on_auth_callback(SCOPES_GMAIL, code, state, GMAIL_TYPE)


@app.post("/answer")
def get_answer(request: AnswerRequest = Body(...), current_user: str = Depends(get_current_user)):
    try:
        user = request.thread_id
        print(user)
        logger.info(f"Requête reçue : text='{request.text}', thread_id={user}")
        _id_discussion = str(uuid.uuid4())
        user, result, suggestions, metadata_ = answer(request.text, user, current_user, request.clientTime, request.timeZone, _id_discussion)
        logger.info("Réponse générée avec succès")
        db = get_con()
        cursor = db.cursor()
        _id = str(uuid.uuid4())
        save_message(_id, user, "user", request.text, cursor)
        save_message(_id_discussion, user, "bot", result, cursor)
        db.commit()
        db.close()
        
        # Préparer la réponse avec les informations de la conversation si disponible
        response = {"result": result, "thread_id": user, "suggestions": suggestions}
        
        # Si c'est une nouvelle conversation, ajouter le label
        response["label"] = None
        if "label" in metadata_:
            response["label"] = metadata_["label"]
        
        return response
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

# @app.post("/threads")
# async def create_thread(thread: ThreadCreate, current_user: str = Depends(get_current_user)):
#     thread_id = create_message(thread, current_user)
#     return {"id": thread_id, "label": thread.label, "user_uuid": current_user}

@app.post("/threads")
async def create_thread(thread: ThreadCreate, current_user: str = Depends(get_current_user)):
    resp = generate_conversation(thread.label, current_user)
    return resp


@app.get("/threads")
async def get_threads(current_user: str = Depends(get_current_user)):
    threads = get_all_threads(current_user)
    return {"threads": threads}

# Root endpoint pour tester l'API
@app.get("/")
def root():
    return {"message": "Bienvenue sur l'API Deep Rice Bot ! Endpoint principal : /answer (POST)"}

router = APIRouter()

def build_messages(user_uuid, clientTime, timeZone, discussion_id, text, thread_id):
    _instru = (
        instruction
        + f"\n Utilise l'uuid {str(user_uuid)} pour les fonctions nécessitant un ID utilisateur."
        + f"\nBase-toi sur la date {str(clientTime)} et le fuseau {str(timeZone)}."
        + f"\nVoici l'uuid de la reponse : {discussion_id}."
    )
    is_new = thread_id is None
    if is_new:
        thread_id = str(uuid.uuid4())
        _instru += "\nCeci est le premier message. Utilise le tool 'create_conversation' pour créer la conversation."
    config = {"configurable": {"thread_id": thread_id}}
    current = get_last_messages(config)
    messages = current + [HumanMessage(content=_instru), HumanMessage(content=text)]
    return messages, config, is_new

@app.get("/history")
def get_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: str = Depends(get_current_user)
):
    """
    Récupère l'historique de l'utilisateur connecté
    """
    try:
        history = get_user_history(current_user, limit=limit, offset=offset)
        return {
            "success": True,
            "data": history,
            "count": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/agent/stream")
def stream_agent(
    text: str,
    user_uuid: str,
    clientTime: str = "",
    timeZone: str = "",
    discussion_id: str = "",
    thread_id: str | None = None,
):
    messages, config, is_new = build_messages(user_uuid, clientTime, timeZone, discussion_id, text, thread_id)

    def event_generator():
        new_thread_id = thread_id
        partial = ""
        for event in agent_app.stream({"messages": messages, "metadata": {"user_id": user_uuid}}, config, stream_mode="values"):
            last = event["messages"][-1].content
            # Simple heuristic: send incremental delta (you can refine diffing)
            delta = last if not partial or not last.startswith(partial) else last[len(partial):]
            partial = last
            payload = {"delta": delta, "full": partial}
            if is_new and "metadata" in event and "thread_id" in event["metadata"]:
                new_thread_id = event["metadata"]["thread_id"]
                payload["thread_id"] = new_thread_id
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

app.include_router(router)

# Lancement : uvicorn api.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)