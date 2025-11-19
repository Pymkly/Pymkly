import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from config import config
import os

def get_con_sqlite(row=False):
    conn = sqlite3.connect("chat_history.db", check_same_thread=False)
    if row:
        conn.row_factory = sqlite3.Row
    return conn

def get_con(row=False):
    """
    Retourne une connexion PostgreSQL.
    row=True : retourne un cursor avec RealDictCursor pour accéder aux colonnes par nom
    """
    # Récupérer les paramètres de connexion depuis config ou variables d'environnement
    db_config = {
        'host': 'localhost',
        'port': '5432',
        'database': 'tsisy',
        'user': 'postgres',
        'password': 'itu16'
    }
    
    conn = psycopg2.connect(**db_config)
    
    if row:
        # Pour compatibilité avec row_factory de SQLite
        conn.cursor_factory = RealDictCursor
    
    return conn