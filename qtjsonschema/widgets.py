"""
Widget definitions for JSON schema elements.
"""

from PyQt5 import QtCore, QtWidgets, QtGui

from abc import abstractmethod, ABC


def iter_widgets(layout):
    for i in range(layout.count()):
        yield layout.itemAt(i).widget()


class UnsupportedSchemaError(BaseException):
    pass


class UnsupportedSchema(QtWidgets.QLabel):
    """Widget representation of an unsupported schema element.

    Presents a label noting the name of the element and its type.
    If the element is a reference, the reference name is listed instead of a type.
    """

    def __init__(self, name, schema, parent):
        self.name = name
        self.schema = schema
        self.parent = parent

        self._type = schema.get("type", schema.get("$ref", "(?)"))
        QtWidgets.QLabel.__init__(self, "(Unsupported schema entry: %s, %s)" % (name, self._type), parent)
        self.setStyleSheet("QLabel { font-style: italic; }")

    def to_json_object(self):
        return "(unsupported)"


# $ref, items, allOf, anyOf, additionalItems, dependencies,
# oneOf, type, extends, properties, patternProperties,
# additionalProperties

class JSONBaseWidget:
    def __init__(self, name, schema, ctx, parent):
        super().__init__()

        self.name = name
        self.schema = schema
        self.parent = parent
        self.ctx = ctx

        if "definitions" in schema:
            self.definitions = schema["definitions"]
        elif parent:
            self.definitions = parent.definitions
        else:
            self.definitions = {}

    @abstractmethod
    def from_json_object(self, data):
        pass

    @abstractmethod
    def to_json_object(self):
        pass


class JSONObjectWidget(JSONBaseWidget, QtWidgets.QGroupBox):
    """
        Widget representation of an object.

        Objects have properties, each of which is a widget of its own.
        We display these in a groupbox, which on most platforms will
        include a border.
    """

    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, ctx, parent)

        self.setTitle(self.name)
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setAlignment(QtCore.Qt.AlignTop)
        self.setLayout(self.layout)
        self.setFlat(False)

        if "description" in schema:
            self.setToolTip(schema['description'])

        self.properties = {}

        if "properties" not in schema:
            label = QtWidgets.QLabel("Invalid object description (missing properties)", self)
            label.setStyleSheet("QLabel { color: red; }")
            self.layout.addWidget(label)

        else:
            for k, v in schema['properties'].items():
                widget = _create_widget(k, v, ctx, self)
                self.layout.addWidget(widget)
                self.properties[k] = widget

                # TODO pattern properties control widget

    def from_json_object(self, data):
        for k, v in data.items():
            self.properties[k].from_json_object(v)

    def to_json_object(self):
        return {k: v.to_json_object() for k, v in self.properties.items()}


class JSONPrimitiveBaseWidget(JSONBaseWidget, QtWidgets.QWidget):
    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, ctx, parent)
        layout = QtWidgets.QHBoxLayout()

        self.label = QtWidgets.QLabel(schema.get('title', name))
        if "description" in schema:
            self.label.setToolTip(schema['description'])

        self.editor = self.edit_widget()

        layout.addWidget(self.label)
        layout.addWidget(self.editor)

        self.setLayout(layout)

    @property
    @abstractmethod
    def edit_widget(self):
        pass


class JSONStringWidget(JSONPrimitiveBaseWidget):
    """
        Widget representation of a string.

        Strings are text boxes with labels for names.
    """
    edit_widget = QtWidgets.QLineEdit

    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, ctx, parent)

        pattern = schema.get("pattern")
        if pattern:
            expression = QtCore.QRegularExpression(pattern)
            validator = QtGui.QRegularExpressionValidator(expression)
            self.editor.setValidator(validator)

        max_length = schema.get("maxLength")
        if max_length is not None:
            self.editor.setMaxLength(max_length)

            # TODO

    def from_json_object(self, data):
        self.editor.setText(data)

    def to_json_object(self):
        return str(self.editor.text())


class JSONIntegerWidget(JSONPrimitiveBaseWidget):
    """
        Widget representation of an integer (SpinBox)
    """
    edit_widget = QtWidgets.QSpinBox

    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, ctx, parent)

        self._set_limits(schema)

    def _set_limits(self, schema):
        if "minimum" in schema:
            minimum = schema['minimum']
            if schema.get("exclusiveMinimum", False):
                minimum += 1

            self.editor.setMinimum(minimum)

        if "maximum" in schema:
            maximum = schema['maximum']
            if schema.get("exclusiveMaximum", False):
                maximum -= 1

            self.editor.setMaximum(maximum)

    def from_json_object(self, data):
        self.editor.setValue(data)

    def to_json_object(self):
        return self.editor.value()


class JSONNumberWidget(JSONPrimitiveBaseWidget):
    """
        Widget representation of a number (DoubleSpinBox)
    """
    edit_widget = QtWidgets.QDoubleSpinBox

    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, ctx, parent)

        self._set_limits(schema)

    def _set_limits(self, schema):
        if "minimum" in schema:
            minimum = schema['minimum']
            if schema.get("exclusiveMinimum", False):
                minimum += 0.01  # TODO

            self.editor.setMinimum(minimum)

        if "maximum" in schema:
            maximum = schema['maximum']
            if schema.get("exclusiveMaximum", False):
                maximum -= 0.01

            self.editor.setMaximum(maximum)

    def from_json_object(self, data):
        self.editor.setValue(data)

    def to_json_object(self):
        return self.editor.value()


