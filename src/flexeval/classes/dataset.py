import logging
from datetime import datetime

import peewee as pw

from flexeval.classes.base import BaseModel
from flexeval.classes.jsonview import JsonView

logger = logging.getLogger(__name__)


class Dataset(BaseModel):
    """Holds a dataset, e.g. a jsonl file"""

    id = pw.IntegerField(primary_key=True)
    timestamp = pw.DateTimeField(default=datetime.now)
    datasource_type = pw.TextField(null=False)
    name = pw.TextField(default=None, null=True)
    notes = pw.TextField(default=None, null=True)
    is_loaded = pw.BooleanField(default=False)
    metadata = pw.TextField(default="{}", null=False)
    metadata_dict = JsonView("metadata")
