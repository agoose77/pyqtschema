"""
Widget definitions for JSON schema elements.
"""

import re
from functools import partial
from ipaddress import IPv4Address, IPv6Address, AddressValueError

from PyQt5 import QtCore, QtWidgets, QtGui
from rfc3986 import urlparse

from .tools import FileResourceLoader, HTTPResourceLoader, Context, DocumentLoader, create_cached_uri_loader_registry


def is_valid_ip_address(cls, address) -> bool:
    try:
        cls(address)
    except AddressValueError:
        return False
    return True


def validate_uri(uri: str) -> bool:
    result = urlparse(uri)
    return result.is_valid()


def is_valid_hostname(hostname: str) -> bool:
    # Curteousy of https://stackoverflow.com/a/2532344
    if len(hostname) > 255:
        return False
    if hostname[-1] == ".":
        hostname = hostname[:-1]  # strip exactly one dot from the right, if present
    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))


# Widgets supporting $ref
# $ref, items, allOf, anyOf, additionalItems, dependencies,
# oneOf, type, extends, properties, patternProperties,
# additionalProperties

FORMAT_PATTERNS = {'date-time': ...,
                   'email': ...,
                   'hostname': ...,
                   'ipv4': partial(is_valid_ip_address, IPv4Address),
                   'ipv6': partial(is_valid_ip_address, IPv6Address),
                   'uri': validate_uri}


def iter_layout_widgets(layout):
    for i in range(layout.count()):
        yield layout.itemAt(i).widget()


def iter_widgets(object):
    for i in range(object.count()):
        yield object.widget(i)


def not_implemented_property():
    """Property descriptor which raises NotImplementedError on __get__"""

    def getter(self):
        raise NotImplementedError

    return property(getter)


class UnsupportedSchemaError(BaseException):
    pass


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

    def initialise(self):
        if 'default' in self.schema:
            self.load_json_object(self.schema['default'])

    def load_json_object(self, data):
        raise NotImplementedError

    def dump_json_object(self):
        raise NotImplementedError


class UnsupportedSchemaWidget(JSONBaseWidget, QtWidgets.QLabel):
    """Widget representation of an unsupported schema element.

    Presents a label noting the name of the element and its type.
    If the element is a reference, the reference name is listed instead of a type.
    """

    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, ctx, parent)

        QtWidgets.QLabel.__init__(self, "(Unsupported schema entry: {}, {})"
                                  .format(name, schema.get("type", "(?)")), parent)
        self.setStyleSheet("QLabel { font-style: italic; }")

    def load_json_object(self, value):
        pass

    def dump_json_object(self):
        return "(unsupported)"


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

    def load_json_object(self, data):
        for k, v in data.items():
            self.properties[k].load_json_object(v)

    def dump_json_object(self):
        return {k: v.dump_json_object() for k, v in self.properties.items()}


class JSONPrimitiveBaseWidget(JSONBaseWidget, QtWidgets.QWidget):
    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, ctx, parent)
        layout = QtWidgets.QHBoxLayout()

        self.label = QtWidgets.QLabel(schema.get('title', name))
        if "description" in schema:
            self.label.setToolTip(schema['description'])

        self.primitive_widget = self.primitive_class()

        layout.addWidget(self.label)
        layout.addWidget(self.primitive_widget)

        self.setLayout(layout)

    primitive_class = not_implemented_property()


class JSONEnumWidget(JSONPrimitiveBaseWidget):
    """
        Widget representation of an enumerated property.
    """
    primitive_class = QtWidgets.QComboBox

    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, ctx, parent)

        self.enum_values = schema['enum']
        items = [str(e) for e in schema['enum']]
        self.primitive_widget.addItems(items)

    def dump_json_object(self):
        index = self.primitive_widget.currentIndex()
        return self.enum_values[index]

    def load_json_object(self, obj):
        index = self.enum_values.index(obj)
        self.primitive_widget.setCurrentIndex(index)


class JSONStringWidget(JSONPrimitiveBaseWidget):
    """
        Widget representation of a string.

        Strings are text boxes with labels for names.
    """
    primitive_class = QtWidgets.QLineEdit

    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, ctx, parent)

        pattern = schema.get("pattern")
        if pattern:
            expression = QtCore.QRegularExpression(pattern)
            validator = QtGui.QRegularExpressionValidator(expression)
            self.primitive_widget.setValidator(validator)

        max_length = schema.get("maxLength")
        if max_length is not None:
            self.primitive_widget.setMaxLength(max_length)

            # TODO

    def load_json_object(self, data):
        self.primitive_widget.setText(data)

    def dump_json_object(self):
        return str(self.primitive_widget.text())


class SpinBoxWidgetBase(JSONPrimitiveBaseWidget):
    """
        Base class for spinbox widgets
    """
    primitive_class = not_implemented_property()
    step = not_implemented_property()

    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, ctx, parent)

        self._set_limits(schema)

    def _set_limits(self, schema):
        if "minimum" in schema:
            minimum = schema['minimum']
            if schema.get("exclusiveMinimum", False):
                minimum += self.step

            self.primitive_widget.setMinimum(minimum)

        if "maximum" in schema:
            maximum = schema['maximum']
            if schema.get("exclusiveMaximum", False):
                maximum -= self.step

            self.primitive_widget.setMaximum(maximum)

    def load_json_object(self, data):
        self.primitive_widget.setValue(data)

    def dump_json_object(self):
        return self.primitive_widget.value()


class JSONIntegerWidget(SpinBoxWidgetBase):
    """
        Widget representation of an integer (SpinBox)
    """
    primitive_class = QtWidgets.QSpinBox
    step = 1


