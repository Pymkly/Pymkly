from api.agent.tool_model import ToolResponse
from api.db.conn import get_con
import json
from langchain_core.tools import tool
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from fastapi import HTTPException
from datetime import datetime

SCOPES_DRIVE = ['https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = "credentials.json"  # Même fichier que Calendar
SERVICES = {}

db = get_con(row=True)

# Fonction pour avoir le drive service via le dictionnaire
def get_drive_service(user_id: str):
    if user_id not in SERVICES:
        SERVICES[user_id] = {}
        SERVICES[user_id]["drive"] = get_drive_service_db(user_id)

    if "drive" not in SERVICES[user_id]:
        SERVICES[user_id]["drive"] = get_drive_service_db(user_id)
    return SERVICES[user_id]["drive"]

def get_drive_service_db(user_id: str):
    """Retourne un service Google Drive (googleapiclient) en utilisant le refresh_token stocké."""
    conn = get_con()
    cursor = conn.cursor()
    cursor.execute("SELECT refresh_token FROM v_user_credentials WHERE user_uuid = %s and cred_type_value=%s order by created_at desc", (user_id, 1))
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
        "scopes": SCOPES_DRIVE
    }

    creds = Credentials.from_authorized_user_info(creds_data, SCOPES_DRIVE)
    try:
        if not creds or not creds.valid:
            creds.refresh(Request())
    except Exception as e:
        # propagate HTTPException for caller to handle (insufficient_scope / invalid_scope)
        raise HTTPException(status_code=403, detail=f"Impossible de rafraîchir le token Drive: {e}")
    return build('drive', 'v3', credentials=creds)

@tool
def list_drive_files(folder_id: str = None, query: str = None, max_results: int = 20, order_by: str = "modifiedTime desc", user_id: str = None) -> ToolResponse:
    """
    Liste les fichiers et dossiers dans Google Drive.
    Retourne une chaîne lisible contenant id, nom, type (fichier/dossier), taille, date de modification, et propriétaires.
    - folder_id : ID du dossier parent (optionnel, si non fourni liste depuis la racine)
    - query : Requête de recherche Google Drive (ex: "name contains 'rapport'", "mimeType = 'application/pdf'")
    - max_results : Nombre maximum de fichiers à retourner (défaut: 50, max: 1000)
    - order_by : Ordre de tri (défaut: "modifiedTime desc", options: "name", "modifiedTime", "createdTime", "folder", "quotaBytesUsed")
    - user_id : ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne.
    """
    if not user_id:
        return ToolResponse("Erreur : user_id manquant.")
    
    try:
        service = get_drive_service(user_id)
        
        # Construire la requête
        q_parts = []
        
        # Si folder_id est fourni, filtrer par dossier parent
        if folder_id:
            q_parts.append(f"'{folder_id}' in parents")
        
        # Ajouter la requête personnalisée si fournie
        if query:
            q_parts.append(f"({query})")
        
        # Par défaut, exclure les fichiers dans la corbeille
        q_parts.append("trashed = false")
        
        # Construire la requête finale
        q_final = " and ".join(q_parts) if q_parts else "trashed = false"
        
        # Paramètres de la requête
        params = {
            'q': q_final,
            'pageSize': min(max_results, 1000),  # Limiter à 1000 max
            'fields': 'nextPageToken, files(id, name, mimeType, size, modifiedTime, createdTime, owners, shared, webViewLink)',
            'orderBy': order_by
        }
        
        # Exécuter la requête
        results = service.files().list(**params).execute()
        files = results.get('files', [])
        
        if not files:
            return ToolResponse("Aucun fichier trouvé dans Google Drive.")
        
        # Formater les résultats
        result_lines = [f"Trouvé {len(files)} fichier(s) :\n"]
        
        for file in files:
            file_id = file.get('id', 'N/A')
            name = file.get('name', 'Sans nom')
            mime_type = file.get('mimeType', 'N/A')
            
            # Déterminer le type
            if mime_type == 'application/vnd.google-apps.folder':
                file_type = "📁 Dossier"
            elif 'google-apps' in mime_type:
                file_type = f"📄 Google {mime_type.split('.')[-1].capitalize()}"
            else:
                file_type = "📄 Fichier"
            
            # Taille
            size = file.get('size')
            if size:
                size_str = f"{int(size) / 1024:.2f} KB" if int(size) < 1024*1024 else f"{int(size) / (1024*1024):.2f} MB"
            else:
                size_str = "N/A"
            
            # Dates
            modified_time = file.get('modifiedTime', 'N/A')
            created_time = file.get('createdTime', 'N/A')
            
            # Propriétaires
            owners = file.get('owners', [])
            owner_names = ", ".join([owner.get('displayName', owner.get('emailAddress', 'N/A')) for owner in owners])
            
            # Lien de partage
            web_view_link = file.get('webViewLink', 'N/A')
            shared = file.get('shared', False)
            shared_str = "Partagé" if shared else "Privé"
            
            result_lines.append(
                f"\n{file_type}: {name}\n"
                f"  ID: {file_id}\n"
                f"  Type MIME: {mime_type}\n"
                f"  Taille: {size_str}\n"
                f"  Modifié: {modified_time}\n"
                f"  Créé: {created_time}\n"
                f"  Propriétaire(s): {owner_names}\n"
                f"  Statut: {shared_str}\n"
                f"  Lien: {web_view_link}\n"
            )
        
        return ToolResponse("".join(result_lines))
        
    except HttpError as he:
        return ToolResponse(f"Erreur Google Drive API : {str(he)}")
    except Exception as e:
        return ToolResponse(f"Erreur lors de la liste des fichiers : {str(e)}")
