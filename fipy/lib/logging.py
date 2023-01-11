# MicroPython reimplementation of Python's logging library
#
# Copied from the micropython-lib repository
# https://github.com/micropython/micropython-lib/blob/master/logging/logging.py
# 
# Modified by Sergiusz Michalik
# 
# Original library is MIT licensed, as noted in setup.py
# https://github.com/micropython/micropython-lib/blob/master/logging/setup.py

import sys

CRITICAL    = 50
TRACEBACK   = 45
ERROR       = 40
WARNING     = 30
INFO        = 20
DEBUG       = 10
NOTSET      = 0

_level_dict = {
    CRITICAL: "CRIT",
    TRACEBACK: "TRACEBACK",
    ERROR: "ERROR",
    WARNING: "WARN",
    INFO: "INFO",
    DEBUG: "DEBUG",
}

_stream = sys.stderr

class Logger:

    level = NOTSET

    def __init__(self, name):
        self.name = name
    
    def _level_str(self, level):
        l = _level_dict.get(level)
        if l is not None:
            return l
        return "LVL%s" % level

    def setLevel(self, level):
        self.level = level

    def isEnabledFor(self, level):
        return level >= self.level

    def log(self, level, msg, *args):
        if level >= self.level:
            _stream.write("%s:%s:" % (self._level_str(level), self.name))
            if not args:
                print(msg, file=_stream)
            else:
                print(msg % args, file=_stream)


    def debug(self, msg, *args):
        self.log(DEBUG, msg, *args)

    def info(self, msg, *args):
        self.log(INFO, msg, *args)

    def warning(self, msg, *args):
        self.log(WARNING, msg, *args)

    def error(self, msg, *args):
        self.log(ERROR, msg, *args)

    def traceback(self, e):
        import uio as io
        from sys import print_exception
        buff = io.BytesIO()
        print_exception(e, buff)

        traceback = buff.getvalue().decode().split('\n')
        for line in traceback:
            self.log(TRACEBACK, line)

    def critical(self, msg, *args):
        self.log(CRITICAL, msg, *args)

    def exc(self, e, msg, *args):
        self.log(ERROR, msg, *args)
        sys.print_exception(e, _stream)

    def exception(self, msg, *args):
        self.exc(sys.exc_info()[1], msg, *args)


_loggers = {}

def getLogger(name, level=INFO):
    if name in _loggers:
        _loggers[name].setLevel(level)
        return _loggers[name]

    l = Logger(name)
    _loggers[name] = l
    l.setLevel(level)
    return l

