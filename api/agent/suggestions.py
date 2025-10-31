from langchain_core.tools import tool

from api.agent.tool_model import ToolResponse
from api.db.conn import get_con

conn = get_con()

@tool
def add_suggestions(response_uuid: str, suggestions: list[str]):
    """Permet d'enregistrer une liste de suggestions des nouvelles requêtes que l'utilisateur peuvent posées après ta réponse. Params : response_uuid (uuid de ta réponse, c'est donnée au début), suggestions (la liste de suggestions)"""
    return ToolResponse("")