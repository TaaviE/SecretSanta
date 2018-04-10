#!/usr/bin/python3
# coding=utf-8
# author=Taavi Eomäe

#####
# TODO:
# * Add marking gifts as bougth
#
# Known flaws:
# * SecretSanta can't match less than two people or people from less than one family
####

# Plotting
import matplotlib as pylab
from flask_wtf import RecaptchaField

pylab.use("Agg")  # Because we won't have a GUI on the server itself
import matplotlib.pyplot as plotlib
import networkx as netx

# Graphing
import secretsanta

# Utilities
import copy
import datetime
import random
import base64
import json
import os
from Cryptodome.Cipher import AES

# Flask
from flask import g, request, render_template, session, redirect, send_from_directory
from flask_security import login_required, logout_user, SQLAlchemyUserDatastore, forms, Security
from flask_login import current_user
from flask_mail import Message

# App specific config
from config import Config, db, app, mail

# Database models
from models import family_model, shuffles_model, groups_model, users_groups_admins_model, \
    users_families_admins_model, names_model, wishlist_model

# Recursion fix
import sys

sys.setrecursionlimit(2000)

# Error reporting
from raven.contrib.flask import Sentry

sentry = Sentry(app,
                dsn=Config.SENTRY_URL,
                logging=True)

# Setup Flask-Security
userroles = db.Table(
    "roles_users",
    db.Column("id", db.Integer(), db.ForeignKey("user.id")),
    db.Column("role_id", db.Integer(), db.ForeignKey("role.id"))
)

from models import users_model

user_datastore = SQLAlchemyUserDatastore(db,
                                         users_model.User,
                                         users_model.Role)


class ExtendedRegistrerForm(forms.RegisterForm):
    username = forms.StringField("Eesnimi", [forms.Required()])
    recaptcha = RecaptchaField("Captcha")


class ExtendedResetForm(forms.ResetPasswordForm):
    recaptcha = RecaptchaField("Captcha")


class ExtendedConfirmationForm(forms.SendConfirmationForm):
    recaptcha = RecaptchaField("Captcha")


class ExtendedForgotPasswordForm(forms.ForgotPasswordForm):
    recaptcha = RecaptchaField("Captcha")


security = Security(app, user_datastore,
                    confirm_register_form=ExtendedRegistrerForm,
                    reset_password_form=ExtendedResetForm,
                    send_confirmation_form=ExtendedConfirmationForm,
                    forgot_password_form=ExtendedForgotPasswordForm)

# Background scheduling task
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger


def remind_to_add(rate_limit=True):
    print(get_timestamp() + " Started sending adding reminders")
    now = datetime.datetime.now()
    try:
        with open("remind_to_add", "r+") as timer_file:
            lastexec = timer_file.read()
            lastexec = datetime.datetime(*map(int, reversed(lastexec.split("/"))))

            if now - lastexec < datetime.timedelta(days=30):
                print(get_timestamp() + " Adding reminders were rate-limited")
                if rate_limit:
                    return
            else:
                timer_file.seek(0)
                timer_file.write(get_timestamp_string(now))
    except Exception:
        print(get_timestamp() + " Adding reminders rate-limit file was not found")
        with open("remind_to_add", "w") as timer_file:
            timer_file.write(get_timestamp_string(now))

    for user in users_model.User.query:
        if user.last_activity_at:
            if now - datetime.datetime(*map(int, user.last_activity_at.split("/"))) < datetime.timedelta(days=15):
                continue

        email_to_send = "Tere,\n"
        email_to_send += "Tegemist on väikese meeldetuletusega enda nimekirja koostamisele hakata mõtlema\n"
        email_to_send += "\n"
        email_to_send += "Kirja saavad kõik kasutajad kes ei ole vähemalt 15 päeva sisse loginud\n"
        email_to_send += "Jõulurakendus 🎄"

        mail.send_message(subject="Meeldetuletus kinkide kohta",
                          body=email_to_send,
                          recipients=[user.email])

    print(get_timestamp() + " Finished sending adding reminders")


def remind_to_buy(rate_limit=True):
    print(get_timestamp() + " Started sending purchase reminders")
    now = datetime.datetime.now()
    try:
        with open("remind_to_buy", "r+") as timer_file:
            lastexec = timer_file.read()
            lastexec = datetime.datetime(*map(int, reversed(lastexec.split("/"))))

            if now - lastexec < datetime.timedelta(days=15):
                print(get_timestamp() + " Buying reminders were rate-limited")
                if rate_limit:
                    return
            else:
                timer_file.seek(0)
                timer_file.write(get_timestamp_string(now))
    except Exception:
        print(get_timestamp() + " Reminder to buy timer file was not found")
        with open("remind_to_buy", "w") as timer_file:
            timer_file.write(get_timestamp_string(now))

    for user in users_model.User.query:
        marked_entries = get_person_marked(user.id)
        items_to_purchase = []
        for entry in marked_entries:
            if entry.status == wishlist_model.NoteState.PLANNING_TO_PURCHASE.value["id"] or entry.status == wishlist_model.NoteState.MODIFIED.value["id"]:
                items_to_purchase.append((entry.item, get_person_name(entry.user_id)))

        if len(items_to_purchase) == 0:
            continue

        email_to_send = "Tere,\n"
        email_to_send += "Olete märkinud, et plaanite osta allpool loetletud kingitused kuid ei ole vastavate kingituste staatust uuendanud vähemalt viisteist päeva eelnevast meeldetuletusest:\n"
        email_to_send += "\n"
        email_to_send += "Kingitus | Kellele\n"
        for item in items_to_purchase:
            email_to_send += "\""
            email_to_send += item[0]
            email_to_send += "\" - "
            email_to_send += item[1]
            email_to_send += "\n"
        email_to_send += "\n"
        email_to_send += "Palume mitte unustada, ebameeldivad üllatused ei ole need, mida jõuludeks teistele teha soovime\n"
        email_to_send += "Jõulurakendus 🎄"

        mail.send_message(subject="Meeldetuletus kinkide kohta",
                          body=email_to_send,
                          recipients=[user.email])

    print(get_timestamp() + " Finished sending purchase reminders")


