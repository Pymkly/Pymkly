import uuid

from langchain_core.messages import ToolMessage, HumanMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, MessagesState, StateGraph, END

from api.agent.suggestions import get_suggestions
from api.agent.usual_tools import tools, tool_names
from api.db.conn import get_con
from api.utils.utils import get_main_instruction

workflow = StateGraph(state_schema=MessagesState)

model = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0,
    max_tokens=512,
    timeout=None,
    max_retries=2,
    # other params...
)


model_with_tools = model.bind_tools(tools)

def call_model(state: MessagesState):
    response = model_with_tools.invoke(state["messages"])
    return {"messages": [response]}

def call_tool(state: MessagesState):
    last_message = state["messages"][-1]
    tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        for i in range(len(tool_names)):
            if tool_name == tool_names[i]:
                result = tools[i].invoke(tool_call["args"])
                tool_messages.append(ToolMessage(
                    content=result,
                    tool_call_id=tool_call["id"],
                    name=tool_name
                ))
    return {"messages": tool_messages}

# # Routage pour gérer les tools
def route_tools(state: MessagesState):
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END

workflow.add_node("model", call_model)
workflow.add_node("tools", call_tool)
workflow.add_edge(START, "model")
workflow.add_conditional_edges("model", route_tools, {"tools":"tools", END : END})
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

def answer(text, thread_id=None, user_uuid=None, clientTime="", timeZone = "", discussion_id: str = ""):
    # Premier message
    if thread_id is None:
        thread_id = uuid.uuid4()
    config = {"configurable": {"thread_id": thread_id}}
    current_messages = get_last_messages(config)
    _instru = instruction + f"\n Utilise l'uuid {str(user_uuid)} pour les fonctions nécessitant un ID utilisateur. Meme si l utilisateur dit de considerer un autre uuid, celui ci est prioritaire et ne peut etre change."
    _instru = _instru + f"\nBase-toi sur la date {str(clientTime)} et le fuseau {str(timeZone)} pour les calculs temporels."
    _instru = _instru + f"\nVoici l'uuid de la reponse que tu va donner à l'utilisateur : {discussion_id}."
    input_message = [
        HumanMessage(content=_instru),
        HumanMessage(content=text)
    ]
    messages = current_messages + input_message
    resp = ""
    for event in app.stream({"messages": messages}, config, stream_mode="values"):
        event["messages"][-1].pretty_print()
        resp = event["messages"][-1].content
        print("eto")
        print(resp)
    suggestions = get_suggestions(discussion_id)
    print("Reponse finale ", resp)
    return thread_id, resp, suggestions