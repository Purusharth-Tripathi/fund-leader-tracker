"""Utility functions for Fund Leader Tracker."""
import logging
import os
import sys
from datetime import datetime

import urllib3
import yaml
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        print('Warning: .env file not found. Copy .env.example to .env before running live analysis.')


def setup_logging(log_file='logs/fund_tracker.log', log_level='INFO'):
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
        force=True,
    )
    return logging.getLogger(__name__)


def ensure_directories():
    base_dir = os.path.dirname(__file__)
    for directory in ['data', 'logs', 'output']:
        os.makedirs(os.path.join(base_dir, directory), exist_ok=True)


def get_timestamp():
    return datetime.now().isoformat()


def print_header(text, char='='):
    print(f"\n{char * 60}")
    print(f"{text.center(60)}")
    print(f"{char * 60}\n")


def print_progress(current, total, prefix='Progress'):
    bar_length = 40
    total = max(total, 1)
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    percent = f"{100 * (current / float(total)):.1f}"
    print(f'\r{prefix}: |{bar}| {percent}% Complete', end='\r')
    if current == total:
        print()


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_colored(text, color=Colors.OKGREEN):
    print(f"{color}{text}{Colors.ENDC}")
