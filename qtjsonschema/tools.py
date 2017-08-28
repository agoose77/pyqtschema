from abc import ABC, abstractmethod
from functools import lru_cache
from json import load as load_json

import requests
from uritools import uricompose, urisplit, urijoin


class ResourceLoader(ABC):
    @abstractmethod
    def load_resource(self, location):
        pass


class HTTPResourceLoader(ResourceLoader):
    def load_resource(self, location):
        return requests.get(location).json()


class FileResourceLoader(ResourceLoader):
    def load_resource(self, location):
        result = urisplit(location)
        if result.authority:
            raise ValueError("Network paths unsupported")

        path = result.path[1:]
        with open(path) as f:
            return load_json(f)


class DocumentLoader(ResourceLoader):
    def __init__(self, document, location):
        self.location = location
        self.document = document

    def load_resource(self, location):
        if location != self.location:
            raise ValueError("Cannot retrieve external documents")
        return self.document


class URILoaderRegistry:
    def __init__(self):
        self.scheme_to_loader = {}

    def load_resource_from_loader(self, loader, location):
        print(f"Loading resource {location} with {loader}")
        return loader.load_resource(location)

    def load_uri(self, uri):
        result = urisplit(uri)
        location = uricompose(result.scheme, result.authority, result.path)
        loader = self.scheme_to_loader[result.scheme]
        resource = self.load_resource_from_loader(loader, location)

        if result.fragment:
            assert result.fragment.startswith("/")
            reference = Reference(result.fragment[1:])
            return reference.extract(resource)

        return resource

    def register_for_scheme(self, scheme, resource):
        self.scheme_to_loader[scheme] = resource


class CachedURILoaderRegistry(URILoaderRegistry):
    load_resource_from_loader = lru_cache(1024)(URILoaderRegistry.load_resource_from_loader)


class Reference:
    def __init__(self, uri):
        self.elements = [e.replace('~1', '/').replace('~0', '~') for e in uri.split('/')]

    def extract(self, obj):
        for elem in self.elements:
            obj = obj[elem]
        return obj


class Context:
    def __init__(self, scope_uri, registry):
        self.scope_uri = scope_uri
        self.registry = registry

    def follow_uri(self, uri):
        new_uri = urijoin(self.scope_uri, uri)
        return self.__class__(new_uri, self.registry)

    def dereference(self, uri):
        reference_path = urijoin(self.scope_uri, uri)
        return self.registry.load_uri(reference_path)

    def __repr__(self):
        return f"Context({self.scope_uri!r}, {self.registry!r})"
