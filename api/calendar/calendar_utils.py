import json
import re

from fastapi import HTTPException
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.tools import tool
import pytz
from datetime import datetime

from api.agent.tool_model import ToolResponse
from api.db.conn import get_con

SCOPES_CALENDAR = ['https://www.googleapis.com/auth/calendar' , ]
SCOPES_TASKS = ['https://www.googleapis.com/auth/tasks']
SCOPES_GMAIL = ['https://mail.google.com/']
CREDENTIALS_FILE = "credentials.json"
SERVICES = {}


# Fonction pour avoir le calendar service via le dictionnaire
def get_calendar_service(user_id: str):
    if user_id not in SERVICES:
        SERVICES[user_id] = {}
        SERVICES[user_id]["calendar"] = get_calendar_service_db(user_id)

    if "calendar" not in SERVICES[user_id]:
        SERVICES[user_id]["calendar"] = get_calendar_service_db(user_id)
    return SERVICES[user_id]["calendar"]

# Fonction pour avoir le tasks service via le dictionnaire
def get_tasks_service(user_id: str):
    if user_id not in SERVICES:
        SERVICES[user_id] = {}
        SERVICES[user_id]["tasks"] = get_tasks_service_db(user_id)

    if "tasks" not in SERVICES[user_id]:
        SERVICES[user_id]["tasks"] = get_tasks_service_db(user_id)
    return SERVICES[user_id]["tasks"]


# Fonction pour authentifier et obtenir le service Calendar
def get_calendar_service_db(user_id: str):
    conn = get_con()
    cursor = conn.cursor()
    cursor.execute("SELECT refresh_token FROM v_user_credentials WHERE user_uuid = ? and cred_type_value=? order by created_at desc", (user_id, 1))
    result = cursor.fetchone()
    conn.close()
    if not result:
        raise HTTPException(status_code=401, detail="Utilisateur non authentifié ou token manquant")
    with open(CREDENTIALS_FILE, 'r') as f:
        creds_info = json.load(f)
        client_id = creds_info["web"]["client_id"]
        client_secret = creds_info["web"]["client_secret"]
    print("***INFO***")
    print(result)
    print(client_id)
    print(client_secret)
    print("***Fin INFO***")
    refresh_token = result[0]
    creds_data = {
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": SCOPES_CALENDAR
    }

    creds = Credentials.from_authorized_user_info(creds_data, SCOPES_CALENDAR)
    if not creds or not creds.valid:
        creds.refresh(Request())
    return build('calendar', 'v3', credentials=creds)

def get_tasks_service_db(user_id: str):
    conn = get_con()
    cursor = conn.cursor()
    cursor.execute("SELECT refresh_token FROM v_user_credentials WHERE user_uuid = ? and cred_type_value=? order by created_at desc", (user_id, 1))
    result = cursor.fetchone()
    conn.close()
    if not result:
        raise HTTPException(status_code=401, detail="Utilisateur non authentifié ou token manquant")
    with open(CREDENTIALS_FILE, 'r') as f:
        creds_info = json.load(f)
        client_id = creds_info["web"]["client_id"]
        client_secret = creds_info["web"]["client_secret"]

    refresh_token = result[0]
    print("refresh_token:", refresh_token)
    creds_data = {
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": SCOPES_CALENDAR + SCOPES_TASKS
    }

    creds = Credentials.from_authorized_user_info(creds_data, SCOPES_CALENDAR + SCOPES_TASKS)
    if not creds or not creds.valid:
        creds.refresh(Request())

    # *** DIAGNOSTIC : AFFICHER SCOPES ***
    print(f"*** TOKEN SCOPES: {creds.scopes} ***")
    print(f"*** TOKEN VALID: {creds.valid} ***")


    return build('tasks', 'v1', credentials=creds)

