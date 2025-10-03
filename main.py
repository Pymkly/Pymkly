from api.agent.usualagent import answer
import uuid

from api.db.conn import get_con
from api.user.usermanager import insert_user
from api.utils.utils import chose_user

message, users = chose_user()
print(message)
chose = int(input("Votre choix : "))


user = None
if chose == 0:
    user = uuid.uuid4()
    conn = get_con()
    insert_user(user, conn)
    conn.close()

else:
    print(users)
    user = uuid.UUID(users[chose-1])
while True:
    text = input("Demande : ")
    user, resp = answer(text, user)
