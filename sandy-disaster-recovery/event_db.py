#!/usr/bin/env python
#
# Copyright 2012 Jeremy Pack
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
import datetime
import logging
import re

from google.appengine.ext import db
from google.appengine.api import memcache

import wtforms
from wtforms import TextField
from wtforms.ext.appengine.db import model_form

# Local libraries.
import cache


class Event(db.Model):
  name = db.StringProperty(required = True)
  short_name = db.StringProperty()
  created_date = db.DateProperty(auto_now_add=True)
  start_date = db.DateProperty(auto_now_add=True)
  end_date = db.DateProperty()
  num_sites = db.IntegerProperty(default = 0)
  case_label = db.StringProperty()
  counties = db.StringListProperty()
  latitudes = db.ListProperty(float)
  longitudes = db.ListProperty(float)
  reminder_days = db.IntegerProperty(default=15)
  reminder_contents = db.TextProperty()
  timestamp_last_login = db.DateTimeProperty()

  @property
  def organizations(self):
      """
      Active, verified organizations related to this incident.

      Handles current and legacy incident/s properties.
      """
      from organization import Organization  # avoid circular import

      # lookup using new incidents field
      orgs = list(
          Organization.all().filter('incidents', self.key())
              .filter('org_verified', True)
              .filter('is_active', True)
      )

      # build list of id and look for global admin
      org_ids = set()
      seen_global_admin = False
      for org in orgs:
          if org.is_global_admin:
              seen_global_admin = True
          org_id = org.key().id()
          if org_id not in org_ids:
              org_ids.add(org_id)

      # check legacy incident field
      legacy_field_orgs = Organization.all().filter('incident', self.key()) \
          .filter('org_verified', True) \
          .filter('is_active', True)
      for org in legacy_field_orgs:
          if org.key().id() not in org_ids:
              orgs.append(org)

      # prepend global admin if not encountered
      if not seen_global_admin:
          orgs = (
              list(Organization.all().filter('name', 'Admin')) +
              orgs
          )
      return orgs

  @property
  def logged_in_to_recently(self):
      " An org logged in within the last 24 hours. "
      now = datetime.datetime.utcnow()
      return (
          self.timestamp_last_login and 
          (now - self.timestamp_last_login).total_seconds() < 24 * 60 * 60
      )


  @property
  def filename_friendly_name(self):
      return re.sub(r'\W+', '-', self.name.lower())


def DefaultEventName():
  return "Hurricane Sandy Recovery"


@db.transactional(xg=True, retries=100)
def AddSiteToEvent(site, event_id, force=False, can_overwrite=False):
  event = Event.get_by_id(event_id)
  if not site or not event or ((not force and not can_overwrite) and site.event):
    logging.critical("Could not initialize site: " + str(site.key().id()))
    return False
  site.event = event
  site.case_number = event.case_label + str(event.num_sites)
  event.num_sites += 1
  cache.PutAndCache(event, ten_minutes)
  site.compute_similarity_matching_fields()
  site.put()
  return True


ten_minutes = 600
@db.transactional(xg=True, retries=100)
def SetCountiesForEvent(event_id, counties):
  event = Event.get_by_id(event_id)
  event.counties = [county for county in counties]
  event.latitudes = []
  event.longitudes = []
  cache.PutAndCache(event, ten_minutes)
  return True


def GetDefaultEvent():
  cache_key = 'Event:default'
  event = memcache.get(cache_key)
  if event:
    return event
  event_q = Event.gql("WHERE name = :name", name = DefaultEventName())
  for e in event_q:
    memcache.set(cache_key, e, ten_minutes)
    return e
  return None


def GetEventFromParam(event_id_param):
  try:
    event_id = int(event_id_param)
    event = GetCached(event_id)
  except:
    event = GetDefaultEvent()
  return event


def GetCached(event_id):
  return cache.GetCachedById(Event, ten_minutes, event_id)


def GetAllCached():
  return cache.GetAllCachedBy(Event, ten_minutes)


def GetAndCache(event_id):
  return cache.GetAndCache(Event, ten_minutes, event_id)


def ReduceNumberOfSitesFromEvent(event_id):
  event = Event.get_by_id(event_id)
  event.num_sites -= 1
  cache.PutAndCache(event, ten_minutes)


class NewEventForm(model_form(Event)):
    name = TextField('Name', [wtforms.validators.Length(min = 1, max = 100,
    message = "Name must be between 1 and 100 characters")])
    short_name = TextField('Short Name', [wtforms.validators.Length(min = 1, max = 100,
    message = "Name must be between 1 and 100 characters")])
