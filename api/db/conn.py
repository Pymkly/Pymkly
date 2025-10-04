import sqlite3

def get_con(row=False):
    conn = sqlite3.connect("chat_history.db", check_same_thread=False)
    if row:
        conn.row_factory = sqlite3.Row
    return conn