import logging
import logging.config
import logging.handlers
import os
import sys

from pathlib import Path

import zlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Создаем папку "logs" в корневой директории проекта, если ее еще нет
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)
LOGS_DIR = os.path.abspath(LOGS_DIR)


class MyRotatingFileHandler(logging.handlers.RotatingFileHandler):
	file_size = 5 * 1024 * 1024

	def __init__(self, filename, mode='a', maxBytes=file_size, backupCount=0, encoding="utf-8", delay=False):
		super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
		self.namer = self.file_namer
		self.rotator = self.file_rotator

	def file_namer(self, name: str):
		return name + ".gz"

	def file_rotator(self, source: str, dest: str):
		with open(source, "rb") as sf:
			data = sf.read()
			compressed = zlib.compress(data, 9)
			with open(dest, "wb") as df:
				df.write(compressed)
		os.remove(source)


# Set up exception hook to log exceptions
def log_exception(exc_type, exc_value, exc_traceback):
	logging.debug("--- Uncaught exception ---\n", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = log_exception

LOGGING_CONFIG = {
	"version": 1,
	"disable_existing_loggers": False,
	"formatters": {
		"default": {
			"format": "%(asctime)s %(levelname)s: %(filename)s -> %(funcName)s(), line: %(lineno)d - %(message)s [%(name)s]",
			"datefmt": "%d/%m/%Y %H:%M:%S"
		},
		"simple": {
			"format": "%(asctime)s %(levelname)s: %(message)s",
			"datefmt": "%d/%m/%Y %H:%M:%S"
		},
		"json": {
			"()": "pythonjsonlogger.jsonlogger.JsonFormatter",
			"format": "asctime: %(asctime)s created: %(created)f filename: %(filename)s funcName: %(funcName)s levelname: %(levelname)s levelno: %(levelno)s lineno: %(lineno)d message: %(message)s module: %(module)s name: %(name)s pathname: %(pathname)s process: %(process)d processName: %(processName)s relativeCreated: %(relativeCreated)d thread: %(thread)d threadName: %(threadName)s exc_info: %(exc_info)s",
			"datefmt": "%d/%m/%Y %H:%M:%S"
		}
	},
	"handlers": {
		"brief_info": {
			"level": "DEBUG",
			"class": "logging.StreamHandler",
			"formatter": "simple",
			"stream": sys.stdout
		},
		"detail_info": {
			"level": "ERROR",
			"formatter": "default",
			"class": "logging.StreamHandler",
			"stream": sys.stdout
		},
		"log_warn": {
			"level": "WARNING",
			"formatter": "default",
			"()": MyRotatingFileHandler,
			"filename": f"{LOGS_DIR}/warn.log",
			"backupCount": 8
		},
		"log_error": {
			"level": "ERROR",
			"formatter": "default",
			"()": MyRotatingFileHandler,
			"filename": f"{LOGS_DIR}/error.log",
			"backupCount": 8
		},
		"json_error": {
			"level": "CRITICAL",
			"formatter": "json",
			"class": "logging.StreamHandler",
			"stream": sys.stdout
		}
	},
	"loggers": {
		__name__: {
			"level": "INFO",
			"handlers": [
				"detail_info",
				"json_error",
			],
			"propagate": True
		},
		"httpx": {
			"level": "WARNING",
			"handlers": ["detail_info"]
		},
		"httpcore": {
			"level": "ERROR",
			"handlers": ["detail_info"]
		}
	},
	"root": {
		"level": "INFO",
		"handlers": ["brief_info", "log_warn", "log_error"]
	}
}

logging.config.dictConfig(LOGGING_CONFIG)
log = logging.getLogger(__name__)
