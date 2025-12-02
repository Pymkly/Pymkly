from api.agent.suggestions import add_suggestions
from api.contact.contact_utils import add_contact, get_contact, change_contact, add_contacts_to_group, \
    create_contact_group, get_groupes, remove_contact_on_groupe, remove_contact_group
from api.calendar.calendar_utils import create_calendar_event, list_calendar_events, update_calendar_event, \
    delete_calendar_event, add_attendee, remove_attendee
from api.task.task_utils import create_calendar_task
from api.gmail.gmail_utils import list_emails , send_email
from api.threads.threads_utils import create_conversation
from api.drive.drive_utils import list_drive_file_permissions, list_drive_files, get_drive_storage_info, share_drive_file_by_link , share_drive_file, update_drive_file_permission, remove_drive_file_permission, download_drive_file, rename_drive_file

tools = [create_calendar_event, list_calendar_events, update_calendar_event, delete_calendar_event, add_contact, get_contact, change_contact, add_attendee, remove_attendee, add_contacts_to_group, create_contact_group, get_groupes, remove_contact_on_groupe, remove_contact_group , create_calendar_task, list_emails , send_email, create_conversation, list_drive_files , get_drive_storage_info , share_drive_file , share_drive_file_by_link , update_drive_file_permission , remove_drive_file_permission , list_drive_file_permissions , download_drive_file , rename_drive_file ]
tool_names = [tool.name for tool in tools]

