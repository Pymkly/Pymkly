from api.db.conn import get_con
import json
from langchain_core.tools import tool
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.message import EmailMessage
from fastapi import HTTPException
import re
import base64
import mimetypes
from datetime import datetime
import os


SCOPES_GMAIL = ['https://mail.google.com/']
CREDENTIALS_FILE = "credentials_gmail.json"

db = get_con(row=True)

def get_gmail_service(user_id: str):
    """Retourne un service Gmail (googleapiclient) en utilisant le refresh_token stocké."""
    conn = get_con()
    cursor = conn.cursor()
    cursor.execute("SELECT refresh_token FROM v_user_credentials WHERE user_uuid = ? and cred_type_value=? order by created_at desc", (user_id, 50))
    result = cursor.fetchone()
    conn.close()
    if not result:
        raise HTTPException(status_code=401, detail="Utilisateur non authentifié ou token manquant")
    with open(CREDENTIALS_FILE, 'r') as f:
        creds_info = json.load(f)
        client_id = creds_info["web"]["client_id"]
        client_secret = creds_info["web"]["client_secret"]

    refresh_token = result[0]
    creds_data = {
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": SCOPES_GMAIL
    }

    creds = Credentials.from_authorized_user_info(creds_data, SCOPES_GMAIL)
    try:
        if not creds or not creds.valid:
            creds.refresh(Request())
    except Exception as e:
        # propagate HTTPException for caller to handle (insufficient_scope / invalid_scope)
        raise HTTPException(status_code=403, detail=f"Impossible de rafraîchir le token Gmail: {e}")
    return build('gmail', 'v1', credentials=creds)

@tool
def list_emails(start_date: str = None, end_date: str = None, state:str = None, box: str = "inbox", max_results: str = "50", from_email: str = None, user_id: str = None ) -> str:
    """
    Liste les mails entre start_date et end_date (ISO datetimes).
    Retourne une chaîne lisible contenant id, threadId, from, subject, date et un extrait (snippet).
    - start_date / end_date : ISO format (ex: '2025-10-01T00:00:00+03:00')
    - state: None | "read" | "unread"  -> filtre les mails par état
    - box: "inbox" (défaut) | "sent" | "all" | "drafts" | "spam" | "trash"
    - max_results: nombre maximum de mails à retourner (défaut 50)
    - from_email: filtre par expéditeur (ex: "alice@example.com")
    - user_id : ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne.
    """
    if not user_id:
        return "Erreur : user_id manquant."
    try:
        # Valider / parser les dates ISO
        try:
            dt_start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            dt_end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except Exception:
            return "Erreur : start_date ou end_date non au format ISO attendu."

        after_ts = int(dt_start.timestamp())
        before_ts = int(dt_end.timestamp())

        svc = get_gmail_service(user_id)

        # préparer query et labelIds selon les paramètres
        q_parts = []
        if after_ts:
            q_parts.append(f"after:{after_ts}")
        if before_ts:
            q_parts.append(f"before:{before_ts}")
        if state:
            s = state.lower()
            if s == "unread":
                q_parts.append("is:unread")
            elif s == "read":
                q_parts.append("is:read")
            else:
                return "Erreur : paramètre state invalide (utiliser 'read' ou 'unread')."
            
        if from_email:
            # mettre entre guillemets si adresse contient espace ou nom complet
            safe = from_email.strip()
            if " " in safe:
                q_parts.append(f'from:"{safe}"')
            else:
                q_parts.append(f"from:{safe}")


        q = " ".join(q_parts) if q_parts else None

        label_map = {
            "inbox": ["INBOX"],
            "sent": ["SENT"],
            "drafts": ["DRAFT"],
            "spam": ["SPAM"],
            "trash": ["TRASH"],
            "all": None
        }
        if box not in label_map:
            return "Erreur : paramètre box invalide (inbox|sent|all|drafts|spam|trash)."
        label_ids = label_map[box]

        max_results = int(max_results) if max_results.isdigit() else 50

        if label_ids:
            resp = svc.users().messages().list(userId='me', labelIds=label_ids, q=q, maxResults=max_results).execute()
        else:
            resp = svc.users().messages().list(userId='me', q=q, maxResults=max_results).execute()

        msgs = resp.get('messages', [])
        if not msgs:
            return f"Aucun message trouvé entre {start_date} et {end_date}."

        lines = [f"Mails entre {start_date} et {end_date} (state={state}) : ({len(msgs)} résultats suivis, max {max_results})"]
        for m in msgs:
            msg_id = m['id']
            full = svc.users().messages().get(userId='me', id=msg_id, format='full').execute()
            headers = {h['name']: h['value'] for h in full.get('payload', {}).get('headers', [])}
            subject = headers.get('Subject', '(sans sujet)')
            sender = headers.get('From', '(inconnu)')
            date_h = headers.get('Date', '')
            snippet = full.get('snippet', '')
            labels = full.get('labelIds', []) or []
            msg_state = 'unread' if 'UNREAD' in labels else 'read'
            lines.append(f"- ID: {msg_id} | Thread: {full.get('threadId')} | From: {sender} | Subject: {subject} | Date: {date_h} | State: {msg_state}\n  Snippet: {snippet}")

        return "\n".join(lines)
    except HttpError as he:
        return f"Erreur Gmail API : {str(he)}"
    except Exception as e:
        return f"Erreur lors de la liste des mails : {str(e)}"
    
@tool
def send_email(to: str, subject: str, body: str, cc: list = None, bcc: list = None, attachments: list = None, user_id: str = None) -> str:
    """
    Envoie un email via l'API Gmail pour l'utilisateur `user_id`.
    - to: string ou liste d'emails
    - cc, bcc: list d'emails (optionnel)
    - attachments: liste de chemins de fichiers locaux (optionnel)
    - subject: sujet de l'email
    - body: contenu texte de l'email
    - user_id : ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne.
    Retourne un message texte avec l'ID du message ou une erreur.
    """
    if not user_id:
        return "Erreur : user_id manquant."
    try:
        svc = get_gmail_service(user_id)

        # récupérer l'email de l'utilisateur authentifié
        profile = svc.users().getProfile(userId='me').execute()
        from_email = profile.get('emailAddress', 'me')

        msg = EmailMessage()
        # to peut être une chaîne ou une liste
        if isinstance(to, (list, tuple)):
            msg['To'] = ", ".join(to)
        else:
            msg['To'] = to
        if cc:
            msg['Cc'] = ", ".join(cc) if isinstance(cc, (list, tuple)) else cc
        if bcc:
            msg['Bcc'] = ", ".join(bcc) if isinstance(bcc, (list, tuple)) else bcc
        msg['From'] = from_email
        msg['Subject'] = subject or ""
        msg.set_content(body or "")

        # attachments: chemins de fichiers locaux
        if attachments:
            for path in attachments:
                try:
                    if not os.path.isfile(path):
                        continue
                    ctype, encoding = mimetypes.guess_type(path)
                    if ctype is None:
                        ctype = 'application/octet-stream'
                    maintype, subtype = ctype.split('/', 1)
                    with open(path, 'rb') as f:
                        data = f.read()
                    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=os.path.basename(path))
                except Exception:
                    # ignore a bad attachment and continue
                    continue

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        resp = svc.users().messages().send(userId='me', body={'raw': raw}).execute()
        return f"Message envoyé ! ID: {resp.get('id')}"
    except HttpError as he:
        return f"Erreur Gmail API : {str(he)}"
    except Exception as e:
        return f"Erreur envoi mail : {str(e)}"