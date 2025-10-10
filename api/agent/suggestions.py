import uuid

from langchain_core.tools import tool

from api.db.conn import get_con

conn = get_con()

@tool
def add_suggestions(response_uuid: str, suggestions: list[str]):
    """Permet d'enregistrer une liste de suggestions des nouvelles requêtes que l'utilisateur peuvent posées après ta réponse. Params : response_uuid (uuid de ta réponse, c'est donnée au début), suggestions (la liste de suggestions)"""
    cursor = conn.cursor()
    for suggestion in suggestions:
        _id = str(uuid.uuid4())
        cursor.execute("insert into discussion_messages_suggestions(id, discussion_message_id, suggestions) values (?, ?, ?)", (_id, response_uuid, suggestion))
    conn.commit()
    return "la suggestion a été ajouté dans la base, tu peux maintenant donner la réponse finale"

def get_suggestions(response_uuid: str):
    cursor = conn.cursor()
    cursor.execute("select suggestions from discussion_messages_suggestions where discussion_message_id = ?", (response_uuid,))
    resp = cursor.fetchall()
    return [r[0] for r in resp]