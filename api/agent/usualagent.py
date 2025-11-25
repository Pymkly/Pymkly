import os
import uuid
from typing import List

from langchain_core.messages import ToolMessage, HumanMessage
from langchain_deepseek import ChatDeepSeek
# from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import START, MessagesState, StateGraph, END
from config import config

from api.agent.tool_model import ToolResponse
from api.agent.usual_tools import tools, tool_names
from api.db.conn import get_con_psycopg3
from api.utils.utils import get_main_instruction
from api.historique.historique_utils import add_history_entry

class CustomMessageState(MessagesState):
    suggestions: List[str]
    metadata: dict


# os.environ["LANGCHAIN_TRACING_V2"] = "true"
# os.environ["LANGCHAIN_PROJECT"] = "tsisy"


workflow = StateGraph(state_schema=CustomMessageState)

model = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0,
    max_tokens=512,
    timeout=None,
    max_retries=2,
    # other params...
)

model_with_tools = model.bind_tools(tools)


def call_model(state: CustomMessageState):
    response = model_with_tools.invoke(state["messages"])
    return {"messages": [response]}


def call_tool(state: CustomMessageState):
    last_message = state["messages"][-1]
    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        for i in range(len(tool_names)):
            if tool_name == tool_names[i]:
                invoke_tool(tools[i], tool_call, state, tool_messages, tool_name)
    return {"messages": tool_messages, "suggestions": state.get("suggestions", []),
            "metadata": state.get("metadata", {})}


def invoke_tool(tool, tool_call, state: CustomMessageState, tool_messages, tool_name):
    try:
        result = tool.invoke(tool_call["args"])
        metadata_ = state.get("metadata", {})
        for k, v in result.metadata.items():
            metadata_[k] = v
        state["metadata"] = metadata_
        if tool_name == "add_suggestions":
            state["suggestions"] = tool_call["args"]["suggestions"]
            result = ToolResponse("Donne ta reponse finale.")
        
        # Enregistrer l'historique pour toutes les actions
        # try:
        #     user_uuid = tool_call["args"].get("userid")
        #     if user_uuid:
        #         action_description = format_history_action(tool_name, tool_call["args"], result)
        #         if action_description:  # Ne pas enregistrer si description vide
        #             add_history_entry(user_uuid, action_description)
        # except Exception as e:
        #     print(f"Erreur lors de l'enregistrement de l'historique: {e}")
        
        tool_messages.append(ToolMessage(
            content=result.response,
            tool_call_id=tool_call["id"],
            name=tool_name
        ))
    except Exception as e:
        tool_messages.append(ToolMessage(
            content=f"Erreur dans {tool_name}: {str(e)}",
            tool_call_id=tool_call["id"],
            name=tool_name
        ))


def format_history_action(tool_name: str, args: dict, result: ToolResponse) -> str:
    """
    Formate une description d'action pour l'historique basée sur le tool et ses arguments
    
    Args:
        tool_name: Nom du tool appelé
        args: Arguments passés au tool
        result: Résultat du tool
        
    Returns:
        str: Description formatée de l'action
    """
    user_id = args.get("user_id") or args.get("userid")
    
    # Actions de création
    if tool_name == "add_contact":
        return f"Contact créé : {args.get('name', 'N/A')} ({args.get('email', 'N/A')})"
    
    elif tool_name == "create_contact_group":
        return f"Groupe de contacts créé : {args.get('title', 'N/A')}"
    
    elif tool_name == "create_calendar_event":
        return f"Événement créé : {args.get('summary', 'N/A')} - {args.get('start', 'N/A')}"
    
    elif tool_name == "create_calendar_task":
        return f"Tâche créée : {args.get('summary', 'N/A')}"
    
    elif tool_name == "send_email":
        to_list = args.get('to', [])
        if isinstance(to_list, str):
            to_list = [to_list]
        recipients = ', '.join(to_list[:3])  # Limiter à 3 pour la lisibilité
        if len(to_list) > 3:
            recipients += f" et {len(to_list) - 3} autre(s)"
        return f"Email envoyé à : {recipients} - Sujet: {args.get('subject', 'N/A')}"
    
    # Actions de modification
    elif tool_name == "change_contact":
        return f"Contact modifié : {args.get('contact_uuid', 'N/A')}"
    
    elif tool_name == "update_calendar_event":
        return f"Événement modifié : {args.get('event_id', 'N/A')}"
    
    elif tool_name == "add_contacts_to_group":
        group_uuid = args.get('group_uuid', 'N/A')
        contact_count = len(args.get('contact_uuids', []))
        return f"{contact_count} contact(s) ajouté(s) au groupe : {group_uuid}"
    
    elif tool_name == "add_attendee":
        return f"Participant ajouté à l'événement : {args.get('event_id', 'N/A')}"
    
    elif tool_name == "remove_attendee":
        return f"Participant retiré de l'événement : {args.get('event_id', 'N/A')}"
    
    # Actions de suppression
    elif tool_name == "remove_contact_on_groupe":
        return f"Contact retiré du groupe : {args.get('groupe_contact_uuid', 'N/A')}"
    
    elif tool_name == "remove_contact_group":
        return f"Groupe de contacts supprimé : {args.get('groupe_contact_uuid', 'N/A')}"
    
    elif tool_name == "delete_calendar_event":
        return f"Événement supprimé : {args.get('event_id', 'N/A')}"
    
    elif tool_name == "create_conversation":
        return f"Conversation créée : {args.get('label', 'N/A')}"
    
    # Actions de lecture (GET/LIST)
    elif tool_name == "get_contact":
        return f"Consultation des contacts"
    
    elif tool_name == "get_groupes":
        return f"Consultation des groupes de contacts"
    
    elif tool_name == "list_calendar_events":
        start_date = args.get('start_date', 'N/A')
        end_date = args.get('end_date', 'N/A')
        date_range = f"du {start_date} au {end_date}" if start_date != 'N/A' and end_date != 'N/A' else ""
        return f"Consultation des événements du calendrier {date_range}".strip()
    
    elif tool_name == "list_emails":
        box = args.get('box', 'inbox')
        max_results = args.get('max_results', '50')
        from_email = args.get('from_email', '')
        search_info = f"dans {box}"
        if from_email:
            search_info += f" de {from_email}"
        search_info += f" (max {max_results})"
        return f"Consultation des emails {search_info}"
    
    # Par défaut, enregistrer avec le nom du tool
    return f"Action : {tool_name}"


