from api.db.conn import get_con
from app import GMAIL_TYPE
import imaplib
from google.oauth2.credentials import Credentials
import os
from google.auth.transport.requests import Request
import json
from imap_tools import MailBox, A
import base64

db = get_con(row=True)

def get_token(user_id: str, type_ : int):
    cursor = db.cursor()
    cursor.execute('''SELECT u.email, v_user_credentials.uuid, user_uuid, refresh_token, cred_type_id, cred_type_label, cred_type_value from v_user_credentials join users u on u.uuid = v_user_credentials.user_uuid where user_uuid=? and cred_type_value=? ''' , (user_id, type_))
    token = cursor.fetchone()
    return dict(token)

def load_credentials(file_path: str):
    with open(file_path, 'r') as f:
        credentials = json.load(f)
    return credentials['web']['client_id'], credentials['web']['client_secret']

# def connect_gmail(user_id: str):
#     token = get_token(user_id, GMAIL_TYPE['value'])['refresh_token']
#     print("token :" + token)
#     mail = imaplib.IMAP4_SSL('imap.gmail.com')
#     mail.log
#     mail.select('inbox')
#     print("ok")

# def connect_gmail(user_id: str):
#     # Charger client_id et client_secret
#     client_id, client_secret = load_credentials('credentials_gmail.json')
#
#     # Récupérer le refresh token
#     token_data = get_token(user_id, GMAIL_TYPE['value'])
#     print("Token data:", token_data)
#     if not token_data or 'refresh_token' not in token_data:
#         raise ValueError("Refresh token non trouvé pour cet utilisateur.")
#
#     # Générer les credentials
#     credentials = Credentials(
#         token=None,
#         refresh_token=token_data['refresh_token'],
#         client_id=client_id,
#         client_secret=client_secret,
#         token_uri="https://oauth2.googleapis.com/token"
#     )
#
#     # Rafraîchir pour obtenir un access token
#     credentials.refresh(Request())
#     access_token = credentials.token.strip()  # Nettoyer les espaces
#     print("Generated access token (cleaned):", access_token)
#
#     # Utiliser l'email Gmail
#     gmail_email = token_data['email']
#     if "@gmail.com" not in gmail_email:
#         raise ValueError("Email Gmail invalide.")
#
#     # Préparer l'authentification XOAUTH2
#     auth_string = f'user={gmail_email}\1auth=Bearer {access_token}\1\1'
#     encoded_auth = base64.b64encode(auth_string.encode()).decode('utf-8')
#     print("Auth string (raw):", auth_string)
#     print("Auth string (base64):", encoded_auth)
#
#     # Connexion IMAP avec debug explicite
#     try:
#         mail = imaplib.IMAP4_SSL('imap.gmail.com')
#         print("Starting authentication...")
#         response = mail.authenticate('XOAUTH2', lambda x: encoded_auth)
#         print("Authentication response:", response)
#         mail.select('inbox')
#         print("Connexion IMAP réussie !")
#         status, data = mail.list()
#         print("Dossiers disponibles :", data)
#     except imaplib.IMAP4.error as e:
#         print(f"Erreur IMAP : {e}")
#     finally:
#         mail.logout()
#

def connect_gmail(user_id: str):
    # Charger client_id et client_secret
    client_id, client_secret = load_credentials('credentials_gmail.json')

    # Récupérer le refresh token
    token_data = get_token(user_id, GMAIL_TYPE['value'])
    print("Token data:", token_data)
    if not token_data or 'refresh_token' not in token_data:
        raise ValueError("Refresh token non trouvé pour cet utilisateur.")

    # Générer les credentials
    credentials = Credentials(
        token=None,
        refresh_token=token_data['refresh_token'],
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=['https://mail.google.com/']  # Scope explicite pour IMAP
    )

    # Rafraîchir pour obtenir un access token
    credentials.refresh(Request())
    access_token = credentials.token
    print("Generated access token:", access_token)

    # Utiliser l'email Gmail
    gmail_email = token_data['email']
    if "@gmail.com" not in gmail_email:
        raise ValueError("Email Gmail invalide.")

    # Préparer l'authentification XOAUTH2 (format Google officiel)
    # Note : Les \1 sont des caractères ASCII 1 (0x01)
    user_bytes = gmail_email.encode('utf-8')
    auth_bytes = b'auth=Bearer ' + access_token.encode('utf-8')
    auth_string = b'\0' + user_bytes + b'\0' + auth_bytes + b'\0' + b'\0'  # Format XOAUTH2 avec bytes
    encoded_auth = base64.b64encode(auth_string).decode('ascii')
    print("Auth string bytes length:", len(auth_string))
    print("Auth string (base64):", encoded_auth)

    # Connexion IMAP
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        print("Starting authentication...")
        response = mail.authenticate('XOAUTH2', lambda x: encoded_auth)
        print("Authentication response:", response)
        mail.select('inbox')
        print("Connexion IMAP réussie !")
        status, data = mail.list()
        print("Dossiers disponibles :", data)
    except imaplib.IMAP4.error as e:
        print(f"Erreur IMAP : {e}")
    finally:
        mail.logout()


connect_gmail('f25d5d9d-b995-4aac-81dc-6686d8082e08')
