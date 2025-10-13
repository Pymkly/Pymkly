import uuid

from api.db.conn import get_con

db = get_con()
conn = get_con(row=True)

def create_message(thread, current_user):
    """thread : objet misy label, current_user : uuid de l'utilisateur"""
    thread_id = str(uuid.uuid4())
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO threads (id, user_uuid, label) VALUES (?, ?, ?)",
        (thread_id, current_user, thread.label)
    )
    db.commit()
    return thread_id

def save_message(_id, thread_id: str, role: str, content: str, cursor):
    cursor.execute(
        "INSERT INTO discussion_messages (id, thread_id, role, content) VALUES (?, ?, ?, ?)",
        (_id, thread_id, role, content)
    )

def get_all_threads(current_user:str):
    cursor = db.cursor()
    cursor.execute("SELECT id, label FROM threads WHERE user_uuid = ?  order by threads.created_at desc",
                   (current_user,))
    threads = [{"id": row[0], "title": row[1], "lastMessage": "", "category": "note", "timestamp": None, "isActive": False} for
        row in cursor.fetchall()]
    if len(threads) > 0:
        threads[0]["isActive"] = True
    return threads

def get_one_threads(thread_id: str):
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM discussion_messages WHERE thread_id = ? ORDER BY created_at ASC",
                   (thread_id,))
    messages = cursor.fetchall()
    return [{"id": str(uuid.uuid4()), "timestamp": None, "content": msg["content"],
                      "isUser": True if msg['role'] == 'user' else False} for msg in messages]