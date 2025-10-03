import sqlite3

def get_con():
    conn = sqlite3.connect("chat_history.db", check_same_thread=False)
    return conn