from api.db.conn import get_con
from app import GMAIL_TYPE
import json
import base64
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.message import EmailMessage
from fastapi import HTTPException
SCOPES_GMAIL = ['https://mail.google.com/']
CREDENTIALS_FILE = "credentials_gmail.json"

db = get_con(row=True)

def get_gmail_service(user_id: str):
    """Retourne un service Gmail (googleapiclient) en utilisant le refresh_token stocké."""
    conn = get_con()
    cursor = conn.cursor()
    cursor.execute("SELECT refresh_token FROM v_user_credentials WHERE user_uuid = ? and cred_type_value=? order by created_at desc", (user_id, GMAIL_TYPE['value']))
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

def list_messages(user_id: str):
    svc = get_gmail_service(user_id)
    resp = svc.users().messages().list(userId='me', maxResults=10).execute()
    msgs = resp.get('messages', [])
    print("Found:", len(msgs))
    return msgs

def get_token(user_id: str, type_ : int):
    cursor = db.cursor()
    cursor.execute('''SELECT u.email, v_user_credentials.uuid, user_uuid, refresh_token, cred_type_id, cred_type_label, cred_type_value 
                      from v_user_credentials join users u on u.uuid = v_user_credentials.user_uuid 
                      where user_uuid=? and cred_type_value=? order by created_at desc''' , (user_id, type_))
    token = cursor.fetchone()
    return dict(token) if token else None

def load_credentials(file_path: str):
    with open(file_path, 'r') as f:
        credentials = json.load(f)
    return credentials['web']['client_id'], credentials['web']['client_secret']

def list_messages_str(user_id: str):
    svc = get_gmail_service(user_id)
    resp = svc.users().messages().list(userId='me', maxResults=10).execute()
    msgs = resp.get('messages', [])
    results = []

    def _get_text_from_payload(p):
        # Try to extract text from payload or its parts (handles multipart)
        if not p:
            return ""
        body = p.get('body', {}).get('data')
        if body:
            try:
                return base64.urlsafe_b64decode(body.encode('utf-8')).decode('utf-8', errors='replace')
            except Exception:
                return ""
        for part in p.get('parts', []) or []:
            text = _get_text_from_payload(part)
            if text:
                return text
        return ""

    for m in msgs:
        msg_id = m['id']
        full = svc.users().messages().get(userId='me', id=msg_id, format='full').execute()
        headers = {h['name']: h['value'] for h in full.get('payload', {}).get('headers', [])}
        snippet = full.get('snippet', '')
        body = _get_text_from_payload(full.get('payload', {})) or snippet

        results.append({
            'id': msg_id,
            'threadId': full.get('threadId'),
            'from': headers.get('From'),
            'to': headers.get('To'),
            'subject': headers.get('Subject'),
            'date': headers.get('Date'),
            'snippet': snippet,
            'body_preview': body[:200]  # preview to avoid huge prints
        })

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return results


list_messages_str('e43604e475138836c2d9d06012e09070')