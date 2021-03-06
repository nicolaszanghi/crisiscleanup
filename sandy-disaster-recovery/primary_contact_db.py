#!/usr/bin/env python
#
# Copyright 2012 Andy Gimma
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
# System libraries.
import logging
from google.appengine.ext.db import to_dict
from google.appengine.ext import db
from wtforms.ext.appengine.db import model_form
from google.appengine.api import memcache

from wtforms import BooleanField, TextField, HiddenField, validators

# Local libraries.
import cache


ten_minutes = 600


def _GetOrganizationName(contact, field):
  """Returns the name of the organization in the given field, if possible.
  """
  if hasattr(contact, field):
    try:
      org = getattr(contact, field)
    except db.ReferencePropertyResolveError:
      return None
    if org:
      return org.name
    return None

def _GetField(contact, field):
  """Simple field accessor, with a bit of logging."""
  try:
    return getattr(contact, field)
  except AttributeError:
    logging.warn('contact %s is missing attribute' % (contact.key().id(), field))
    return None


class Contact(db.Model):
    first_name = db.StringProperty(required=True)
    last_name = db.StringProperty(required=True)
    title = db.StringProperty()
    phone = db.StringProperty(required=True)
    email = db.StringProperty(required=True)
    organization = db.ReferenceProperty()
    is_primary = db.BooleanProperty()
    
    CSV_FIELDS = [
        'first_name',
        'last_name',
        'title',
        'phone',
        'email',
        'organization',
        'is_primary',
    ]
    
    _CSV_ACCESSORS = {
        'organization': _GetOrganizationName,
    }

    @property
    def full_name(self):
        return "%s %s" % (self.first_name, self.last_name)
    
    def ToCsvLine(self):
      """Returns the site as a list of string values, one per field in
      CSV_FIELDS."""
      csv_row = []
      for field in self.CSV_FIELDS:
        accessor = self._CSV_ACCESSORS.get(field, _GetField)
        value = accessor(self, field)
        if value is None:
          csv_row.append('')
        else:
          try:
            csv_row.append(unicode(value).encode("utf-8"))
          except:
            logging.critical("Failed to parse: " + value + " " + str(self.key().id()))
      return csv_row

    @classmethod
    def for_event(cls, event):
        " Return generator of contacts for organizations of event. "
        return (
            contact for contact in Contact.all()
            if contact.organization
            and contact.organization.may_access(event)
        )

    
cache_prefix = Contact.__name__ + "-d:"
    
def PutAndCache(contact, cache_time):
    contact.put()
    return memcache.set(cache_prefix + str(contact.key().id()),
    (contact, ContactToDict(contact)),
    time = cache_time)
        
  
def GetAllCached():
    return cache.GetAllCachedBy(Contact, ten_minutes)

def GetAndCache(contact_id):
    contact = Contact.get_by_id(contact_id)
    if contact:
        memcache.set(cache_prefix + str(contact.key().id()),
        (contact, ContactToDict(contact)),
        time = cache_time)
        return contact

def ContactToDict(contact):
  contact_dict = to_dict(contact)
  contact_dict["id"] = contact.key().id()
  return contact_dict
  
def RemoveOrgFromContacts(org):
    contacts = db.GqlQuery("SELECT * From Contact WHERE organization = :1", org.key())
    to_put = []
    for c in contacts:
        c.organization = None
        to_put.append(c)
    if to_put:
        db.put(to_put)
        
    
    # search all contacts with -org- as incident
    # set incident to None
    # putandcache
    

class ContactForm(model_form(Contact, exclude=['organization'])):

    id = HiddenField()
    first_name = TextField('First Name', [
        validators.Length(
            min=1, max=100,
            message = "Name must be between 1 and 100 characters")
    ])
    last_name = TextField('Last Name',[
        validators.Length(
            min=1, max=100,
            message = "Name must be between 1 and 100 characters")
    ])
    title = TextField('Org Title',[
        validators.Length(
            min=1, max=100,
            message = "Org Title must be between 1 and 100 characters")
    ])
    phone = TextField('Phone', [
        validators.Length(
            min=1, max=15,
            message = "Phone must be between 1 and 15 characters")
    ])
    email = TextField('Email', [
        validators.Length(
            min=1, max=100,
            message = "Email must be between 1 and 100 characters"),
        validators.Email(message="That's not a valid email address.")
    ])


class ContactFormFull(ContactForm):

    is_primary = BooleanField()


class ContactFormFullWithDelete(ContactFormFull):

    delete_me = BooleanField("Delete (on save)")