class JSONBooleanWidget(JSONPrimitiveBaseWidget):
    """
        Widget representing a boolean (CheckBox)
    """
    edit_widget = QtWidgets.QCheckBox

    def to_json_object(self):
        return bool(self.editor.isChecked())


class JSONArrayWidget(JSONBaseWidget, QtWidgets.QWidget):
    """
        Widget representation of an array.

        Arrays can contain multiple objects of a type, or
        they can contain objects of specific types.

        We include a label and button for adding types.
    """

    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, ctx, parent)

        self.layout = QtWidgets.QVBoxLayout()
        self.controls_layout = QtWidgets.QHBoxLayout()
        self.items_layout = QtWidgets.QVBoxLayout()

        label = QtWidgets.QLabel(name, self)
        label.setStyleSheet("QLabel { font-weight: bold; }")
        if "description" in schema:
            label.setToolTip(schema['description'])

        button = QtWidgets.QPushButton("Append", self)
        button.clicked.connect(self.click_add)

        self.controls_layout.addWidget(label)
        self.controls_layout.addWidget(button)

        self.layout.addLayout(self.controls_layout)
        self.layout.addLayout(self.items_layout)
        self.setLayout(self.layout)

        try:
            self.items_schema = schema['items']
        except KeyError:
            raise UnsupportedSchemaError("Arrays require items")

        self.additional_item_schema = schema.get("additionalItems")

    def _get_item_schema(self, index):
        if isinstance(self.items_schema, list):
            try:
                schema = self.items_schema[index]
            except IndexError:
                schema = self.additional_item_schema
                assert schema is not None
        else:
            assert isinstance(self.items_schema, dict)
            schema = self.items_schema

        return schema

    def click_add(self):
        self.add_item()

    def add_item(self, data=None):
        index = self.items_layout.count()
        schema = self._get_item_schema(index)
        obj = _create_widget("Item #{:d}".format(index), schema, self.ctx, self)

        self.layout.addWidget(obj)

        if data is not None:
            obj.from_json_object(data)

    def from_json_object(self, data):
        for i, datum in enumerate(data):
            if i < self.items_layout.count():
                self.items_layout.itemAt(i).widget().from_json_object(datum)
            else:
                self.add_item(datum)

    def to_json_object(self):
        return [w.to_json_object() for w in iter_widgets(self.items_layout) if hasattr(w, "to_json_object")]


schema_type_to_widget_class = {
    "object": JSONObjectWidget,
    "string": JSONStringWidget,
    "integer": JSONIntegerWidget,
    "array": JSONArrayWidget,
    "number": JSONNumberWidget,
    "boolean": JSONBooleanWidget
}

from abc import ABC, abstractmethod
from functools import lru_cache
from uritools import uricompose, urijoin, urisplit
import requests
from json import load as load_json


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


def create_widget(name, schema, schema_uri=None):
    registry = CachedURILoaderRegistry()

    http_loader = HTTPResourceLoader()
    file_resource_loader = FileResourceLoader()
    document_loader = DocumentLoader(schema, schema_uri)

    registry.register_for_scheme('http', http_loader)
    registry.register_for_scheme('https', http_loader)
    registry.register_for_scheme('file', file_resource_loader)
    registry.register_for_scheme(None, document_loader)
    # TODO we give the filepath to help resolve remove refs
    # If schema_uri is not given (e.g we operate on anon dict schema), then no scheme is present
    ctx = Context(schema_uri or "#", registry)

    return _create_widget(name, schema, ctx, None)


def _create_widget(name, schema, ctx, parent):
    if "id" in schema:
        ctx = ctx.follow_uri(schema['id'])

    if "$ref" in schema:
        schema = ctx.dereference(schema['$ref'])

    if "type" in schema:
        schema_type = schema['type']
        try:
            object_class = schema_type_to_widget_class[schema_type]
        except KeyError:
            pass
        else:
            try:
                return object_class(name, schema, ctx, parent)

            except UnsupportedSchemaError:
                return UnsupportedSchema(name, schema, parent)

    return UnsupportedSchema(name, schema, parent)


if __name__ == "__main__":
    ref = f"identifier.json#/definitions/identifier"
    registry = URILoaderRegistry()

    http_retriever = HTTPResourceLoader()
    registry.register_for_scheme('http', http_retriever)
    registry.register_for_scheme('https', http_retriever)
    registry.register_for_scheme('file', FileResourceLoader())

    from pathlib import Path
    uri = (Path(__file__).parent / 'schema.json').as_uri()
    ctx = Context(uri, registry)
    # ctx.follow_uri(schema_url)
    result = ctx.dereference(ref)


    # TODO "ID" is used as a base URL, we don't do that explictly atm, so where a reference doesn't
    # give a scheme it will fail to join properly
