import json
import pathlib


class ContextDB:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.data = {}
        if path.exists():
            with open(path, 'r') as f:
                self.data = json.loads(f.read())

        self.keys_used = set()

    def get_key(self, key, hash):
        if not key or not hash:
            return None

        key_data = self.data.get(key)
        if not key_data:
            return None


        hash_old = key_data.get('hash')
        if hash_old != hash:
            self.data.pop(key)
            return None

        self.keys_used.add(key)
        return key_data['data']

    def set_key(self, key, hash, data):
        self.keys_used.add(key)

        self.data[key] = {
            'hash': hash,
            'data': data
        }

    def dump(self):
        # dump any unused keys:
        for key in list(self.data.keys()):
            if key not in self.keys_used:
                print(f'Purging {key} data')
                self.data.pop(key)

        with open(self.path, 'w') as f:
            f.write(json.dumps(self.data, indent=2))
