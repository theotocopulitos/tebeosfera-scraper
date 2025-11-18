#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Compatibility utilities for TebeoSfera scraper (Python 3)

Provides simple implementations of utility functions needed by the
tebeosfera modules, without IronPython/.NET dependencies.

@author: Comic Scraper Enhancement Project
'''


def sstr(obj):
    '''
    Safely converts the given object into a string (sstr = safestr).

    Args:
        obj: Any object to convert to string

    Returns:
        String representation of the object
    '''
    if obj is None:
        return '<None>'
    if isinstance(obj, str):
        return obj
    if isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except:
            return obj.decode('latin-1', errors='replace')
    return str(obj)


def is_string(obj):
    '''
    Returns a boolean indicating whether the given object is a string.

    Args:
        obj: Object to check

    Returns:
        True if obj is a string, False otherwise
    '''
    if obj is None:
        return False
    return isinstance(obj, str)


# Simple log module replacement
class SimpleLog:
    '''Simple logging for standalone operation'''

    @staticmethod
    def write(message):
        '''Write a log message to stdout'''
        print(f"[LOG] {message}")

    @staticmethod
    def debug(message):
        '''Write a debug message to stdout'''
        print(f"[DEBUG] {message}")

    @staticmethod
    def error(message):
        '''Write an error message to stderr'''
        import sys
        print(f"[ERROR] {message}", file=sys.stderr)


# Create a singleton log instance
log = SimpleLog()
