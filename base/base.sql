create table users (
    uuid text primary key
);

-- Via sqlite3 /path/to/chat_history.db
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;
ALTER TABLE users RENAME TO users_old;
CREATE TABLE users (
    uuid TEXT PRIMARY KEY,
    nom_complet TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    mot_de_passe TEXT NOT NULL
);
INSERT INTO users (uuid, nom_complet, email, mot_de_passe)
SELECT uuid, '', '', '' FROM users_old;  -- Migrer les anciens UUIDs avec des valeurs par défaut
DROP TABLE users_old;
COMMIT;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS user_credentials (
    uuid TEXT PRIMARY KEY,
    user_uuid TEXT,
    refresh_token TEXT,
    FOREIGN KEY (user_uuid) REFERENCES users(uuid) ON DELETE CASCADE
);
create table contacts (
    uuid text primary key,
    name text,
    numero text,
    email text,
    userid text,
    foreign key (userid) references users(uuid) on delete cascade
);

create table groupe_contacts (
    uuid text primary key,
    userid text,
    title text,
    foreign key (userid) references users(uuid) on delete cascade
);

create table groupe_contacts_details (
    uuid text primary key ,
    groupe_contact_uuid text,
    contact_uuid text,
    foreign key (contact_uuid) references contacts(uuid) on delete cascade ,
    foreign key (groupe_contact_uuid) references groupe_contacts(uuid) on delete cascade
);


create  view v_contact_group as
select gc.uuid,
       gc.userid,
       gc.title,
       c.uuid as contact_uuid,
       c.name as contact_name,
       c.numero as contact_numero,
       c.email as contact_email
    from groupe_contacts gc
    left join groupe_contacts_details gcd on gc.uuid = gcd.groupe_contact_uuid
    left join contacts c on gcd.contact_uuid = c.uuid;

select * from v_contact_group;

CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    user_uuid TEXT NOT NULL,
    label TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_uuid) REFERENCES users(uuid)
);

CREATE TABLE IF NOT EXISTS discussion_messages (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
        );

select * , u.nom_complet
from threads
left join users u on threads.user_uuid = u.uuid;