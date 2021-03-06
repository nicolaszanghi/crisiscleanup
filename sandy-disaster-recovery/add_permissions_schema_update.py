import hashlib
import logging
from google.appengine.ext import deferred
from google.appengine.ext import db
import organization
import event_db
#from models import phase
#from models import incident_definition


BATCH_SIZE = 100  # ideal batch size may vary based on entity size.


def AddPermissionsSchemaUpdate(cursor=None, num_updated=0):        
    query = organization.Organization.all()
    if cursor:
        query.with_cursor(cursor)

    to_put = []

    for p in query.fetch(limit=BATCH_SIZE):
        p.permission="Full Access"
        to_put.append(p)
    if to_put:
        db.put(to_put)
        num_updated += len(to_put)
        logging.debug(
            'Put %d entities to Datastore for a total of %d',
            len(to_put), num_updated)
        deferred.defer(
            AddPermissionsSchemaUpdate, cursor=query.cursor(), num_updated=num_updated)
    else:
        logging.debug(
            'AddPermissionsSchemaUpdate complete with %d updates!', num_updated)

    