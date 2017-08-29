"""
Widget definitions for JSON schema elements.
"""

from abc import abstractmethod
from ast import literal_eval

from PyQt5 import QtCore, QtWidgets, QtGui

from .tools import CachedURILoaderRegistry, FileResourceLoader, HTTPResourceLoader, Context, DocumentLoader


# Widgets supporting $ref
# $ref, items, allOf, anyOf, additionalItems, dependencies,
# oneOf, type, extends, properties, patternProperties,
# additionalProperties

def iter_layout_widgets(layout):
    for i in range(layout.count()):
        yield layout.itemAt(i).widget()


def iter_widgets(object):
    for i in range(object.count()):
        yield object.widget(i)


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

    def dump_json_object(self):
        return "(unsupported)"


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

    def load_json_object(self, data):
        raise NotImplementedError

    def dump_json_object(self):
        raise NotImplementedError


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

    @property
    @abstractmethod
    def primitive_class(self):
        pass


class JSONEnumWidget(JSONPrimitiveBaseWidget):
    """
        Widget representation of an enumerated property.
    """
    primitive_class = QtWidgets.QComboBox

    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, ctx, parent)

        items = [str(e) for e in schema['enum']]
        self.primitive_widget.addItems(items)

    def dump_json_object(self):
        as_string = self.primitive_widget.currentText()
        return literal_eval(as_string)

    def load_json_object(self, obj):
        as_string = str(obj)
        index = self.primitive_widget.findText(as_string)
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


class JSONIntegerWidget(JSONPrimitiveBaseWidget):
    """
        Widget representation of an integer (SpinBox)
    """
    primitive_class = QtWidgets.QSpinBox

    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, ctx, parent)

        self._set_limits(schema)

    def _set_limits(self, schema):
        if "minimum" in schema:
            minimum = schema['minimum']
            if schema.get("exclusiveMinimum", False):
                minimum += 1

            self.primitive_widget.setMinimum(minimum)

        if "maximum" in schema:
            maximum = schema['maximum']
            if schema.get("exclusiveMaximum", False):
                maximum -= 1

            self.primitive_widget.setMaximum(maximum)

    def load_json_object(self, data):
        self.primitive_widget.setValue(data)

    def dump_json_object(self):
        return self.primitive_widget.value()


class JSONNumberWidget(JSONPrimitiveBaseWidget):
    """
        Widget representation of a number (DoubleSpinBox)
    """
    primitive_class = QtWidgets.QDoubleSpinBox

    def __init__(self, name, schema, ctx, parent):
        super().__init__(name, schema, ctx, parent)

        self._set_limits(schema)

    def _set_limits(self, schema):
        if "minimum" in schema:
            minimum = schema['minimum']
            if schema.get("exclusiveMinimum", False):
                minimum += 0.01  # TODO

            self.primitive_widget.setMinimum(minimum)

        if "maximum" in schema:
            maximum = schema['maximum']
            if schema.get("exclusiveMaximum", False):
                maximum -= 0.01

            self.primitive_widget.setMaximum(maximum)

    def load_json_object(self, data):
        self.primitive_widget.setValue(data)

    def dump_json_object(self):
        return self.primitive_widget.value()


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
        super().__init__(name, schema, ctx, parent)

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


def create_widget(name, schema, schema_uri=None):
    """Create widget according to given JSON schema.
    if `schema_uri` is omitted, external references may only be resolved against absolute URI `id` fields--
    
    :param name: widget name
    :param schema: dict-like JSON object
    :param schema_uri: URI corresponding to given schema object
    """
    registry = CachedURILoaderRegistry()

    http_loader = HTTPResourceLoader()
    file_resource_loader = FileResourceLoader()
    document_loader = DocumentLoader(schema, schema_uri)

    registry.register_for_scheme('http', http_loader)
    registry.register_for_scheme('https', http_loader)
    registry.register_for_scheme('file', file_resource_loader)
    registry.register_for_scheme(None, document_loader)

    ctx = Context(schema_uri or "#", registry)
    return _create_widget(name, schema, ctx, None)


def _create_widget(name, schema, ctx, parent):
    if "id" in schema:
        ctx = ctx.follow_uri(schema['id'])

    if "$ref" in schema:
        schema = ctx.dereference(schema['$ref'])

    if "enum" in schema:
        return JSONEnumWidget(name, schema, ctx, parent)

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
