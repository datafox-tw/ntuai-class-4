#!/usr/bin/env python3
"""
Compatibility entrypoint.

Use this file so older class commands (`python iceland_travel_lab.py`) still
launch the latest Iceland lab web app built in `iceland_lab_web/`.
"""

from iceland_lab_web.app import run


if __name__ == "__main__":
    run()
