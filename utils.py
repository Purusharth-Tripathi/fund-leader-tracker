"""
Utility functions for Fund Leader Tracker
"""
import os
import sys
import yaml
import logging
from datetime import datetime
from dotenv import load_dotenv
import urllib3

# Suppress SSL warnings for corporate environments
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def load_config():
    """Load configuration from config.yaml"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: config.yaml not found at {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing config.yaml: {e}")
        sys.exit(1)


def load_env():
    """Load environment variables from .env file"""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        print("Warning: .env file not found. Using .env.example as template.")
        print("Please copy .env.example to .env and configure your API key.")


def setup_logging(log_file='logs/fund_tracker.log', log_level='INFO'):
    """Setup logging configuration"""
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


def ensure_directories():
    """Ensure all required directories exist"""
    directories = ['data', 'logs', 'output']
    base_dir = os.path.dirname(__file__)

    for directory in directories:
        dir_path = os.path.join(base_dir, directory)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"Created directory: {dir_path}")


def format_currency(value):
    """Format number as currency"""
    try:
        return f"${value:,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def format_percent(value):
    """Format number as percentage"""
    try:
        return f"{value:.2f}%"
    except (TypeError, ValueError):
        return "N/A"


def get_timestamp():
    """Get current timestamp in ISO format"""
    return datetime.now().isoformat()


def print_header(text, char='='):
    """Print formatted header"""
    print(f"\n{char * 60}")
    print(f"{text.center(60)}")
    print(f"{char * 60}\n")


def print_progress(current, total, prefix='Progress'):
    """Print progress bar"""
    bar_length = 40
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    percent = f"{100 * (current / float(total)):.1f}"
    print(f'\r{prefix}: |{bar}| {percent}% Complete', end='\r')
    if current == total:
        print()


class Colors:
    """Terminal color codes"""
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
    """Print colored text"""
    print(f"{color}{text}{Colors.ENDC}")
