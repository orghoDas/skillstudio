import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            'time': datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        if hasattr(record, 'status_code'):
            entry['status_code'] = record.status_code
        if record.exc_info:
            entry['exception'] = self.formatException(record.exc_info)
        return json.dumps(entry)
