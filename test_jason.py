from api.agent.suggestions import add_suggestions
from api.contact.contact_utils import add_contact, get_contact, change_contact, add_contacts_to_group, \
    create_contact_group, get_groupes, remove_contact_on_groupe, remove_contact_group
from api.calendar.calendar_utils import create_calendar_event, list_calendar_events, shift_calendar_event, \
    delete_calendar_event, add_attendee, remove_attendee
from api.task.task_utils import create_calendar_task

def get_tool_names(tools):
    """
    Extrait AUTOMATIQUEMENT les noms des tools.
    Input : list de functions @tool
    Output: list de str (noms)
    """
    return [tool.name for tool in tools]

tools = [create_calendar_event, list_calendar_events, shift_calendar_event, delete_calendar_event, add_contact, get_contact, change_contact, add_attendee, remove_attendee, add_contacts_to_group, create_contact_group, get_groupes, remove_contact_on_groupe, remove_contact_group, add_suggestions , create_calendar_task]
tool_names = [tool.name for tool in tools]

print("Outils disponibles :", tool_names)