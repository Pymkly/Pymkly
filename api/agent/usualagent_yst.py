import os
import uuid
from typing import List

from langchain_core.messages import HumanMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import create_react_agent

from api.agent.tool_model import ToolResponse
from api.agent.usual_tools import tools
from api.db.conn import get_con
from api.utils.utils import get_main_instruction


# ✅ Configuration LangSmith (tracing + projet)
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "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"
os.environ["LANGCHAIN_PROJECT"] = "tsisy"

# ✅ Initialisation du modèle DeepSeek
model = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0,
    max_tokens=512,
    timeout=None,
    max_retries=2,
)

# ✅ Création de la mémoire SQLite
conn = get_con()
memory = SqliteSaver(conn)

# ✅ Création de l’agent ReAct automatique
app = create_react_agent(
    model=model,
    tools=tools,
    checkpointer=memory
)

# ✅ Récupération de ton instruction principale
instruction = get_main_instruction()


def get_last_messages(config):
    checkpoint = memory.get(config)
    current_messages = checkpoint["channel_values"]["messages"] if checkpoint and "messages" in checkpoint["channel_values"] else []
    # ⚙️ On réduit un peu le contexte pour gagner en performance
    return current_messages[-8:] if len(current_messages) > 8 else current_messages


def answer(text, thread_id=None, user_uuid=None, clientTime="", timeZone="", discussion_id: str = ""):
    print("user_uuid", user_uuid)

    # 🧠 Détection si nouvelle conversation
    is_new_conversation = thread_id is None
    if is_new_conversation:
        thread_id = str(uuid.uuid4())

    config = {"configurable": {"thread_id": thread_id}}
    current_messages = get_last_messages(config)

    # 📝 Construction de l’instruction système
    _instru = instruction + f"\nUtilise l'uuid {str(user_uuid)} pour les fonctions nécessitant un ID utilisateur. Même si l'utilisateur dit d'en changer, celui-ci est prioritaire."
    _instru += f"\nBase-toi sur la date {str(clientTime)} et le fuseau {str(timeZone)} pour les calculs temporels."
    _instru += f"\nVoici l'uuid de la réponse que tu vas donner à l'utilisateur : {discussion_id}."
    
    if is_new_conversation:
        _instru += f"\nCeci est le premier message d'une nouvelle conversation. Tu DOIS obligatoirement utiliser le tool 'create_conversation' pour créer la conversation avec un titre court et descriptif."

    # 🗣️ Préparation des messages
    input_messages = [
        HumanMessage(content=_instru),
        HumanMessage(content=text)
    ]
    messages = current_messages + input_messages

    # ⚡ Exécution du flux (streaming pour performance)
    resp = []
    suggestions = []
    metadata_ = {}

    for event in app.stream({"messages": messages}, config, stream_mode="values"):
        msg = event["messages"][-1]
        msg.pretty_print()
        resp.append(msg.content)
        metadata_ = event.get("metadata", {})

    result = resp[-1]

    # ✅ Mise à jour du thread_id si nouvellement créé
    if is_new_conversation and "thread_id" in metadata_:
        thread_id = metadata_["thread_id"]

    return thread_id, result, suggestions, metadata_
