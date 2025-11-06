import os
import uuid
from typing import List

from langchain_core.messages import ToolMessage, HumanMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, MessagesState, StateGraph, END

from api.agent.tool_model import ToolResponse
from api.agent.usual_tools import tools, tool_names
from api.db.conn import get_con
from api.utils.utils import get_main_instruction


class CustomMessageState(MessagesState):
    suggestions: List[str]
    metadata: dict


os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = "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"
os.environ["LANGCHAIN_PROJECT"] = "tsisy"


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
        tool_messages.append(ToolMessage(
            content=result.response,
            tool_call_id=tool_call["id"],
            name=tool_name
        ))
    except Exception as e:
        tool_messages.append(ToolMessage(
            content=f"Erreur dans {tool_name}: {str(e)}",  # Renvoie l'erreur
            tool_call_id=tool_call["id"],
            name=tool_name
        ))


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

# memory = MemorySaver()
conn = get_con()
memory = SqliteSaver(conn)
app = workflow.compile(checkpointer=memory)
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
    for event in app.stream({"messages": messages}, config, stream_mode="values"):
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
