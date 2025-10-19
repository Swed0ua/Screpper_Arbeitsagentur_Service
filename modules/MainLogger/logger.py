import logging.config
import yaml
from logging.handlers import TimedRotatingFileHandler

def setup_logger_from_yaml(name: str | None = None, config_path: str = "./config/logging_config.yaml", log_path: str = 'application.log'):
    """
    Завантажує конфігурацію для логера з YAML файлу.
    Повертає логер, готовий до використання.
    """
    # Завантаження конфігурації з YAML файлу
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f.read())
    
    # Налаштування кастомного шляху до лог-файлу
    config['handlers']['fileHandler']['filename'] = log_path
    
    # Налаштування логера з конфігурації
    logging.config.dictConfig(config)

    # Повертаємо кореневий логер або за іменем модуля
    logger = logging.getLogger(name)
    return logger

logger = setup_logger_from_yaml(log_path='./logs/central.log')

def get_loger():
    return logger