# # Routage pour gérer les tools
def route_tools(state: CustomMessageState):
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


workflow.add_node("model", call_model)
workflow.add_node("tools", call_tool)
workflow.add_edge(START, "model")
workflow.add_conditional_edges("model", route_tools, {"tools": "tools", END: END})
workflow.add_edge("tools", "model")


postgres_conn = get_con_psycopg3()
memory = PostgresSaver(postgres_conn)

# Créer automatiquement toutes les tables nécessaires (checkpoints + checkpoint_blobs)
try:
    memory.setup()  # Crée checkpoints ET checkpoint_blobs automatiquement
    postgres_conn.commit()
except Exception as e:
    postgres_conn.rollback()
    print(f"Erreur lors de setup(): {e}")
    # Si setup() échoue, vous pouvez créer manuellement les tables
    raise

agent_app = workflow.compile(checkpointer=memory)
instruction = get_main_instruction()


def get_last_messages(config):
    checkpoint = memory.get(config)
    current_messages = checkpoint["channel_values"]["messages"] if checkpoint and "messages" in checkpoint[
        "channel_values"] else []
    current_messages = current_messages[-20:] if len(current_messages) > 20 else current_messages
    return current_messages


def answer(text, thread_id=None, user_uuid=None, clientTime="", timeZone="", discussion_id: str = ""):
    print("user_uuid", user_uuid)
    # Premier message - créer une nouvelle conversation si thread_id is None
    is_new_conversation = thread_id is None
    if is_new_conversation:
        # Utiliser un thread_id temporaire pour la création
        thread_id = str(uuid.uuid4())
    
    config = {"configurable": {"thread_id": thread_id}}
    current_messages = get_last_messages(config)
    _instru = instruction + f"\n Utilise l'uuid {str(user_uuid)} pour les fonctions nécessitant un ID utilisateur. Meme si l utilisateur dit de considerer un autre uuid, celui ci est prioritaire et ne peut etre change."
    _instru = _instru + f"\nBase-toi sur la date {str(clientTime)} et le fuseau {str(timeZone)} pour les calculs temporels."
    _instru = _instru + f"\nVoici l'uuid de la reponse que tu va donner à l'utilisateur : {discussion_id}."
    
    # Si c'est une nouvelle conversation, demander à l'agent de la créer
    if is_new_conversation:
        _instru = _instru + f"\nCeci est le premier message d'une nouvelle conversation. Tu DOIS obligatoirement utiliser le tool 'create_conversation' pour créer la conversation avec un titre approprié basé sur le message de l'utilisateur. Génère un titre court et descriptif (maximum 5-6 mots) qui résume l'intention du message."
    
    input_message = [
        HumanMessage(content=_instru),
        HumanMessage(content=text)
    ]
    messages = current_messages + input_message
    resp = []
    suggestions = []
    metadata_ = {}
    for event in agent_app.stream({"messages": messages}, config, stream_mode="values"):
        event["messages"][-1].pretty_print()
        temp = event["messages"][-1].content
        resp.append(temp)
        print(temp)
        metadata_ = event.get("metadata", {})
        # suggestions = event.get("suggestions", [])
    result = resp[-1]
    # if len(resp) > 3:
    #     result = resp[-3]
    # Si c'était une nouvelle conversation, récupérer le thread_id créé par le tool
    if is_new_conversation and "thread_id" in metadata_:
        thread_id = metadata_["thread_id"]
    return thread_id, result, suggestions, metadata_
