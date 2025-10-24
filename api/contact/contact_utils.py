import uuid

from api.db.conn import get_con
from langchain_core.tools import tool

conn = get_con()

@tool
def remove_contact_group(groupe_contact_uuid: str, userid: str) -> str:
    """Permet de supprimer un groupe de contact. Params : groupe_contact_uuid (uuid du groupe de contact), user_id (ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne )."""
    try:
        cursor = conn.cursor()
        check_before_remove_contact_group(cursor, groupe_contact_uuid, userid)
        query = "delete from groupe_contacts_details where groupe_contact_uuid = ?"
        cursor.execute(query, (groupe_contact_uuid,))
        query = "delete from groupe_contacts where uuid = ?"
        cursor.execute(query, (groupe_contact_uuid,))
        conn.commit()
        return "Operation réussi"
    except Exception as ex:
        return f"Erreur lors de la suppression du groupe : {ex}"


def check_before_remove_contact_group(cursor, groupe_contact_uuid: str, userid: str):
    query = "select * from groupe_contacts where uuid=? and userid=?"
    cursor.execute(query, (groupe_contact_uuid, userid))
    groupes = cursor.fetchall()
    if len(groupes) == 0:
        raise Exception("Le groupe n'existe pas ou n'appartient pas à l'utilisateur")

@tool
def remove_contact_on_groupe(groupe_contact_uuid: str, contact_uuid: str, userid: str):
    """ Permet d'enlever une personne dans un groupe. Params: groupe_contact_uuid (uuid du groupe de contact), contact_uuid (uuid du contact à elever), user_id (ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne )."""
    try :
        cursor = conn.cursor()
        check_before_remove_contact_on_groupe(cursor, groupe_contact_uuid, contact_uuid, userid)
        query = "select uuid from groupe_contacts_details where contact_uuid=? and groupe_contact_uuid=?"
        cursor.execute(query, (contact_uuid, groupe_contact_uuid))
        group_details = cursor.fetchone()
        if group_details:
            query = "delete from groupe_contacts_details where uuid=?"
            cursor.execute(query, (group_details[0],))
            conn.commit()
            return f"le contact a bien été supprimé du groupe"
        return "Le contact n'est pas associé au groupe"
    except Exception as e:
        return f"Erreur lors de l'enlevement du contact dans le groupe: {e}"



def check_before_remove_contact_on_groupe(cursor, groupe_contact_uuid: str, contact_uuid: str, userid: str):
    query = f"select uuid, userid, title, contact_uuid, contact_name, contact_numero, contact_email from v_contact_group where userid = ?"
    cursor.execute(query, (userid,))
    contacts = cursor.fetchall()
    check_group_exist = False
    check_group_contact_exist = False
    for contact in contacts:
        if contact[0] == groupe_contact_uuid:
            check_group_exist = True
            if contact[3] == contact_uuid:
                check_group_contact_exist = True
    if not check_group_exist:
        raise Exception("Le groupe en question n'existe pas ou n'appartient pas à l'utilisateur")
    if not check_group_contact_exist:
        raise Exception("Ce contact n est pas associé à ce groupe")


@tool
def get_groupes(userid):
    """ Permet de lister les groupes des contacts. Params: user_id (ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne )."""
    try :
        query = f"select uuid, userid, title, contact_uuid, contact_name, contact_numero, contact_email from v_contact_group where userid = ?"
        cursor = conn.cursor()
        cursor.execute(query, (userid,))
        contacts = cursor.fetchall()
        contact_format = [f"{contact[0]},{contact[1]},{contact[2]},{contact[3]},{contact[4]},{contact[5]},{contact[6]}" for contact in contacts]
        resp = "\n".join(contact_format)
        resp = "Contact group uuid, userid, titre du groupe, contact uuid, contact name, contact numero, contact email\n" + resp
        return resp
    except Exception as ex:
        return f"Erreur lors de la recuperation des groupes : {ex}"


@tool
def add_contacts_to_group(group_uuid: str, contact_uuids: list, userid: str) -> str:
    """Ajoute des contacts à un groupe existant. Params: group_uuid (UUID du groupe), contact_uuids (liste d'UUIDs de contacts), user_id (ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne )."""
    try:
        cursor = conn.cursor()
        # Ajouter les contacts au groupe
        added_count = 0
        for contact_uuid in contact_uuids:
            detail_uuid = str(uuid.uuid4())
            check_before_remove_contact_on_groupe(cursor, group_uuid, detail_uuid, userid)
            cursor.execute(
                "INSERT INTO groupe_contacts_details (uuid, groupe_contact_uuid, contact_uuid) VALUES (?, ?, ?)",
                (detail_uuid, group_uuid, contact_uuid))
            added_count += 1
        conn.commit()
        return f"{added_count} contact(s) ajouté(s) au groupe UUID: {group_uuid}."
    except Exception as e:
        return f"Erreur lors de l'ajout au groupe : {str(e)}"

