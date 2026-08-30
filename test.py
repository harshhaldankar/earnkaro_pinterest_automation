import json
try:
    json.loads('{\n,\n}')
except Exception as e:
    print(repr(e))
