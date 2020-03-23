create extension "uuid-ossp";

create table families
(
    id       integer generated by default as identity
        constraint families_pkey
            primary key,
    name     varchar(255)            not null,
    creation timestamp default now() not null
);

alter table families
    owner to jolod;

create unique index families_id_uindex
    on families (id);

create table groups
(
    id          serial not null
        constraint groups_pkey
            primary key,
    name        varchar(255),
    description integer
);

alter table groups
    owner to jolod;

create unique index groups_id_uindex
    on groups (id);

create table names_cases
(
    name     varchar(255) not null
        constraint names_genitive_pkey
            primary key,
    genitive varchar(255) not null
);

alter table names_cases
    owner to jolod;

create unique index names_genitive_name_uindex
    on names_cases (name);

create table role
(
    id          serial not null
        constraint role_pkey
            primary key,
    name        varchar(80),
    description varchar(255)
);

alter table roles
    owner to jolod;

create unique index role_id_uindex
    on roles (id);

create unique index role_name_uindex
    on roles (name);

create table families_groups
(
    family_id integer               not null
        constraint families_groups_admins_families_id_fk
            references families,
    confirmed boolean default false not null,
    group_id  integer               not null
        constraint families_groups_groups_id_fk
            references groups,
    constraint families_groups_pk
        primary key (group_id, family_id)
);

alter table families_groups
    owner to jolod;

create index families_groups_admins_family_id_index
    on families_groups (family_id);

create index families_groups_group_id_index
    on families_groups (group_id);

create table group_reminders
(
    "group"    integer                 not null
        constraint reminders_pk
            primary key
        constraint reminders_groups_id_fk
            references groups,
    last_check timestamp default now() not null,
    type       varchar(4),
    last_sent  timestamp
);

alter table groups_reminders
    owner to jolod;

create index reminders_group_index
    on groups_reminders ("group");

create index reminders_last_check_group_index
    on groups_reminders (last_check, "group");

create unique index reminders_group_type_uindex
    on groups_reminders ("group", type);

create table subscription_types
(
    id   serial not null
        constraint subscription_types_pk
            primary key,
    name varchar(255)
);

alter table subscription_types
    owner to jolod;

create unique index subscription_types_id_uindex
    on subscription_types (id);

create table users
(
    id           bigint generated always as identity (maxvalue 2147483647)
        constraint user_pkey
            primary key,
    language     varchar(5) default 'en'::character varying not null,
    birthday     timestamp,
    sex          boolean,
    first_name   varchar(255)                               not null,
    last_name    varchar(255),
    email        varchar(255)                               not null,
    password     varchar(255)                               not null,
    login_count  integer    default 0                       not null,
    confirmed_at timestamp,
    active       boolean    default false                   not null
);

comment on table users is 'Contains all the users';

comment on column users.id is 'Unique identifier of an user';

comment on column users.language is 'Two-letter character code for UI language';

comment on column users.birthday is 'Birthday for birthday gifts';

comment on column users.sex is 'Sex of the person for proper addressing';

comment on column users.first_name is 'First name of the person';

comment on column users.last_name is 'Last name of the person ';

alter table users
    owner to jolod;

create table roles_users
(
    id      bigint  not null
        constraint roles_users_id_fkey
            references users
            on update cascade,
    role_id integer not null
        constraint roles_users_role_id_fkey
            references roles,
    constraint roles_users_pk
        primary key (id, role_id)
);

alter table roles_users
    owner to jolod;

create table shuffles
(
    giver    bigint  not null
        constraint shuffles_giver_fkey
            references users
            on update cascade,
    getter   bigint  not null
        constraint shuffles_getter_fkey
            references users
            on update cascade,
    event_id integer not null
        constraint shuffles_groups_id_fk
            references groups,
    year     integer not null,
    id       integer generated by default as identity (maxvalue 2147483647)
        constraint shuffles_pk
            primary key
);

alter table shuffles
    owner to jolod;

create index shuffles_group_index
    on shuffles (event_id);