@tool
def create_contact_group(title: str, user_uuid: str, contact_uuids: list):
    """Crée un groupe de contacts. Params: title (titre du groupe), user_id (ID de l'utilisateur connecté, ne peut pas, en aucun cas, être remplacé par un uuid que l'utilisateur donne ), contact_uuids (liste d'UUIDs de contacts)."""
    try:
        group_id = str(uuid.uuid4())
        cursor = conn.cursor()
        cursor.execute("INSERT INTO groupe_contacts (uuid, userid, title) VALUES (?, ?, ?)", (group_id, user_uuid, title))
        for contact_uuid in contact_uuids:
            detail_uuid = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO groupe_contacts_details (uuid, groupe_contact_uuid, contact_uuid) VALUES (?, ?, ?)",
                (detail_uuid, group_id, contact_uuid))
        conn.commit()
        return f"Groupe créé ! UUID: {group_id} - Titre: {title} avec {len(contact_uuids)} contacts."
    except Exception as e:
        return f"Erreur lors de la création du groupe : {str(e)}"



@tool
def change_contact(contact_uuid, name, numero, email, userid):
    """ Permet de modifier un contact pour un utilisateur. Params: contact_uuid(uuid du contact deja enregistré) ,name (nom de la personne), numero (numero de la personne), email (email de la personne), userid (uuid de l'utilisateur rattaché au contact) """
    try :
        query = f"update contacts set name=?, numero=?, email=?, userid=? where uuid=?"
        cursor = conn.cursor()
        cursor.execute(query, (name, numero, email, userid, contact_uuid))
        conn.commit()
        return "Contact modifié avec succés"
    except Exception as e:
        return f"Erreur lors de la modification du contact : {str(e)}"

@tool
def add_contact(name, numero, email, userid , niveau = 0, type_contact = None):
    """ Permet d'enregistrer un contact pour un utilisateur. Params: name (nom de la personne), numero (numero de la personne), email (email de la personne), userid (uuid de l'utilisateur rattaché au contact) , niveau (niveau d'importance du type de contact 0  à 10 . 0:pas tres important , 5:moyennement important , 10: tres important), type_contact (nom du type de contact : Personnel , Professionnel , client , Famille) """
    try :
        _id = str(uuid.uuid4())
        query = f"insert into contacts(uuid, name, numero, email, userid, niveau, type_contact_uuid) values (?, ?, ?, ?, ?, ?, ?)"
        cursor = conn.cursor()
        type_contact = get_type_contact(type_contact)
        cursor.execute(query, (_id, name, numero, email, userid, niveau, type_contact))
        conn.commit()
        return "Contact inseré avec succés"
    except Exception as e:
        return f"Erreur lors de l'enregistrement du contact : {str(e)}"


def get_type_contact(nom):
    """ Permet de récupérer le type de contact en fonction de son nom. Params: nom (nom du type de contact) """
    try:
        query = f"select uuid from type_contact where nom = ?"
        cursor = conn.cursor()
        cursor.execute(query, (nom,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        return f"Erreur lors de la récupération du type de contact : {str(e)}"

@tool
def get_contact(userid):
    """ Permet de lister les contacts d'un utilisateur. Params: userid (uuid de l'utilisateur) """
    try:
        query = f"select contacts.uuid, name, numero, email, userid , niveau, type_contact.nom from contacts join type_contact on contacts.type_contact_uuid = type_contact.uuid where userid = ?"
        cursor = conn.cursor()
        cursor.execute(query, (userid,))
        contacts = cursor.fetchall()
        contact_format = [f"{contact[0]},{contact[1]},{contact[2]},{contact[3]},{contact[4]},{contact[5]},{contact[6]}" for contact in contacts]
        resp = "\n".join(contact_format)
        resp = "uuid, name, numero, email, userid, niveau, type_contact\n" + resp
        return resp
    except Exception as e:
        return f"Erreur lors de la recuperation des contacts pour l utilisateur {str(userid)} : {str(e)}"