import uuid

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from api.agent.usualagent import answer
from pydantic import BaseModel
import logging

from api.db.conn import get_con
from api.user.usermanager import insert_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="H", description="API pour ton assistant personnel", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Ajuste pour ton frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnswerRequest(BaseModel):
    text: str
    thread_id: str = None

@app.post("/answer")
def get_answer(request: AnswerRequest = Body(...)):
    try:
        user = request.thread_id
        if request.thread_id is None:
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