class JSONNumberWidget(SpinBoxWidgetBase):
    """
        Widget representation of a number (DoubleSpinBox)
    """
    primitive_class = QtWidgets.QDoubleSpinBox
    step = 0.01


class JSONBooleanWidget(JSONPrimitiveBaseWidget):
    """
        Widget representing a boolean (CheckBox)
    """
    primitive_class = QtWidgets.QCheckBox

    def dump_json_object(self):
        return bool(self.primitive_widget.isChecked())


class JSONArrayWidget(JSONBaseWidget, QtWidgets.QWidget):
    """
        Widget representation of an array.

        Arrays can contain multiple objects of a type, or
        they can contain objects of specific types.

        We include a label and button for adding types.
    """

    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, parent, ctx)

        self.layout = QtWidgets.QVBoxLayout()
        self.controls_layout = QtWidgets.QHBoxLayout()
        self.items_layout = QtWidgets.QVBoxLayout()

        label = QtWidgets.QLabel(name, self)
        label.setStyleSheet("QLabel { font-weight: bold; }")
        if "description" in schema:
            label.setToolTip(schema['description'])

        append_button = QtWidgets.QPushButton("", self)
        icon = append_button.style().standardIcon(QtWidgets.QStyle.SP_FileIcon)
        append_button.setIcon(icon)
        append_button.clicked.connect(self.click_add)
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum,
                                            QtWidgets.QSizePolicy.Maximum)
        append_button.setSizePolicy(size_policy)

        remove_button = QtWidgets.QPushButton("", self)
        icon = remove_button.style().standardIcon(QtWidgets.QStyle.SP_TrashIcon)
        remove_button.setIcon(icon)
        remove_button.clicked.connect(self.click_remove)
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum,
                                            QtWidgets.QSizePolicy.Maximum)
        remove_button.setSizePolicy(size_policy)

        self.controls_layout.addWidget(label)
        self.controls_layout.addWidget(append_button)
        self.controls_layout.addWidget(remove_button)

        self.layout.addLayout(self.controls_layout)

        self.items_list = QtWidgets.QListWidget(self)
        self.widget_stack = QtWidgets.QStackedWidget(self)

        self.items_list.currentItemChanged.connect(self._current_item_changed)

        self.layout.addWidget(self.items_list)
        self.layout.addWidget(self.widget_stack)

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

    def _current_item_changed(self, current, previous):
        index = self.items_list.indexFromItem(current).row()
        self.widget_stack.setCurrentIndex(index)

    def click_add(self):
        self.add_item()

    def click_remove(self):
        self.remove_item()

    def add_item(self, data=None):
        index = self.items_list.count()
        schema = self._get_item_schema(index)
        obj = _create_widget("Item #{:d}".format(index), schema, self.ctx, self)

        self.items_list.addItem(f"{index}")
        self.widget_stack.addWidget(obj)

        if data is not None:
            obj.load_json_object(data)

    def remove_item(self):
        last_item_index = self.items_list.count() - 1
        if last_item_index < 0:
            return

        self.items_list.takeItem(last_item_index)

        widget = self.widget_stack.widget(last_item_index)
        self.widget_stack.removeWidget(widget)

    def load_json_object(self, data):
        for i, datum in enumerate(data):
            if i < self.widget_stack.count():
                self.widget_stack.widget(i).load_json_object(datum)
            else:
                self.add_item(datum)

    def dump_json_object(self):
        return [w.dump_json_object() for w in iter_widgets(self.widget_stack)]


schema_type_to_widget_class = {
    "object": JSONObjectWidget,
    "string": JSONStringWidget,
    "integer": JSONIntegerWidget,
    "array": JSONArrayWidget,
    "number": JSONNumberWidget,
    "boolean": JSONBooleanWidget
}


def create_widget(name: str, schema: dict, schema_uri: str = None) -> JSONBaseWidget:
    """Create widget according to given JSON schema.
    if `schema_uri` is omitted, external references may only be resolved against absolute URI `id` fields--
    
    :param name: widget name
    :param schema: dict-like JSON object
    :param schema_uri: URI corresponding to given schema object
    """
    registry_class = create_cached_uri_loader_registry()
    registry = registry_class()

    http_loader = HTTPResourceLoader()
    file_resource_loader = FileResourceLoader()
    document_loader = DocumentLoader(schema, schema_uri)

    registry.register_for_scheme('http', http_loader)
    registry.register_for_scheme('https', http_loader)
    registry.register_for_scheme('file', file_resource_loader)
    registry.register_for_scheme(None, document_loader)

    ctx = Context(schema_uri or "#", registry)
    return _create_widget(name, schema, ctx, None)


def _create_widget(name: str, schema: dict, ctx: Context, parent: JSONBaseWidget) -> JSONBaseWidget:
    if "id" in schema:
        ctx = ctx.follow_uri(schema['id'])

    while "$ref" in schema:
        schema = ctx.dereference(schema['$ref'])

    if "enum" in schema:
        widget_class = JSONEnumWidget

    elif "type" in schema:
        schema_type = schema['type']
        widget_class = schema_type_to_widget_class.get(schema_type, UnsupportedSchemaWidget)

    else:
        widget_class = UnsupportedSchemaWidget

    # If instantiation fails, error
    try:
        widget = widget_class(name, schema, ctx, parent)

    except UnsupportedSchemaError:
        widget = UnsupportedSchemaWidget(name, schema, ctx, parent)

    widget.initialise()
    return widget
