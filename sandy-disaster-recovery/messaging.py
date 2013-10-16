#!/usr/bin/env python
#
# Copyright 2013 Chris Wood
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os

from google.appengine.api import app_identity, mail

import jinja2


ADMINISTRATORS = [
    ('Aaron Titus', 'aaron@crisiscleanup.org')
]


# jinja

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(
            os.path.dirname(__file__),
            'email_templates'
        )
    )
)


# functions

def get_application_id():
    return app_identity.get_application_id()


def get_default_version_hostname():
    return app_identity.get_default_version_hostname()


def get_app_system_email_address():
    return "%s <noreply@%s.appspotmail.com>" % (
        app_identity.get_service_account_name(),
        app_identity.get_application_id()
    )


def email_administrators(subject, body):
    """
    Email all ADMINISTRATORS with an email of @body and rewritten
    @subject of "[myappid] <@subject>"
    """
    subject = "[%s] %s" % (app_identity.get_application_id(), subject)
    sender_address = get_app_system_email_address()
    for name, email_address in ADMINISTRATORS:
        recipient_address = "%s <%s>" % (name, email_address)
        mail.send_mail(
            sender_address,
            recipient_address,
            subject,
            body
        )


def email_administrators_using_templates(
    event, subject_template_name, body_template_name, **kwargs):
    subject_template = jinja_environment.get_template(subject_template_name)
    body_template = jinja_environment.get_template(body_template_name)

    kwargs.update({'event': event})

    rendered_subject = subject_template.render(kwargs)
    rendered_body = body_template.render(kwargs)

    prefixed_subject = "[%s] %s" % (app_identity.get_application_id(), rendered_subject)
    sender_address = get_app_system_email_address()

    for name, email_address in ADMINISTRATORS:
        recipient_address = "%s <%s>" % (name, email_address)
        mail.send_mail(
            sender_address,
            recipient_address,
            prefixed_subject,
            rendered_body
        )
