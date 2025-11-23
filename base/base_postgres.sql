-- Active: 1763566535683@@127.0.0.1@5432@tsisy
-- Création des extensions si nécessaire
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table users
CREATE TABLE users (
    uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nom_complet VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    mot_de_passe VARCHAR(255) NOT NULL
);

-- Table CredType
CREATE TABLE CredType (
    uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    label VARCHAR(255),
    value INTEGER
);

INSERT INTO CredType(uuid, label, value) VALUES
    ('a468b915-0ea1-476c-990f-78233f888422', 'Calendar', 1),
    ('a468b915-0ea1-476c-990f-78233f888423', 'Gmail', 50);

-- Table user_credentials
CREATE TABLE user_credentials (
    uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_uuid UUID NOT NULL,
    refresh_token TEXT,
    cred_type_id UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_uuid) REFERENCES users(uuid) ON DELETE CASCADE,
    FOREIGN KEY (cred_type_id) REFERENCES CredType(uuid) ON DELETE CASCADE
);

-- Table contacts
CREATE TABLE contacts (
    uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    numero VARCHAR(50) NOT NULL,
    niveau INTEGER DEFAULT 0,
    type_contact_uuid UUID,
    userid UUID NOT NULL,
    FOREIGN KEY (userid) REFERENCES users(uuid) ON DELETE CASCADE,
    FOREIGN KEY (type_contact_uuid) REFERENCES type_contact(uuid) ON DELETE SET NULL
);

-- Table groupe_contacts
CREATE TABLE groupe_contacts (
    uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    userid UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    FOREIGN KEY (userid) REFERENCES users(uuid) ON DELETE CASCADE
);

-- Table groupe_contacts_details
CREATE TABLE groupe_contacts_details (
    uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    groupe_contact_uuid UUID NOT NULL,
    contact_uuid UUID NOT NULL,
    type_destinataire VARCHAR(10) DEFAULT 'to' CHECK(type_destinataire IN ('to', 'cc', 'bcc')),
    FOREIGN KEY (contact_uuid) REFERENCES contacts(uuid) ON DELETE CASCADE,
    FOREIGN KEY (groupe_contact_uuid) REFERENCES groupe_contacts(uuid) ON DELETE CASCADE
);

-- Vue v_contact_group
CREATE OR REPLACE VIEW v_contact_group AS
SELECT gc.uuid,
       gc.userid,
       gc.title,
       c.uuid as contact_uuid,
       c.name as contact_name,
       c.numero as contact_numero,
       c.email as contact_email,
       gcd.type_destinataire
FROM groupe_contacts gc
LEFT JOIN groupe_contacts_details gcd ON gc.uuid = gcd.groupe_contact_uuid
LEFT JOIN contacts c ON gcd.contact_uuid = c.uuid;

-- Table threads
CREATE TABLE threads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_uuid UUID NOT NULL,
    label VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_uuid) REFERENCES users(uuid) ON DELETE CASCADE
);

-- Table discussion_messages
CREATE TABLE discussion_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id UUID NOT NULL,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
);

-- Table discussion_messages_suggestions
CREATE TABLE discussion_messages_suggestions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    discussion_message_id UUID NOT NULL,
    suggestions TEXT,
    FOREIGN KEY (discussion_message_id) REFERENCES discussion_messages(id) ON DELETE CASCADE
);

-- Table reset_password
CREATE TABLE reset_password (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    token VARCHAR(255) NOT NULL,
    expire_date TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(uuid) ON DELETE CASCADE
);

-- Table type_contact
CREATE TABLE type_contact (
    uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nom VARCHAR(255) NOT NULL,
    description TEXT
);

INSERT INTO type_contact (nom, description) VALUES
    ('Personnel', 'Contacts personnels'),
    ('Professionnel', 'Contacts professionnels'),
    ('client', 'Contacts clients'),
    ('Famille', 'Contacts familiaux');

-- Vue v_user_credentials
CREATE OR REPLACE VIEW v_user_credentials AS
SELECT uc.uuid,
       uc.user_uuid,
       uc.refresh_token,
       uc.cred_type_id,
       uc.created_at,
       ct.label cred_type_label,
       ct.value cred_type_value
FROM user_credentials uc
LEFT JOIN CredType ct ON uc.cred_type_id = ct.uuid;

-- Index pour améliorer les performances
CREATE INDEX idx_user_credentials_user_uuid ON user_credentials(user_uuid);
CREATE INDEX idx_contacts_userid ON contacts(userid);
CREATE INDEX idx_groupe_contacts_userid ON groupe_contacts(userid);
CREATE INDEX idx_threads_user_uuid ON threads(user_uuid);
CREATE INDEX idx_discussion_messages_thread_id ON discussion_messages(thread_id);

-- Table checkpoints pour LangGraph PostgresSaver
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    checkpoint JSONB NOT NULL,
    parent_checkpoint_id TEXT,
    metadata JSONB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

-- Index pour la table checkpoints
CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id ON checkpoints(thread_id, checkpoint_ns);
CREATE INDEX IF NOT EXISTS idx_checkpoints_parent ON checkpoints(parent_checkpoint_id);

drop table checkpoints;