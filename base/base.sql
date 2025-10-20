-- Active: 1760701096431@@127.0.0.1@3306
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

create table CredType (
    uuid text primary key ,
    label text,
    value int
);

insert into CredType(uuid, label, value) values
    ('a468b915-0ea1-476c-990f-78233f888422', 'Calendar', 1);

pragma foreign_keys = OFF;
BEGIN transaction ;
alter table user_credentials rename to user_cred_old;

CREATE TABLE IF NOT EXISTS user_credentials (
    uuid TEXT PRIMARY KEY,
    user_uuid TEXT,
    refresh_token TEXT,
    cred_type_id text,
    FOREIGN KEY (user_uuid) REFERENCES users(uuid) ON DELETE CASCADE,
    FOREIGN KEY (cred_type_id) references CredType(uuid) on delete cascade
);
INSERT INTO user_credentials (uuid, user_uuid, refresh_token, cred_type_id)
SELECT uuid, user_uuid, refresh_token, 'a468b915-0ea1-476c-990f-78233f888422' FROM user_cred_old;  -- Migrer les anciens UUIDs avec des valeurs par défaut
DROP TABLE user_cred_old;
commit ;
pragma foreign_keys = ON;

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


create table if not exists discussion_messages_suggestions (
    id text PRIMARY KEY ,
    discussion_message_id text,
    suggestions text,
    foreign key (discussion_message_id) references discussion_messages(id)
);

create table reset_password(
    id text primary key ,
    user_id text,
    token text,
    expire_date timestamp
);

-- ajoute created_at
pragma foreign_keys = OFF;
BEGIN transaction ;
alter table user_credentials rename to user_cred_old;

CREATE TABLE IF NOT EXISTS user_credentials (
    uuid TEXT PRIMARY KEY,
    user_uuid TEXT,
    refresh_token TEXT,
    cred_type_id text,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_uuid) REFERENCES users(uuid) ON DELETE CASCADE,
    FOREIGN KEY (cred_type_id) references CredType(uuid) on delete cascade
);
INSERT INTO user_credentials (uuid, user_uuid, refresh_token, cred_type_id)
SELECT uuid, user_uuid, refresh_token, 'a468b915-0ea1-476c-990f-78233f888422' FROM user_cred_old;  -- Migrer les anciens UUIDs avec des valeurs par défaut
DROP TABLE user_cred_old;
commit ;
pragma foreign_keys = ON;

create view if not exists v_user_credentials as
select uc.uuid,
       uc.user_uuid,
       uc.refresh_token,
       uc.cred_type_id,
       uc.created_at,
       ct.label cred_type_label,
       ct.value cred_type_value
from user_credentials uc
left join CredType ct on uc.cred_type_id=ct.uuid;