create index shuffles_year_index
    on shuffles (year);

create unique index shuffles_id_uindex
    on shuffles (id);

create unique index shuffles_giver_year_uindex
    on shuffles (giver, year);

create unique index shuffles_giver_getter_group_year_uindex
    on shuffles (giver, getter, event_id, year);

create table users_families_admins
(
    user_id   integer               not null
        constraint users_families_admins_user_id_fkey
            references users
            on update cascade,
    family_id integer               not null
        constraint users_families_admins_family_id_fkey
            references families,
    admin     boolean               not null,
    confirmed boolean default false not null,
    constraint users_families_admins_pkey
        primary key (user_id, family_id)
);

comment on table users_families_admins is 'Contains all user-family relationships and if the user is the admin of that family';

alter table users_families_admins
    owner to jolod;

create table users_groups_admins
(
    user_id   integer               not null
        constraint users_groups_admins_user_id_fkey
            references users
            on update cascade,
    group_id  integer               not null
        constraint users_groups_admins_group_id_fkey
            references groups,
    admin     boolean               not null,
    confirmed boolean default false not null,
    constraint users_groups_admins_pk
        primary key (user_id, group_id)
);

alter table users_groups_admins
    owner to jolod;

create index users_groups_admins_group_id_index
    on users_groups_admins (group_id);

create index users_groups_admins_user_id_index
    on users_groups_admins (user_id);

create table user_connections
(
    id               integer                 not null
        constraint user_connection_pk
            primary key,
    user_id          bigint                  not null
        constraint user_connection_user_new_id_fk
            references users
            on update cascade,
    provider_user_id varchar(255)            not null,
    created_at       timestamp default now() not null,
    token            varchar(255),
    provider         varchar(255)            not null
);

alter table users_connections
    owner to jolod;

create unique index user_connection_id_uindex
    on users_connections (id);

create index user_connections_user_id_index
    on users_connections (user_id);

create table subscriptions
(
    user_id      integer              not null
        constraint subscriptions_pk
            primary key
        constraint subscriptions_user_id_fk
            references users
            on update cascade,
    type_id      integer              not null
        constraint subscriptions_subscription_types_id_fk
            references subscription_types,
    until        timestamp            not null,
    active       boolean default true not null,
    purchased_by integer              not null
        constraint subscriptions_users_id_fk
            references users
);

alter table subscriptions
    owner to jolod;

create unique index subscriptions_user_id_type_uindex
    on subscriptions (user_id, type_id);

create index subscriptions_active_purchased_by_index
    on subscriptions (active, purchased_by);

create table emails
(
    email     varchar                 not null
        constraint emails_pk
            primary key,
    verified  boolean   default false not null,
    "primary" boolean   default false not null,
    user_id   integer                 not null
        constraint emails_new_user_new_id_fk
            references users,
    added     timestamp default now() not null
);

alter table emails
    owner to jolod;

create unique index emails_email_uindex
    on emails (email);

create index emails_user_id_index
    on emails (user_id);

create trigger update_email_trigger
    before insert or update or delete
    on emails
    for each row
execute procedure deal_with_email_changes();

create unique index user_new_id_uindex
    on users (id);

create unique index users_email_uindex
    on users (email);

create trigger user_update_trigger
    before insert or update or delete
    on users
    for each row
execute procedure deal_with_user_changes();

create table passwords
(
    user_id  bigint                  not null
        constraint passwords_new_user_id_fkey
            references users,
    password varchar(255)            not null
        constraint passwords_pk
            primary key
        constraint passwords_new_password_key
            unique,
    active   boolean   default false not null,
    created  timestamp default now() not null
);

alter table users_passwords
    owner to jolod;

create index passwords_user_id_index
    on users_passwords (user_id);

create table audit_events_types
(
    id          serial                                      not null
        constraint event_types_new_pkey
            primary key,
    name        varchar(255)  default ''::character varying not null,
    description varchar(1024) default ''::character varying not null
);

alter table audit_events_types
    owner to jolod;

