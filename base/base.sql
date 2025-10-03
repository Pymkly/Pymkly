create table users (
    uuid text primary key
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
    foreign key (contact_uuid) references contacts(uuid),
    foreign key (groupe_contact_uuid) references groupe_contacts(uuid) on delete cascade
);

drop view v_contact_group;
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