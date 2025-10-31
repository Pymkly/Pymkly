
from api.agent.tool_model import ToolResponse
from langchain_core.tools import tool

from api.threads.threads import create_message


class ThreadCls:
    def __init__(self, label):
        self.label = label


@tool
def create_conversation(title: str, user_id: str = None) -> ToolResponse:
    """Créer une conversation. Si l'utilisateur donne juste un message, propose un titre à partir du message. Params : title (titre de la conversation), user_id (ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne)."""
    param = ThreadCls(title)
    thread_id = create_message(param, user_id)
    return ToolResponse("Conversation créé avec succes.", {
        "thread_id": thread_id,
        "label" : title
    })
