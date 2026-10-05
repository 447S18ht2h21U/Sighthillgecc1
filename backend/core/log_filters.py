import logging
import re

class CallbackLogFilter(logging.Filter):
    """Strip callback query strings from Django's development request/error logs."""
    def filter(self, record):
        def clean(value):
            return re.sub(r'(/api/docusign/callback/)\?[^\s"\']*', r'\1?[redacted]', value) if isinstance(value, str) else value
        record.msg = clean(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(clean(arg) for arg in record.args)
        elif isinstance(record.args, dict):
            record.args = {key: clean(value) for key, value in record.args.items()}
        return True


