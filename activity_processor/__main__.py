"""Entry point for python -m activity_processor"""
from post_utils import load_config
from activity_processor import process_queue

process_queue(load_config())