def get_timestamp_string(now):
    return str(now.hour) + "/" + str(now.day) + "/" + str(now.month) + "/" + str(now.year)


def remind_about_change(rate_limit=True):
    print(get_timestamp() + " Started sending change reminders")
    now = datetime.datetime.now()
    try:
        with open("remind_about_change", "r+") as timer_file:
            lastexec = timer_file.read()
            lastexec = datetime.datetime(*map(int, reversed(lastexec.split("/"))))

            if now - lastexec < datetime.timedelta(hours=6):
                print(get_timestamp() + " Changing reminders were rate-limited")
                if rate_limit:
                    return
            else:
                timer_file.seek(0)
                timer_file.write(get_timestamp_string(now))
    except Exception:
        print(get_timestamp() + " Change reminder timer file was not found")
        with open("remind_about_change", "w") as timer_file:
            timer_file.write(get_timestamp_string(now))

    for user in users_model.User.query:
        marked_entries = get_person_marked(user.id)
        items_to_purchase = []
        for entry in marked_entries:
            if entry.status == wishlist_model.NoteState.MODIFIED.value["id"]:
                items_to_purchase.append((entry.item, get_person_name(entry.user_id)))

        if len(items_to_purchase) == 0:
            continue

        email_to_send = "Tere,\n"
        email_to_send += "Viimase päeva jooksul on muudetud allpool loetletud soove, on oluline, et otsustaksite kas soovite ikka kinki osta või vabastate selle teistele:\n"
        email_to_send += "\n"
        email_to_send += "Kingitus | Kellele\n"
        for item in items_to_purchase:
            email_to_send += "\""
            email_to_send += item[0]
            email_to_send += "\" - "
            email_to_send += item[1]
            email_to_send += "\n"
        email_to_send += "\n"
        email_to_send += "Palume päeva jooksul enda otsus uuesti süsteemi sisestada\n"
        email_to_send += "Jõulurakendus 🎄"

        mail.send_message(subject="Meeldetuletus kinkide kohta",
                          body=email_to_send,
                          recipients=[user.email])

    print(get_timestamp() + " Finished sending change reminders")


scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(remind_to_add,
                  trigger=IntervalTrigger(days=30),
                  name="Addition reminder",
                  id="add_reminder",
                  replace_existing=True)
scheduler.add_job(remind_to_buy,
                  trigger=IntervalTrigger(days=15),
                  name="Buying reminder",
                  id="buy_reminder",
                  replace_existing=True)
scheduler.add_job(remind_about_change,
                  trigger=IntervalTrigger(minutes=720),
                  name="Change reminder",
                  id="cng_reminder",
                  replace_existing=True)


atexit.register(lambda: scheduler.shutdown())
scheduler.start()

# Just for assigning members_to_families a few colors
chistmasy_colors = ["#E5282A", "#DC3D2A", "#0DEF42", "#00B32C", "#0D5901"]


def get_person_marked(user_id):
    passed_person_id = int(user_id)
    wishlist_marked = wishlist_model.Wishlist.query.filter(wishlist_model.Wishlist.purchased_by == passed_person_id).all()
    return wishlist_marked


def get_person_id(name):
    return users_model.User.query.filter(users_model.User.username == name).first().id


def get_family_id(passed_person_id):
    passed_person_id = int(passed_person_id)
    db_families_user_has_conn = users_families_admins_model.UFARelationship.query.filter(
        users_families_admins_model.UFARelationship.user_id == passed_person_id).all()

    db_family = db_families_user_has_conn[0]
    family_id = db_family.family_id
    return family_id


def get_person_name(passed_person_id):
    return users_model.User.query.get(passed_person_id).username


def get_target_id(passed_person_id):
    try:
        return shuffles_model.Shuffle.query.get(passed_person_id).getter
    except Exception:
        return -1


def get_name_in_genitive(name):
    try:
        return names_model.Name.query.get(name).genitive
    except Exception:
        return name


def send_graph(filename):
    return send_from_directory("./generated_graphs", filename)


