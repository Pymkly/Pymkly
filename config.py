import json

from etat import isProd

with open('config.prod.json' if isProd else 'config.local.json' ) as f:
    config = json.load(f)