# Tool pour ajouter un invité
@tool
def add_attendee(event_id: str, emails: list= None, send_invitations: bool = True, user_id: str = None) -> ToolResponse:
    """Ajoute un invité à un événement Google Calendar. Params: event_id (ID de l'événement), emails (liste d'emails des invités à ajouter), send_invitations: Si True (défaut), envoie une notification à tous les invités (y compris les nouveaux). Si False, ajoute les invités sans envoyer de notifications. Le modèle DOIT demander à l'utilisateur s'il souhaite envoyer les notifications lors de l'ajout d'invités, user_id (ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne )."""
    if not user_id:
        return ToolResponse("Erreur : user_id manquant.")
    try:
        if emails:
            # Valider l'email
            for email in emails:
                if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
                    return ToolResponse(f"Erreur : email '{email}' n'est pas valide.")

            service = get_calendar_service(user_id)
            # Récupérer l'événement existant
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            # Ajouter l'invité
            attendees = event.get('attendees', [])
            for email in emails:
                if any(attendee['email'] == email for attendee in attendees):
                    return ToolResponse(f"Erreur : l'email '{email}' est déjà dans la liste des invités.")
                attendees.append({'email': email})
            event['attendees'] = attendees
            
            # Envoyer les notifications selon le paramètre send_invitations
            if send_invitations:
                send_updates = 'all'
                notification_msg = " (notification envoyée à tous les invités)"
            else:
                send_updates = 'none'
                notification_msg = " (ajouté sans envoyer de notifications)"
            
            # Mettre à jour l'événement
            updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event, sendUpdates=send_updates).execute()
            message = ",".join([email for email in emails])
            return ToolResponse(f"Invité ajouté ! ID: {event_id} - {updated_event.get('summary', 'Sans titre')} - Invité: {message}{notification_msg}")
        else:
            return ToolResponse("Aucun emails mentionné. Aucune action n'a été faite.")
    except Exception as e:
        return ToolResponse(f"Erreur lors de l'ajout de l'invité : {str(e)}")


# Tool pour retirer un invité
@tool
def remove_attendee(event_id: str, emails: list = None, send_invitations: bool = True, user_id: str = None) -> ToolResponse:
    """Retire un invité d'un événement Google Calendar. Params: event_id (ID de l'événement), emails (emails des invités), send_invitations: Si True (défaut), envoie une notification aux invités restants. Si False, retire les invités sans envoyer de notifications. Le modèle DOIT demander à l'utilisateur s'il souhaite envoyer les notifications si des invités restent après le retrait, user_id (ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne )."""
    if not user_id:
        return ToolResponse("Erreur : user_id manquant.")
    try:
        if emails :
            # Valider l'email
            for email in emails:
                if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
                    return ToolResponse(f"Erreur : email '{email}' n'est pas valide.")

            service = get_calendar_service(user_id)
            # Récupérer l'événement existant
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            # Retirer l'invité
            attendees = event.get('attendees', [])
            for email in emails:
                if not any(attendee['email'] == email for attendee in attendees):
                    return ToolResponse(f"Erreur : l'email '{email}' n'est pas dans la liste des invités.")
            for email in emails:
                attendees = [attendee for attendee in attendees if attendee['email'] != email]
            event['attendees'] = attendees
            
            # Envoyer les notifications selon le paramètre send_invitations
            if send_invitations and len(attendees) > 0:
                send_updates = 'all'
                notification_msg = " (notification envoyée aux autres invités)"
            elif not send_invitations:
                send_updates = 'none'
                notification_msg = " (retiré sans envoyer de notifications)"
            else:
                send_updates = 'none'
                notification_msg = ""
            
            # Mettre à jour l'événement
            updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event, sendUpdates=send_updates).execute()
            message = ",".join([email for email in emails])
            return ToolResponse(f"Invité retiré ! ID: {event_id} - {updated_event.get('summary', 'Sans titre')} - Retiré: {message}{notification_msg}")
        else:
            return ToolResponse("Aucun emails mentionné. Aucune action n'a été faite.")
    except Exception as e:
        return ToolResponse(f"Erreur lors du retrait de l'invité : {str(e)}")

