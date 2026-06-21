#!/usr/bin/env python3
"""Entry point — delega al package webui/."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from webui import main
main()