def decrypt_id(encrypted_user_id):
    base64_raw_data = base64.urlsafe_b64decode(encrypted_user_id).decode()
    data = json.loads(base64_raw_data)
    ciphertext = base64.b64decode(data[0])
    nonce = base64.b64decode(data[1])
    tag = base64.b64decode(data[2])

    cipher = AES.new(Config.AES_KEY, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt(ciphertext).decode()

    try:
        cipher.verify(tag)
        print(get_timestamp(), "The message is authentic:", plaintext)
    except ValueError:
        print(get_timestamp(), "Key incorrect or message corrupted!")

    return plaintext


def encrypt_id(user_id):
    cipher = AES.new(Config.AES_KEY, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(bytes(str(user_id), encoding="utf8"))
    nonce = base64.b64encode(cipher.nonce).decode()
    ciphertext = base64.b64encode(ciphertext).decode()
    tag = base64.b64encode(tag).decode()
    json_package = json.dumps([ciphertext, nonce, tag])
    packed = base64.urlsafe_b64encode(bytes(json_package, "utf8")).decode()

    return packed


def get_timestamp():
    # [yyyy-mm-dd hh:mm:ss +0000]
    time_now = datetime.datetime.now()
    year = str(time_now.year)
    month = "0" + str(time_now.month) if len(str(time_now.month)) == 1 else str(time_now.month)
    day = "0" + str(time_now.day) if len(str(time_now.day)) == 1 else str(time_now.day)
    hour = "0" + str(time_now.hour) if len(str(time_now.hour)) == 1 else str(time_now.hour)
    minute = "0" + str(time_now.minute) if len(str(time_now.minute)) == 1 else str(time_now.minute)
    second = "0" + str(time_now.second) if len(str(time_now.second)) == 1 else str(time_now.second)
    pid = os.getpid()
    timestamp = "[" + year + "-" + month + "-" + day + " " + \
                hour + ":" + minute + ":" + second + \
                " +0300]" + \
                " [" + str(pid) + "]"
    # FIXME: Get actual timezone

    return timestamp


app.add_url_rule("/generated_graphs/<filename>", endpoint="generated_graphs", view_func=send_graph)

# Show a friendlier error page
if not Config.DEBUG or Config.TESTING:
    @app.errorhandler(500)
    def error_500(err):
        try:
            if not current_user.is_authenticated:
                sentry_enabled = False
            else:
                sentry_enabled = True
        except Exception:
            sentry_enabled = False

        return render_template("error.html",
                               sentry_enabled=sentry_enabled,
                               sentry_ask_feedback=True,
                               sentry_event_id=g.sentry_event_id,
                               sentry_public_dsn=sentry.client.get_public_dsn("https"),
                               message="Päringu töötlemisel tekkis viga!",
                               title="Error")


    @app.errorhandler(404)
    def error_404(err):
        try:
            if not current_user.is_authenticated:
                sentry_enabled = False
            else:
                sentry_enabled = True
        except Exception:
            sentry_enabled = False

        return render_template("error.html",
                               sentry_enabled=sentry_enabled,
                               sentry_ask_feedback=True,
                               sentry_event_id=g.sentry_event_id,
                               sentry_public_dsn=sentry.client.get_public_dsn("https"),
                               message="Lehte ei leitud!",
                               title="Error")


# Views
@app.route("/test")
@login_required
def test():
    check = check_if_admin()
    if check is not None:
        return check
    remind_about_change(False)
    remind_to_buy(False)
    remind_to_add(False)
    return render_template("error.html", message="Here you go!", title="Error")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory("./static", "favicon-16x16.png")


def index():
    user_id = session["user_id"]
    username = get_person_name(user_id)
    no_shuffle = False
    if get_target_id(user_id) == -1:
        no_shuffle = True

    try:
        users_model.User.query.get(user_id).last_activity_at = datetime.datetime.now()
        users_model.User.query.get(user_id).last_activity_ip = "0.0.0.0"
    except Exception:
        sentry.captureException()

    return render_template("index.html",
                           auth=username,
                           no_shuffle=no_shuffle,
                           uid=user_id,
                           title="Kodu")


@app.route("/about")
def about():
    return render_template("home.html", no_sidebar=True)


@app.route("/")
def home():
    if current_user.is_authenticated:
        return index()
    else:
        return about()


@app.route("/contact")
def contact():
    return render_template("contact.html", no_sidebar=True)


@app.route("/robots.txt")
def robots():
    return send_from_directory(app.static_folder, "robots.txt")


@app.route("/sitemap.xml")
def sitemap():
    return send_from_directory(app.static_folder, "sitemap.xml")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route("/shuffle")
@login_required
def shuffle():
    user_id = session["user_id"]
    username = get_person_name(user_id)
    print(get_timestamp(), username)
    gifter = get_person_id(username)
    print(get_timestamp(), gifter)
    giftee = get_target_id(gifter)
    print(get_timestamp(), giftee)
    return render_template("shuffle.html",
                           title="Loosimine",
                           id=giftee)


@app.route("/notes")
@login_required
def notes():
    user_id = session["user_id"]
    # username = get_person_name(user_id)
    notes_from_file = {}
    empty = False

    try:
        db_notes = wishlist_model.Wishlist.query.filter(wishlist_model.Wishlist.user_id == user_id).all()
        for note in db_notes:
            notes_from_file[note.item] = encrypt_id(note.id)
    except Exception as e:
        if not Config.DEBUG:
            sentry.captureException()
        raise e

    if len(notes_from_file) <= 0:
        notes_from_file = {"Praegu on siin ainult veel tühjus, ei tahagi jõuludeks midagi?": ("", "")}
        empty = True

    return render_template("notes.html",
                           list=notes_from_file,
                           empty=empty,
                           title="Minu jõulusoovid")


@app.route("/createnote", methods=["GET"])
@login_required
def createnote():
    return render_template("createnote.html",
                           title="Lisa uus")


@app.route("/createnote", methods=["POST"])
@login_required
def createnote_add():
    print(get_timestamp(), "Got a post request to add a note")
    user_id = session["user_id"]
    username = get_person_name(user_id)
    print(get_timestamp(), "Found user:", username)
    print(get_timestamp(), "Found user id:", user_id)
    currentnotes = {}
    addednote = request.form["note"]

    if len(addednote) > 1000:
        return render_template("error.html",
                               message="Pls no hax " + username + "!!",
                               title="Error")
    elif len(addednote) <= 0:
        return render_template("error.html",
                               message="Jõuluvana tühjust tuua ei saa, " + username + "!",
                               title="Error")

    print(get_timestamp(), "Trying to add a note:", addednote)
    try:
        print(get_timestamp(), "Opening file", user_id)
        #    with open("./notes/" + useridno, "r") as file:
        #        currentnotes = json.load(file)
        db_notes = wishlist_model.Wishlist.query.filter(wishlist_model.Wishlist.user_id == user_id).all()
        for note in db_notes:
            currentnotes[note.item] = note.id
    except Exception as e:
        if not Config.DEBUG:
            sentry.captureException()
        raise e

    if len(currentnotes) >= 200:
        return render_template("error.html",
                               message="Soovinimekiri muutuks liiga pikaks, " + username + "",
                               title="Error")

    db_entry_notes = wishlist_model.Wishlist(
        user_id=user_id,
        item=addednote
    )

    try:
        db.session.add(db_entry_notes)
        db.session.commit()
    except Exception as e:
        if not Config.DEBUG:
            sentry.captureException()
        raise e

    return render_template("success.html",
                           action="Lisatud",
                           link="./notes",
                           title="Lisatud")


@app.route("/editnote", methods=["GET"])
@login_required
def editnote():
    user_id = session["user_id"]
    username = get_person_name(user_id)

    try:
        request_id = request.args["id"]
        request_id = decrypt_id(request_id)
        request_id = int(request_id)

        print(get_timestamp(), user_id, "is trying to remove a note", request_id)
    except Exception:
        if not Config.DEBUG:
            sentry.captureException()
        return render_template("error.html",
                               message="Pls no hax " + username + "!!",
                               title="Error")

    try:
        print(get_timestamp(), user_id, " is editing notes of ", request_id)
        db_note = wishlist_model.Wishlist.query.get(request_id)
    except Exception as e:
        if not Config.DEBUG:
            sentry.captureException()
        raise e

    return render_template("createnote.html",
                           action="Muuda",
                           title="Muuda",
                           placeholder=db_note.item)


@app.route("/editnote", methods=["POST"])
@login_required
def editnote_edit():
    print(get_timestamp(), "Got a post request to edit a note by", end="")
    user_id = session["user_id"]
    # username = get_person_name(user_id)
    print(get_timestamp(), " user id:", user_id)

    addednote = request.form["note"]
    try:
        request_id = request.args["id"]
        request_id = decrypt_id(request_id)
        request_id = int(request_id)
    except Exception:
        if not Config.DEBUG:
            sentry.captureException()
        return render_template("error.html",
                               message="Viga lingis",
                               title="Error")

    db_note = wishlist_model.Wishlist.query.get(request_id)

    try:
        db_note.item = addednote
        db_note.status = wishlist_model.NoteState.MODIFIED.value["id"]
        db.session.commit()
    except Exception as e:
        if not Config.DEBUG:
            sentry.captureException()
        raise e

    return render_template("success.html",
                           action="Muudetud",
                           link="./notes",
                           title="Muudetud")


@app.route("/removenote")
@login_required
def deletenote():
    user_id = session["user_id"]
    username = get_person_name(user_id)

    try:
        request_id = request.args["id"]
        request_id = decrypt_id(request_id)
        request_id = int(request_id)
        print(get_timestamp(), user_id, " is trying to remove a note", request_id)
    except Exception:
        if not Config.DEBUG:
            sentry.captureException()
        return render_template("error.html",
                               message="Viga lingis",
                               title="Error")

    try:
        wishlist_model.Wishlist.query.filter_by(id=request_id).delete()
        db.session.commit()
    except Exception:
        if not Config.DEBUG:
            sentry.captureException()
        return render_template("error.html", message="Ei leidnud seda, mida kustutada tahtsid", title="Error")

    #    with open("./notes/" + useridno, "w") as file:
    #        file.write(json.dumps(currentnotes))

    print(get_timestamp(), "Removed", username, "note with ID", request_id)
    return render_template("success.html",
                           action="Eemaldatud",
                           link="./notes",
                           title="Eemaldatud")


@app.route("/giftingto", methods=["POST"])
@login_required
def updatenotestatus():
    user_id = session["user_id"]
    try:
        back_count = int(request.args["back"]) - 2
    except Exception:
        back_count = -2

    try:
        status = int(request.form["status"])
        note = wishlist_model.Wishlist.query.get(decrypt_id(request.form["id"]))

        if status > -1:
            if int(note.status) == wishlist_model.NoteState.PURCHASED.value["id"] or status == \
                    wishlist_model.NoteState.MODIFIED.value["id"]:
                raise Exception("Invalid access")
            note.status = status
            note.purchased_by = user_id
            db.session.commit()
        #        elif status == "off":
        #            note.status = wishlist_model.NoteState.DEFAULT.value["id"]
        #            note.purchased_by = None
        elif status == -1:
            if int(note.status) == wishlist_model.NoteState.PURCHASED.value["id"] or status == \
                    wishlist_model.NoteState.MODIFIED.value["id"]:
                raise Exception("Invalid access")
            note.status = status
            note.purchased_by = None
            db.session.commit()
        else:
            raise Exception("Invalid status code")
    except Exception as e:
        if not Config.DEBUG:
            sentry.captureException()
        else:
            print(get_timestamp(), "Failed toggling:", e)
        return render_template("error.html", message="Ei saanud staatusemuudatusega hakkama", title="Error", back=True)

    #    with open("./notes/" + useridno, "w") as file:
    #        file.write(json.dumps(currentnotes))

    return redirect("/giftingto?id=" + str(request.args["id"]) + "&back=" + str(back_count), code=303)


@app.route("/giftingto")
@login_required
def giftingto():
    #check = check_if_admin()
    #if check is not None:
    #   return check

    user_id = session["user_id"]
    username = get_person_name(user_id)
    invalid_notes = False

    try:
        back_count = request.args["back"]
    except Exception:
        back_count = -1

    try:
        request_id = request.args["id"]
        request_id = int(decrypt_id(request_id))
    except Exception as e:
        print(get_timestamp(), "Failed decrypting or missing:", e)
        request_id = get_target_id(user_id)

    try:  # Yeah, only valid IDs please
        if request_id == -1:
            return render_template("error.html",
                                   message="Loosimist ei ole veel administraatori poolt tehtud",
                                   title="Error")
        elif request_id < 0:
            raise Exception()
        elif request_id == int(user_id):
            return render_template("error.html",
                                   message="Sellele nimekirjale on ligipääs keelatud",
                                   title="Keelatud")
    except Exception:
        if not Config.DEBUG:
            sentry.captureException()
        return render_template("error.html",
                               message="Pls no hax " + username + "!!",
                               title="Error")

    if check is not None:  # Let's not let everyone read everyone's lists
        if request_id != get_target_id(user_id):
            family_id = get_family_id(user_id)
            family_obj = family_model.Family.query.get(family_id)
            family_group = family_obj.group

            database_all_families_with_members = []
            database_families = family_model.Family.query.filter(family_model.Family.group == family_group).all()
            for db_family in database_families:
                database_family_members = users_families_admins_model.UFARelationship.query.filter(
                    users_families_admins_model.UFARelationship.family_id == db_family.id).all()
                database_all_families_with_members.append(database_family_members)

            found = False
            for family in database_all_families_with_members:
                for member in family:
                    if member.user_id == request_id:
                        found = True

            if not found:
                return check

    currentnotes = {}

    try:
        print(get_timestamp(), user_id, "is opening file:", request_id)
        db_notes = wishlist_model.Wishlist.query.filter(wishlist_model.Wishlist.user_id == request_id).all()
        if len(db_notes) <= 0:
            raise Exception

        for note in db_notes:
            all_states = [state.value for state in wishlist_model.NoteState]
            all_states.remove(wishlist_model.NoteState.MODIFIED.value)
            selections = []
            modifyable = False
            name = ""

            if note.status == wishlist_model.NoteState.DEFAULT.value["id"]:
                selections = all_states
                selections.insert(0, selections.pop(selections.index(wishlist_model.NoteState.DEFAULT.value)))
                modifyable = True
            elif note.status == wishlist_model.NoteState.MODIFIED.value["id"]:
                if note.purchased_by == int(user_id) or note.purchased_by is None:
                    selections = all_states
                    selections.insert(0, wishlist_model.NoteState.MODIFIED.value)
                    modifyable = True
                else:
                    selections = [wishlist_model.NoteState.MODIFIED.value]
                    modifyable = False
                name = note.purchased_by
            elif note.status == wishlist_model.NoteState.PURCHASED.value["id"]:
                selections = [wishlist_model.NoteState.PURCHASED.value]
                name = note.purchased_by
                modifyable = False
            elif note.status == wishlist_model.NoteState.PLANNING_TO_PURCHASE.value["id"]:
                selections = [wishlist_model.NoteState.PLANNING_TO_PURCHASE.value,
                              wishlist_model.NoteState.DEFAULT.value, wishlist_model.NoteState.PURCHASED.value]
                name = note.purchased_by
                if note.purchased_by == int(user_id):
                    modifyable = True
                else:
                    modifyable = False

            currentnotes[note.item] = (encrypt_id(note.id), copy.deepcopy(selections), modifyable, name)
    except ValueError:
        if not Config.DEBUG:
            sentry.captureException()
    except Exception as e:
        currentnotes = {"Praegu on siin ainult veel tühjus": (-1, -1, False, "")}
        invalid_notes = True
        print(get_timestamp(), "Error displaying notes, there might be none:", e)

    return render_template("show_notes.html",
                           notes=currentnotes,
                           target=get_name_in_genitive(get_person_name(request_id)),
                           id=encrypt_id(request_id),
                           title="Kingisoovid",
                           invalid=invalid_notes,
                           back=True,
                           back_count=back_count)


@app.route("/graph")
@login_required
def graph():
    user_id = session["user_id"]
    try:
        family_id = get_family_id(user_id)
        family_obj = family_model.Family.query.get(family_id)
        family_group = family_obj.group
        return render_template("graph.html",
                               id=str(session["user_id"]),
                               image="graph_" + str(family_group) + ".png",
                               title="Graaf")
    except Exception:
        return render_template("error.html", message="Loosimist ei ole administraatori poolt tehtud", title="Error")


@app.route("/settings")
@login_required
def settings():
    user_id = session["user_id"]
    user_obj = users_model.User.query.get(user_id)
    is_in_group = False
    is_in_family = False

    db_families_user_has_conn = users_families_admins_model.UFARelationship.query.filter(
        users_families_admins_model.UFARelationship.user_id == user_id).all()

    user_families = {}
    db_groups_user_has_conn = []
    for family_relationship in db_families_user_has_conn:
        family = family_model.Family.query.get(family_relationship.family_id)
        user_families[family.name] = (encrypt_id(family.id), family_relationship.admin)
        is_in_family = True
        db_groups_user_has_conn += (groups_model.Groups.query.filter(family_model.Family.group == family.group).all())

    user_groups = {}
    for group_relationship in db_groups_user_has_conn:
        uga_relationship = users_groups_admins_model.UGARelationship.query.filter(
            users_groups_admins_model.UGARelationship.user_id == user_id
            and
            users_groups_admins_model.UGARelationship.group_id == group_relationship.id).first()

        if not uga_relationship:
            user_groups[group_relationship.description] = (encrypt_id(group_relationship.id), False)
        else:
            user_groups[group_relationship.description] = (encrypt_id(group_relationship.id), uga_relationship.admin)
        is_in_group = True

    return render_template("settings.html",
                           user_id=user_id,
                           user_name=user_obj.username,
                           family_admin=is_in_family,
                           group_admin=is_in_group,
                           families=user_families,
                           groups=user_groups,
                           title="Seaded",
                           back_link="/")


@app.route("/editfam")
@login_required
def editfamily():
    user_id = session["user_id"]

    try:
        request_id = request.args["id"]
        request_id = int(decrypt_id(request_id))
    except Exception:
        if not Config.DEBUG:
            sentry.captureException()
        return render_template("error.html", message="Tekkis viga, kontrolli linki", title="Error")

    if request_id < 0:
        if not Config.DEBUG:
            sentry.captureException()
        return render_template("error.html", message="Tekkis viga, kontrolli linki", title="Error")

    db_family_members = users_families_admins_model.UFARelationship.query.filter(
        users_families_admins_model.UFARelationship.family_id == request_id).all()

    family = []
    show_admin_column = False
    for member in db_family_members:
        is_admin = False
        is_person = False
        if member.user_id == user_id:
            is_person = True

        family.append((get_person_name(member.user_id), encrypt_id(member.user_id), is_admin, is_person))

    return render_template("editfam.html",
                           family=family,
                           title="Muuda perekonda",
                           admin=show_admin_column,
                           back=False,
                           back_link="/settings")


@app.route("/editfam", methods=["POST"])
@login_required
def editfamily_with_action():
    # user_id = session["user_id"]

    # try:
    # action = request.args["action"]
    # request_id = request.args["id"]
    # request_id = int(decrypt_id(request_id))
    # except Exception:
    # return render_template("error.html", message="Tekkis viga, kontrolli linki", title="Error")

    return None


@app.route("/editgroup")
@login_required
def editgroup():
    user_id = session["user_id"]
    # user_obj = users_model.User.query.get(user_id)

    try:
        request_id = request.args["id"]
        request_id = int(decrypt_id(request_id))
    except Exception:
        if not Config.DEBUG:
            sentry.captureException()
        request_id = 0

    db_groups_user_is_admin = users_groups_admins_model.UGARelationship.query.filter(
        users_groups_admins_model.UGARelationship.user_id == user_id).all()

    db_groups_user_has_conn = family_model.Family.query.filter(family_model.Family.group == request_id).all()

    db_group = db_groups_user_has_conn[request_id]

    db_families_in_group = family_model.Family.query.filter(family_model.Family.group == db_group.group).all()

    families = []
    for family in db_families_in_group:
        admin = False

        if family in db_groups_user_is_admin:
            admin = True

        families.append((family.name, encrypt_id(family.id), admin))

    is_admin = False
    if len(db_groups_user_is_admin) > 0:
        is_admin = True

    return render_template("editgroup.html", title="Muuda gruppi", families=families, admin=is_admin)


@app.route("/editgroup", methods=["POST"])
@login_required
def editgroup_with_action():
    # user_id = session["user_id"]
    # user_obj = users_model.User.query.get(user_id)
    return None


@app.route("/secretgraph")
@login_required
def secretgraph():
    check = check_if_admin()
    if check is not None:
        return check

    request_id = str(request.args["id"])

    return render_template("graph.html",
                           id=str(get_person_name(session["user_id"])),
                           image="s" + request_id + ".png",
                           title="Salajane graaf")


def check_if_admin():
    user_id = session["user_id"]
    requester = get_person_name(user_id)
    requester = requester.lower()

    if requester != "admin" and requester != "taavi":
        return render_template("error.html", message="Pls no hax " + requester + "!!", title="Error")
    else:
        return None


"""@app.route("/family")
@login_required
def family():
    user_id = session["user_id"]
    family_id = users_model.User.query.get(user_id).family_id
    family_members = users_model.User.query.filter(users_model.User.family_id == family_id).all()
    family_member_names = []
    for member in family_members:
        family_member_names.append(member.username)
    return render_template("show_family.html", names=family_member_names, title="Perekond")
"""


def save_graph(passed_graph, file_name, colored=False, id_to_id_mapping=None):
    # This function just saves a networkx graph into a .png file without any GUI(!)
    if id_to_id_mapping is None:
        id_to_id_mapping = {}

    plotlib.figure(num=None, figsize=(10, 10), dpi=60)
    plotlib.axis("off")  # Turn off the axis display
    fig = plotlib.figure(1)
    pos = netx.circular_layout(passed_graph)

    if colored:  # Try to properly color the nodes
        for node in passed_graph:
            node_color = random.choice(chistmasy_colors)
            netx.draw_networkx_nodes([node], pos, node_size=1500, node_color=node_color)
    else:
        netx.draw_networkx_nodes(passed_graph, pos, node_size=1500, node_color=chistmasy_colors[0])

    netx.draw_networkx_edges(passed_graph, pos)

    if colored:
        name_id_lookup_dict = {}  # Let's create a admin-user_id mapping

        for name in id_to_id_mapping.keys():
            name_id_lookup_dict[get_person_id(name)] = name

        netx.draw_networkx_labels(passed_graph, pos, labels=name_id_lookup_dict, font_size=18)
    else:
        netx.draw_networkx_labels(passed_graph, pos, font_size=18)
    cut = 0
    xmax = 1.1 + cut * max(xx for xx, yy in pos.values())
    ymax = 1.1 + cut * max(yy for xx, yy in pos.values())
    xmin = -1.1 + cut * min(xx for xx, yy in pos.values())
    ymin = -1.1 + cut * min(yy for xx, yy in pos.values())
    plotlib.xlim(xmin, xmax)
    plotlib.ylim(ymin, ymax)

    fig.savefig(file_name, bbox_inches="tight")
    plotlib.close()
    print(get_timestamp(), "Saved generated graph to file:", file_name)
    del fig


@app.route("/recreategraph")
@login_required
def regraph():
    check = check_if_admin()
    if check is not None:
        return check

    user_id = session["user_id"]
    family_id = get_family_id(user_id)
    family_obj = family_model.Family.query.get(family_id)
    family_group = family_obj.group

    database_families = family_model.Family.query.filter(family_model.Family.group == family_group).all()
    database_all_families_with_members = []
    for db_family in database_families:
        database_family_members = users_families_admins_model.UFARelationship.query.filter(
            users_families_admins_model.UFARelationship.family_id == db_family.id).all()
        database_all_families_with_members.append(database_family_members)

    families = []
    family_ids_map = {}
    for family_index, list_family in enumerate(database_all_families_with_members):
        families.insert(family_index, {})
        for person_index, person in enumerate(list_family):
            family_ids_map[family_index] = get_family_id(person.user_id)
            families[family_index][get_person_name(person.user_id)] = person.user_id

    families_shuf_nam = {}
    families_shuf_ids = {}
    #    print(get_timestamp(), "Starting finding matches")
    """""
    # This comment block contains self-written algorithm that isn't as robust 
    # as the library's solution thus this is not used for now
    
    families_give_copy = copy.deepcopy(families)  # Does the person need to give a gift
    for family_index, family_members in enumerate(families_give_copy):
        for person in family_members:
            families_give_copy[family_index][person] = True

    families_take_copy = copy.deepcopy(families)  # Does the person need to take a gift
    for family_index, family_members in enumerate(families_take_copy):
        for person in family_members:
            families_take_copy[family_index][person] = True
    
    for index, family in enumerate(families_list_copy):  # For each family among every family
        for person in family:  # For each person in given family
            if families_give_copy[index][person] == True:  # If person needs to gift
                #                print("Looking for a match for:", person, get_person_id(person))
                familynumbers = list(range(0, index))
                familynumbers.extend(range(index + 1, len(family) - 1))
                
                random.shuffle(familynumbers)
                for number in familynumbers:
                    receiving_family_index = number
                    receiving_family = families_take_copy[number]  # For each receiving family
                    #                    print("Looking at other members_to_families:", receiving_family)

                    for receiving_person in receiving_family:  # For each person in other family
                        if families_take_copy[receiving_family_index][receiving_person] == True and \
                                families_give_copy[index][person] == True:  # If person needs to receive
                            families_take_copy[receiving_family_index][receiving_person] = False  
                            #print("Receiving:", receiving_family_index, receiving_person)
                            families_give_copy[index][person] = False  # ; print("Giving:", index, person)
                            families_shuf_nam[person] = receiving_person
                            families_shuf_ids[get_person_id(person)] = get_person_id(receiving_person)
                            #                             print("Breaking")
                            break
    """""

    members_to_families = {}
    for family_id, family_members in enumerate(families):
        for person, person_id in family_members.items():
            members_to_families[person_id] = family_id

    families_to_members = {}
    for family_id, family_members in enumerate(families):
        families_to_members[family_id] = set()
        for person, person_id in family_members.items():
            currentset = families_to_members[family_id]
            currentset.update([person_id])

    last_connections = secretsanta.ConnectionGraph.ConnectionGraph(members_to_families, families_to_members)
    # connections.add(source, target, year)
    current_year = datetime.datetime.now().year
    print(get_timestamp(), current_year, "is the year of Linux Desktop")

    santa = secretsanta.secretsanta.SecretSanta(families_to_members, members_to_families, last_connections)
    new_connections = santa.generate_connections(current_year)

    shuffled_ids_str = {}
    for connection in new_connections:
        families_shuf_ids[connection.source] = connection.target
        families_shuf_nam[get_person_name(connection.source)] = get_person_name(connection.target)
        shuffled_ids_str[str(connection.source)] = str(connection.target)

        #    print(get_timestamp(),  shuffled_names)
        #    print(get_timestamp(),  shuffled_ids)

    for giver, getter in families_shuf_ids.items():
        db_entry_shuffle = shuffles_model.Shuffle(
            giver=giver,
            getter=getter,
        )
        try:
            db.session.add(db_entry_shuffle)
            db.session.commit()
        except Exception:
            db.session.rollback()
            row = shuffles_model.Shuffle.query.get(giver)
            row.getter = getter
            db.session.commit()

    digraph = netx.DiGraph(iterations=10000, scale=2)
    digraph.add_nodes_from(copy.deepcopy(families_shuf_ids).keys())

    for source, destination in copy.deepcopy(families_shuf_ids).items():
        digraph.add_edges_from([(source, destination)])

    save_graph(digraph, "./generated_graphs/graph_" + str(family_group) + ".png")
    del digraph
    #    rerendernamegraph()  # create the graph with names

    return render_template("success.html", action="Genereeritud", link="./notes", title="Genereeritud")


@app.route("/testmail")
@login_required
def test_mail():
    with mail.connect() as conn:
        print(get_timestamp(), conn.configure_host().vrfy)
        msg = Message(recipients=["root@localhost"],
                      body="test",
                      subject="test2")

        conn.send(msg)
    return render_template("success.html", action="Sent", link="./testmail", title="Saadetud")


@app.route("/rerendergraph")
@login_required
def rerender():
    check = check_if_admin()
    if check is not None:
        return check

    user_id = session["user_id"]
    family_id = get_family_id(user_id)
    family_obj = family_model.Family.query.get(family_id)
    family_group = family_obj.group

    digraph = netx.DiGraph(iterations=100000000, scale=2)

    database_all_families_with_members = []
    database_families = family_model.Family.query.filter(family_model.Family.group == family_group).all()
    for db_family in database_families:
        database_family_members = users_families_admins_model.UFARelationship.query.filter(
            users_families_admins_model.UFARelationship.family_id == db_family.id).all()
        database_all_families_with_members.append(database_family_members)

    families_shuf_ids = {}
    for family in database_all_families_with_members:
        for member in family:
            families_shuf_ids[member.user_id] = get_target_id(member.user_id)

    digraph.add_nodes_from(families_shuf_ids.keys())

    for source, destination in copy.deepcopy(families_shuf_ids).items():
        digraph.add_edges_from([(source, destination)])

    save_graph(digraph, "./generated_graphs/graph_" + str(family_group) + ".png")

    return render_template("success.html", action="Genereeritud", link="./notes", title="Genereeritud")


@app.route("/rerendernamegraph")
@login_required
def rerendernamegraph():
    check = check_if_admin()
    if check is not None:
        return check

    digraph = netx.DiGraph(iterations=100000000, scale=2)  # This is probably a horrible idea with more nodes

    user_id = session["user_id"]
    family_id = get_family_id(user_id)
    family_obj = family_model.Family.query.get(family_id)
    family_group = family_obj.group

    database_all_families_with_members = []
    database_families = family_model.Family.query.filter(family_model.Family.group == family_group).all()
    for db_family in database_families:
        database_family_members = users_families_admins_model.UFARelationship.query.filter(
            users_families_admins_model.UFARelationship.family_id == db_family.id).all()
        database_all_families_with_members.append(database_family_members)

    families_shuf_ids = {}
    for family in database_all_families_with_members:
        for member in family:
            families_shuf_ids[member.user_id] = get_target_id(member.user_id)

    for shuffled_ids_id in copy.deepcopy(families_shuf_ids).keys():
        digraph.add_node(shuffled_ids_id)

    for source, destination in copy.deepcopy(families_shuf_ids).items():
        digraph.add_edges_from([(source, destination)])

    save_graph(digraph, "./static/secretgraph.png", colored=True, id_to_id_mapping=families_shuf_ids)

    return render_template("success.html", action="Genereeritud", link="./graph")


"""
@app.route("/login", methods=["GET"])
def login():
    render_template("security/login_user.html", title="Logi sisse")


@app.route("/register", methods=["GET"])
def register():
    render_template("security/register_user.html", title="Registreeru")


@app.route("/change", methods=["GET"])
@login_required
def change():
    render_template("security/change_password.html", title="Muuda parooli")


@app.route("/reset", methods=["GET"])
def reset():
    render_template("security/reset_password.html", title="Lähtesta parool")


@app.route("/confirm", methods=["GET"])
def confirmation():
    render_template("security/send_confirmation.html", title="Kinnita e-mail")
"""

if __name__ == "__main__":
    if Config.DEBUG:
        print(get_timestamp(), "Starting in debug!")
        app.run(debug=Config.DEBUG, use_evalex=False, host="0.0.0.0", port=5000)
    else:
        print(get_timestamp(), "Starting in production.")
        app.run(debug=Config.DEBUG, use_evalex=False, host="127.0.0.1")
