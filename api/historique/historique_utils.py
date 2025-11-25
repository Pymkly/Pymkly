import uuid
from api.db.conn import get_con

db = get_con()


def add_history_entry(user_uuid: str, action: str) -> dict:
    """
    Ajoute une entrée dans l'historique
    
    Args:
        user_uuid: UUID de l'utilisateur
        action: Description de l'action effectuée
        
    Returns:
        dict: Informations de l'entrée créée
    """
    entry_uuid = str(uuid.uuid4())
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO historique (uuid, user_uuid, action) VALUES (%s, %s, %s)",
        (entry_uuid, user_uuid, action)
    )
    db.commit()
    return {
        "uuid": entry_uuid,
        "user_uuid": user_uuid,
        "action": action
    }


def get_user_history(user_uuid: str, limit: int = 50, offset: int = 0) -> list:
    """
    Récupère l'historique d'un utilisateur
    
    Args:
        user_uuid: UUID de l'utilisateur
        limit: Nombre maximum d'entrées à récupérer
        offset: Nombre d'entrées à ignorer (pour la pagination)
        
    Returns:
        list: Liste des entrées d'historique
    """
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT uuid, user_uuid, action, created_at 
        FROM historique 
        WHERE user_uuid = %s 
        ORDER BY created_at DESC 
        LIMIT %s OFFSET %s
        """,
        (user_uuid, limit, offset)
    )
    rows = cursor.fetchall()
    return [
        {
            "uuid": row[0],
            "user_uuid": row[1],
            "action": row[2],
            "created_at": row[3].isoformat() if row[3] else None
        }
        for row in rows
    ]


def get_recent_history(user_uuid: str, days: int = 7) -> list:
    """
    Récupère l'historique récent d'un utilisateur (derniers N jours)
    
    Args:
        user_uuid: UUID de l'utilisateur
        days: Nombre de jours à récupérer
        
    Returns:
        list: Liste des entrées d'historique
    """
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT uuid, user_uuid, action, created_at 
        FROM historique 
        WHERE user_uuid = %s 
        AND created_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'
        ORDER BY created_at DESC
        """,
        (user_uuid, days)
    )
    rows = cursor.fetchall()
    return [
        {
            "uuid": row[0],
            "user_uuid": row[1],
            "action": row[2],
            "created_at": row[3].isoformat() if row[3] else None
        }
        for row in rows
    ]