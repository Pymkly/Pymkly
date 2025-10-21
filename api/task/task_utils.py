# ...existing code...
import re
from datetime import datetime, timezone
from googleapiclient.errors import HttpError
from langchain_core.tools import tool
import pytz
from typing import Literal

from api.calendar.calendar_utils import get_tasks_service

ISO_WITH_TZ_RE = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$'

@tool
def create_calendar_task(summary: str, description: str, due_date: str, time_zone: str = "Indian/Antananarivo", recurrence: Literal["none", "daily", "weekly", "monthly", "custom"] = "none", recurrence_interval: int = None, end_date_recurrence: str = None, user_id: str = None) -> str:
    """
    Crée une VRAIE tâche dans Google Tasks (comme dans l'UI de Google Calendar).
    Params:
        - summary: Titre de la tâche
        - description: Notes/description
        - due_date: Date d'échéance ISO (ex: '2025-10-21T14:00:00') obligatoire (à demander si non fournie)
        - time_zone: Fuseau horaire (pour conversion si besoin)
        - recurrence: "none", "daily", "weekly", "monthly", "custom"
        - recurrence_interval: Pour "custom" (ex: 3 = tous les 3 jours)
        - end_date_recurrence: Date de fin (ISO)
        - user_id: Obligatoire
    """
    if not user_id:
        return "Erreur : user_id manquant."

    try:
        # Récupérer les credentials du service Calendar et build Tasks API
        tasks_service = get_tasks_service(user_id)
        print("date initiale", due_date)
        dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
        print("date convertie", dt.isoformat())
        
        if dt.tzinfo is None:  # Pas de timezone → AJOUTER
            tz = pytz.timezone(time_zone)
            dt = tz.localize(dt)

        # Créer la tâche de base
        task = {
            'title': summary,
            'notes': description,
            'due': dt.isoformat()
        }

        if recurrence != "none":
            if end_date_recurrence:
                end_dt = pytz.timezone(time_zone).localize(
                    datetime.fromisoformat(end_date_recurrence)
                ).isoformat()
                task['recurrence'] = [f"{recurrence.upper()};INTERVAL={recurrence_interval};UNTIL={end_dt}"]
            else:
                task['recurrence'] = [f"{recurrence.upper()};INTERVAL={recurrence_interval}"]
            
            rec_text = f" (répétition {recurrence} x{recurrence_interval})"
        else:
            rec_text = ""

        # Insérer dans la liste par défaut
        created_task = tasks_service.tasks().insert(tasklist='@default', body=task).execute()

        # return f"Tâche créée dans Google Tasks ! ID: {created_task.get('id')} - {summary} (échéance: {due_date})" + (f" (répétition tous les {recurrence_interval} jours)" if recurrence_interval else "")
        return f"Tâche créée ! ID: {created_task.get('id')} - {summary} (échéance: {due_date}){rec_text}"

    except HttpError as he:
        return f"Erreur Google Tasks API : {str(he)}"
    except Exception as e:
        return f"Erreur création tâche : {str(e)}"
