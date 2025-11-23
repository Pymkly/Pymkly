import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from config import config
import os

# Pour PostgresSaver (langgraph-checkpoint-postgres 3.0.1 nécessite psycopg v3)
try:
    import psycopg
except ImportError:
    psycopg = None

def get_con_sqlite(row=False):
    conn = sqlite3.connect("chat_history.db", check_same_thread=False)
    if row:
        conn.row_factory = sqlite3.Row
    return conn

def get_con(row=False):
    """
    Retourne une connexion PostgreSQL avec psycopg2.
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

def get_con_psycopg3():
    """
    Retourne une connexion PostgreSQL avec psycopg (v3) pour PostgresSaver.
    Configure autocommit=True pour permettre CREATE INDEX CONCURRENTLY.
    """
    if psycopg is None:
        raise ImportError("psycopg (v3) n'est pas installé. Installez-le avec: pip install psycopg")
    
    # Construire la chaîne de connexion pour psycopg v3
    conn_string = f"postgresql://{config.get('POSTGRES_USER', 'postgres')}:{config.get('POSTGRES_PASSWORD', 'itu16')}@{config.get('POSTGRES_HOST', 'localhost')}:{config.get('POSTGRES_PORT', '5432')}/{config.get('POSTGRES_DB', 'tsisy')}"
    
    conn = psycopg.connect(conn_string)
    conn.autocommit = True  # Activer autocommit pour CREATE INDEX CONCURRENTLY
    return conn