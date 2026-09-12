#!/bin/zsh
cd "${0:A:h}"
exec .venv/bin/python -m embroidery_app.app
