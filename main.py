# coding=utf-8
# Copyright: Taavi Eomäe 2017-2020
# SPDX-License-Identifier: AGPL-3.0-only
"""
A simple Secret Santa website in Python
Copyright © 2017-2020 Taavi Eomäe

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
import os

from celery import Celery
from flask import Flask
from flask_babelex import Babel
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.schema import CreateColumn

from config import Config
from forms import ExtendedConfirmationForm, ExtendedForgotPasswordForm, ExtendedRegisterForm, ExtendedResetForm


@compiles(CreateColumn, "postgresql")
def use_identity(element, compiler, **kw):
    """
    Overrides serial columns into identity columns when using PostgreSQL
    """
    text = compiler.visit_create_column(element, **kw)
    text = text.replace("SERIAL", "INT GENERATED BY DEFAULT AS IDENTITY")
    return text


basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config.from_object(Config)
csrf = CSRFProtect(app)
mail = Mail(app)
db = SQLAlchemy(app)
babel = Babel(app)
celery = Celery(app.import_name,
                backend=Config.CELERY_RESULT_BACKEND,
                broker=Config.CELERY_BROKER_URL)
celery.conf.update(app.config)

import sentry_sdk

sentry_sdk.init(Config.SENTRY_PUBLIC_DSN,
                integrations=[SqlalchemyIntegration(),
                              CeleryIntegration(),
                              FlaskIntegration(),
                              RedisIntegration()],
                send_default_pii=True,
                debug=Config.DEBUG,
                release=Config.CURRENT_GIT_SHA)

from models.users_model import User, Role
from flask_security import SQLAlchemyUserDatastore, Security

user_datastore = SQLAlchemyUserDatastore(db, User, Role)

security = Security(app,
                    user_datastore,
                    confirm_register_form=ExtendedRegisterForm,
                    reset_password_form=ExtendedResetForm,
                    send_confirmation_form=ExtendedConfirmationForm,
                    forgot_password_form=ExtendedForgotPasswordForm)

# Initialize enums from DB for nicer code
# noinspection PyUnresolvedReferences
from models.enums import event_type_to_id, subscription_type_to_id, audit_event_type_to_id, wishlist_status_to_id

from views import static_page, login_page, main_page, user_specific, edit_page, test_page, graph_page

app.register_blueprint(static_page)
app.register_blueprint(login_page)
app.register_blueprint(main_page)
app.register_blueprint(user_specific)
app.register_blueprint(edit_page)
app.register_blueprint(test_page)
app.register_blueprint(graph_page)
