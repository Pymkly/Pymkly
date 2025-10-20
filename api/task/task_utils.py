# ...existing code...
import re
from datetime import datetime, timezone
from googleapiclient.errors import HttpError
from langchain_core.tools import tool
import pytz

from api.calendar.calendar_utils import get_tasks_service

ISO_WITH_TZ_RE = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$'

@tool
def create_calendar_task(summary: str, description: str, due_date: str, time_zone: str = "Indian/Antananarivo", recurrence_interval: int = None, end_date_recurrence: str = None, user_id: str = None) -> str:
    """
    Crée une VRAIE tâche dans Google Tasks (comme dans l'UI de Google Calendar).
    Params:
      - summary: Titre de la tâche
      - description: Notes/description
      - due_date: Date d'échéance ISO (ex: '2025-10-21T14:00:00')
      - time_zone: Fuseau horaire (pour conversion si besoin)
      - recurrence_interval: Optionnel, pour répétition (en jours) - Note: Tasks n'a pas de récurrence native, on simule via description
      - end_date_recurrence: Optionnel, date de fin de récurrence ISO
      - user_id: Obligatoire
    """
    if not user_id:
        return "Erreur : user_id manquant."

    try:
        print("utilisation de la fonction tache")
        # Récupérer les credentials du service Calendar et build Tasks API
        tasks_service = get_tasks_service(user_id)
        dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
        
        if dt.tzinfo is None:  # Pas de timezone → AJOUTER
            tz = pytz.timezone(time_zone)
            dt = tz.localize(dt)

        # Créer la tâche de base
        task = {
            'title': summary,
            'notes': description,
            'due': dt.isoformat()
        }

        # Insérer dans la liste par défaut
        created_task = tasks_service.tasks().insert(tasklist='@default', body=task).execute()

        return f"Tâche créée dans Google Tasks ! ID: {created_task.get('id')} - {summary} (échéance: {due_date})" + (f" (répétition tous les {recurrence_interval} jours)" if recurrence_interval else "")

    except HttpError as he:
        return f"Erreur Google Tasks API : {str(he)}"
    except Exception as e:
        return f"Erreur création tâche : {str(e)}"
