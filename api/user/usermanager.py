def insert_user(new_uuid, conn):
    _id = str(new_uuid)
    cursor = conn.cursor()
    cursor.execute("insert into users(uuid) values (%s)", (_id,))
    conn.commit()

def list_users(conn):
    cursor = conn.cursor()
    cursor.execute("select uuid from users")
    result = cursor.fetchall()
    users = [res[0] for res in result]
    return users