@tool
def delete_calendar_event(event_id: str, event_series_id: str = None, user_id: str = None) -> ToolResponse:
    """Supprime un événement Google Calendar. Param: event_id (ID de l'événement), event_series_id (ID de la série d'événements si != None supprimer toute la série), user_id (ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne )."""
    if not user_id:
        return ToolResponse("Erreur : user_id manquant.")
    try:
        if event_series_id:
            event_id = event_series_id

        service = get_calendar_service(user_id)
        # Vérifier si l'événement existe
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        summary = event.get('summary', 'Sans titre')
        # Supprimer l'événement
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return ToolResponse(f"Événement supprimé ! ID: {event_id} - {summary}")
    except Exception as e:
        return ToolResponse(f"Erreur lors de la suppression : {str(e)}")

@tool
def update_calendar_event(event_id: str, new_start_time: str, new_end_time: str, time_zone: str, new_summary: str, new_description: str, user_id: str = None) -> ToolResponse:
    """Modifie un événement Google Calendar à de nouvelles dates/heures. Params: event_id (ID de l'événement), new_start_time/new_end_time (ISO format ex: '2025-10-01T14:00:00+03:00'), time_zone (time zone de l'utilisateur), new_summary (nouveau titre de l'événement si donné), new_description (nouvelle description de l'événement si donnée), user_id (ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne )."""
    if not user_id:
        return ToolResponse("Erreur : user_id manquant.")
    try:
        # Valider le format ISO
        if not re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$', new_start_time):
            return ToolResponse(f"Erreur : new_start_time '{new_start_time}' n'est pas au format ISO valide (ex: '2025-10-01T14:00:00+03:00').")
        if not re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$', new_end_time):
            return ToolResponse(f"Erreur : new_end_time '{new_end_time}' n'est pas au format ISO valide (ex: '2025-10-01T15:00:00+03:00').")

        service = get_calendar_service(user_id)
        # Récupérer l'événement existant
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        # Mettre à jour les horaires

        if new_description:
            event['description'] = new_description

        if new_summary:
            event['summary'] = new_summary

        if new_start_time and new_end_time:
            event['start']['dateTime'] = new_start_time
            event['end']['dateTime'] = new_end_time
            event['start']['timeZone'] = time_zone
            event['end']['timeZone'] = time_zone

        # Mettre à jour l'événement
        updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        return ToolResponse(f"Événement décalé ! ID: {event_id} - {updated_event.get('summary', 'Sans titre')} de {new_start_time} à {new_end_time}")
    except Exception as e:
        return ToolResponse(f"Erreur lors du décalage : {str(e)}")

# Tool pour lister les événements
@tool
def list_calendar_events(start_date: str, end_date: str, user_id: str = None) -> ToolResponse:
    """Liste les événements Google Calendar entre start_date et end_date (ISO format ex: '2025-10-01T00:00:00+03:00'). . Retourne l'ID, le titre, la date et les invités de chaque événement, user_id (ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne )."""
    if not user_id:
        return ToolResponse("Erreur : user_id manquant.")
    try:
        # Valider le format ISO
        if not re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$', start_date):
            return ToolResponse(f"Erreur : start_date '{start_date}' n'est pas au format ISO valide (ex: '2025-10-01T00:00:00+03:00').")
        if not re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$', end_date):
            return ToolResponse(f"Erreur : end_date '{end_date}' n'est pas au format ISO valide (ex: '2025-10-01T23:59:59+03:00').")

        service = get_calendar_service(user_id)
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_date,
            timeMax=end_date,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        if not events:
            return ToolResponse(f"Aucun événement trouvé entre {start_date} et {end_date}.")
        result = f"Événements entre {start_date} et {end_date}:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'Sans titre')
            event_id = event.get('id', 'ID inconnu')
            event_series_id = event.get('recurringEventId', None)
            attendees = event.get('attendees', [])
            attendee_emails = [attendee['email'] for attendee in attendees] if attendees else []
            result += f"- {summary} (ID: {event_id}) : {start}\n"+ f"- (ID_SERIES: {event_series_id}) \n"+ (f" [Invités: {', '.join(attendee_emails)}]" if attendee_emails else "") + "\n"
        return ToolResponse(result)
    except Exception as e:
        return ToolResponse(f"Erreur lors de la liste : {str(e)}")

