from jsonschema import RefResolver


class Resolver:
    def __init__(self, resolver, uri=''):
        self._resolver = resolver
        self._uri = uri

    def follow(self, ref):
        new_uri = self._resolver._urljoin_cache(self._uri, ref)
        return Resolver(self._resolver, new_uri)

    def rebase(self, uri):
        return Resolver(self._resolver, uri)

    def resolve(self):
        url, obj = self._resolver.resolve(self._uri)
        return obj


if __name__ == "__main__":
    with open("D:/pycharmprojects/pyqtschema/qtjsonschema/schema.json") as f:
        from json import load

        schema = load(f)

    rr = RefResolver.from_schema(schema)
    resolver = Resolver(rr)
    print(resolver.follow("#/defns/child/defns/age").resolve())
