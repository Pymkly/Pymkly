from api.db.conn import get_con
from app import GMAIL_TYPE
import imaplib

db = get_con(row=True)

def get_token(user_id: str, type_ : int):
    cursor = db.cursor()
    cursor.execute('''SELECT uuid, user_uuid, refresh_token, cred_type_id, cred_type_label, cred_type_value from v_user_credentials where user_uuid=? and cred_type_value=?''', (user_id, type_))
    token = cursor.fetchone()
    return token

def connect_gmail(user_id: str):
    token = get_token(user_id, GMAIL_TYPE['value'])['refresh_token']
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login("hrivonandrasana@gmail.com", token)
    mail.select('inbox')
    print("ok")



connect_gmail('f25d5d9d-b995-4aac-81dc-6686d8082e08')
