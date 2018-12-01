# coding=utf-8
import logging


class Config(object):
    ENV = "debug"  # TODO: Replace with "production"
    FLASK_DEBUG = True  # TODO: Disable in production
    DEVELOPMENT = True  # TODO: Disable in production
    DEBUG = True  # TODO: Disable in production
    TESTING = True  # TODO: Disable in production

    CSRF_ENABLED = False  # TODO: Enable in production
    WTF_CSRF_ENABLED = False  # TODO: Enable in production

    SENTRY_URL = ""  # TODO: Add sentry URL
    SENTRY_USER_ATTRS = ["username",
                         "id",
                         "email"]

    AES_KEY = b"yFrstBQ&iKi1OwugdJ?EnIfPWundVBPO"
    SECRET_KEY = ""  # TODO: Update secret key info
    SQLALCHEMY_DATABASE_URI = ""  # TODO: Add database URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = "localhost"
    MAIL_PORT = 25
    MAIL_USE_SSL = False
    MAIL_USERNAME = ""
    MAIL_PASSWORD = ""  # TODO: Add email server info
    MAIL_DEFAULT_SENDER = ("Pretty mailer name", "place@holder")  # TODO: Update email sender info
    MAIL_SUPPRESS_SEND = True  # TODO: Do not suppress send in production

    RECAPTCHA_PUBLIC_KEY = ""  # TODO: Add captcha keys
    RECAPTCHA_PRIVATE_KEY = ""

    SECURITY_EMAIL_SENDER = ("Pretty mailer name", "place@holder")  # TODO: Update email sender info
    SECURITY_PASSWORD_HASH = "pbkdf2_sha512"
    SECURITY_PASSWORD_SALT = None  # TODO: Add salt!

    SECURITY_REGISTERABLE = True
    SECURITY_RECOVERABLE = True
    SECURITY_CONFIRMABLE = True
    SECURITY_CHANGEABLE = True
    SECURITY_TRACKABLE = True

    USER_AFTER_REGISTER_ENDPOINT = "/login"

    SESSION_COOKIE_SECURE = False  # TODO: Enable in production
    REMEMBER_COOKIE_SECURE = False  # TODO: Enable in production
    SESSION_COOKIE_HTTPONLY = False  # TODO: Enable in production
    REMEMBER_COOKIE_HTTPONLY = False  # TODO: Enable in production

    LOGLEVEL = logging.DEBUG

    BABEL_DEFAULT_LOCALE = "ee"  # TODO: You might want to change this to "en" if you want to default to English