# Tool LangChain pour créer un événement (DeepSeek peut l'appeler)
@tool
def create_calendar_event(summary: str, start_time: str, end_time: str, description: str = "", attendees: list = None, time_zone: str = "Indian/Antananarivo", recurrence: str = None, recurrence_interval: int = None, end_date_recurrence: str = None, reminder_minutes: int = 30, send_invitations: bool = True, user_id: str = None) -> ToolResponse:
    """Crée un événement Google Calendar. Params: summary (titre), start_time/end_time (ISO format ex: '2025-10-01T14:00:00'), description, attendees (liste d'emails à inviter pendant l'evenement, optionnel), time_zone (time zone de l'utilisateur), recurrence: Type de répétition ('daily', 'weekly', 'monthly', 'yearly' , 'custom') ou None , recurrence_interval: entier pour l'intervalle (ex: 3 pour tous les 3 jours) , end_date_recurrence: Fin de la série (ISO)  , reminder_minutes: Minutes avant le début pour le rappel (par défaut 30), send_invitations: Si True (défaut), envoie les invitations par email aux invités. Si False, ajoute les invités sans envoyer d'invitations. Le modèle DOIT demander à l'utilisateur s'il souhaite envoyer les invitations si des invités sont présents, user_id (ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne)."""
    if not user_id:
        return ToolResponse("Erreur : user_id manquant.")
    try:
        service = get_calendar_service(user_id)
        event = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time, 'timeZone': time_zone},  # Ajuste le timezone
            'end': {'dateTime': end_time, 'timeZone': time_zone},
        }
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]

        reminders = {
            "useDefault": False,
            "overrides": [
                {
                    "method": "email",
                    "minutes": reminder_minutes
                }
            ]
        }
        event['reminders'] = reminders

        # Gestion de la récurrence avancée
        if recurrence:
            # Par défaut, FREQ selon le type
            freq = recurrence.upper()
            if recurrence == "custom" and recurrence_interval:
                freq = "DAILY"
            rrule = f"RRULE:FREQ={freq}"
            # Ajout de l'intervalle si fourni
            if recurrence_interval:
                rrule += f";INTERVAL={recurrence_interval}"
            # Ajout de la date de fin si fournie
            if end_date_recurrence:
                dt_end = datetime.fromisoformat(end_date_recurrence.replace('Z', '+00:00'))
                if dt_end.tzinfo is None:
                    tz = pytz.timezone(time_zone)
                    dt_end = tz.localize(dt_end)
                rrule += f";UNTIL={dt_end.astimezone(pytz.UTC).strftime('%Y%m%dT%H%M%SZ')}"
            event['recurrence'] = [rrule]

        # Envoyer les notifications aux invités selon le paramètre send_invitations
        if attendees and send_invitations:
            send_updates = 'all'
            notification_msg = " (invitations envoyées aux invités)"
        elif attendees and not send_invitations:
            send_updates = 'none'
            notification_msg = " (invités ajoutés sans envoyer d'invitations)"
        else:
            send_updates = 'none'
            notification_msg = ""
        
        event = service.events().insert(calendarId='primary', body=event, sendUpdates=send_updates).execute()
        return ToolResponse(f"Événement créé ! ID: {event.get('id')} - {summary} de {start_time} à {end_time}"+ (f" avec invités: {', '.join(attendees)}" if attendees else "") + notification_msg)
    except Exception as e:
        return ToolResponse(f"Erreur lors de la création : {str(e)}")
