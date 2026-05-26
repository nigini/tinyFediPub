"""Entry point for python -m activity_processor"""
from post_utils import load_config
from activity_processor import process_inbox_queue, process_outbox_queue

config = load_config()
process_inbox_queue(config)
process_outbox_queue(config)