create table audit_events
(
    event_type_id integer                 not null
        constraint audit_events_new_audit_events_types_new_id_fk
            references audit_events_types,
    "when"        timestamp default now() not null,
    id            bigint generated always as identity (maxvalue 2147483647)
        constraint audit_events_pk
            primary key,
    user_id       bigint                  not null
        constraint audit_events_new_user_new_id_fk
            references users,
    ip            varchar(255)
);

alter table audit_events
    owner to jolod;

create unique index audit_events_new_id_uindex
    on audit_events (id);

create table event_types
(
    id   integer generated always as identity
        constraint event_types_pkey
            primary key,
    name varchar(255) not null
);

alter table event_types
    owner to jolod;

create table events
(
    id         integer generated always as identity
        constraint events_pkey
            primary key,
    created_at timestamp default now() not null,
    name       varchar(255)            not null,
    event_at   timestamp,
    group_id   integer                 not null
        constraint events_group_id_fkey
            references groups,
    event_type integer   default 1     not null
        constraint events_event_types_id_fk
            references event_types
);

alter table events
    owner to jolod;

create index events_group_id_index
    on events (group_id);

create table notifications
(
    id         integer generated always as identity
        constraint news_pkey
            primary key,
    user_id    integer                    not null
        constraint news_user_id_fkey
            references users
        constraint notifications_users_id_fk
            references users,
    created_at timestamp    default now() not null,
    text       varchar(1024)              not null,
    url        varchar(255) default NULL::character varying,
    dismissed  boolean      default false not null,
    deleted    boolean      default false not null
);

alter table users_notifications
    owner to jolod;

create index notifications_user_id_index
    on users_notifications (user_id);

create table deleted_emails
(
    email     varchar                 not null
        constraint deleted_emails_pkey
            primary key,
    verified  boolean   default false not null,
    "primary" boolean   default false not null,
    user_id   integer                 not null
        constraint deleted_emails_user_id_fkey
            references users,
    added     timestamp               not null,
    deleted   timestamp default now() not null
);

alter table deleted_emails
    owner to jolod;

create unique index deleted_emails_email_uindex
    on deleted_emails (email);

create table wishlist_status_types
(
    id   integer generated always as identity
        constraint wishlist_status_types_pkey
            primary key,
    name varchar(255) not null
);

alter table wishlist_status_types
    owner to jolod;

create table wishlists
(
    user_id      integer       not null
        constraint wishlists_users_id_fk
            references users,
    item         varchar(1024) not null,
    status       integer
        constraint wishlists_wishlist_status_types_id_fk
            references wishlist_status_types,
    purchased_by integer
        constraint wishlists_purchased_by_fkey
            references users
            on update cascade,
    id           bigint generated by default as identity (maxvalue 2147483647)
        constraint wishlists_note_id_pk
            primary key,
    event_id     integer       not null
        constraint wishlists_event_id_fkey
            references events
);

alter table wishlists
    owner to jolod;

create unique index wishlists_note_id_uindex
    on wishlists (id);

create trigger wishlist_update_trigger
    before delete
    on wishlists
    for each row
execute procedure deal_with_wishlist_changes();

create table archived_wishlists
(
    id           bigint generated by default as identity
        constraint archived_wishlists_pkey
            primary key,
    item         varchar(1024) not null,
    status       integer
        constraint archived_wishlists_status_fkey
            references wishlist_status_types,
    purchased_by integer
        constraint archived_wishlists_purchased_by_fkey
            references users,
    user_id      integer       not null
        constraint archived_wishlists_user_id_fkey
            references users,
    event_id     integer       not null
        constraint archived_wishlists_event_id_fkey
            references events,
    received     timestamp default now()
);

alter table archived_wishlists
    owner to jolod;

create unique index archived_wishlists_note_id_uindex
    on archived_wishlists (id);

create index archived_wishlists_user_id_index
    on archived_wishlists (user_id);

create index archived_wishlists_purchased_user_id
    on archived_wishlists (purchased_by);

create index archived_wishlists_event_id
    on archived_wishlists (event_id);

