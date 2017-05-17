"""
Widget definitions for JSON schema elements.
"""
from PyQt5 import QtCore, QtGui, QtWidgets

class UnsupportedSchema(QtWidgets.QLabel):
    """
        Widget representation of an unsupported schema element.

        Presents a label noting the name of the element and its type.
        If the element is a reference, the reference name is listed instead of a type.
    """
    def __init__(self, name, schema, parent=None):
        self.name = name
        self.schema = schema
        self._type = schema.get("type", schema.get("$ref", "(?)"))
        QtWidgets.QLabel.__init__(self, "(Unsupported schema entry: %s, %s)" % (name, self._type), parent)
        self.setStyleSheet("QLabel { font-style: italic; }")

    def to_json_object(self):
        return "(unsupported)"


class JsonBaseWidget(object):
    def __init__(self, name, schema, parent=None):
        super().__init__(name, parent)
        self.name = name
        self.schema = schema

class JsonObject(JsonBaseWidget, QtWidgets.QGroupBox):
    """
        Widget representation of an object.

        Objects have properties, each of which is a widget of its own.
        We display these in a groupbox, which on most platforms will
        include a border.
    """
    def __init__(self, name, schema, parent=None):
        super().__init__(name, schema, parent)
        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.setAlignment(QtCore.Qt.AlignTop)
        self.setLayout(self.vbox)
        self.setFlat(False)

        if "description" in schema:
            self.setToolTip(schema['description'])

        self.properties = {}

        if "properties" not in schema:
            label = QtWidgets.QLabel("Invalid object description (missing properties)", self)
            label.setStyleSheet("QLabel { color: red; }")
            self.vbox.addWidget(label)
        else:
            for k, v in schema['properties'].items():
                widget = create_widget(k, v)
                self.vbox.addWidget(widget)
                self.properties[k] = widget

    def to_json_object(self):
        out = {}
        for k, v in self.properties.items():
            out[k] = v.to_json_object()
        return out


class JsonString(QtWidgets.QWidget):
    """
        Widget representation of a string.

        Strings are text boxes with labels for names.
    """
    def __init__(self, name, schema, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.name = name
        self.schema = schema
        hbox = QtWidgets.QHBoxLayout()

        self.label = QtWidgets.QLabel(name)
        self.edit  = QtWidgets.QLineEdit()

        if "description" in schema:
            self.label.setToolTip(schema['description'])

        hbox.addWidget(self.label)
        hbox.addWidget(self.edit)

        self.setLayout(hbox)

    def to_json_object(self):
        return str(self.edit.text())


class JsonInteger(QtWidgets.QWidget):
    """
        Widget representation of an integer (SpinBox)
    """
    def __init__(self, name, schema, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.name = name
        self.schema = schema
        hbox = QtWidgets.QHBoxLayout()

        self.label = QtWidgets.QLabel(name)
        self.spin  = QtWidgets.QSpinBox()

        if "description" in schema:
            self.label.setToolTip(schema['description'])

        # TODO: min/max

        hbox.addWidget(self.label)
        hbox.addWidget(self.spin)

        self.setLayout(hbox)

    def to_json_object(self):
        return self.spin.value()


class JsonNumber(QtWidgets.QWidget):
    """
        Widget representation of a number (DoubleSpinBox)
    """
    def __init__(self, name, schema, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.name = name
        self.schema = schema
        hbox = QtWidgets.QHBoxLayout()

        self.label = QtWidgets.QLabel(name)
        self.spin  = QtWidgets.QDoubleSpinBox()

        if "description" in schema:
            self.label.setToolTip(schema['description'])

        # TODO: min/max

        hbox.addWidget(self.label)
        hbox.addWidget(self.spin)

        self.setLayout(hbox)

    def to_json_object(self):
        return self.spin.value()


class JsonArray(QtWidgets.QWidget):
    """
        Widget representation of an array.

        Arrays can contain multiple objects of a type, or
        they can contain objects of specific types.

        We include a label and button for adding types.
    """
    def __init__(self, name, schema, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.name = name
        self.schema = schema
        self.count = 0
        self.vbox = QtWidgets.QVBoxLayout()

        self.controls = QtWidgets.QHBoxLayout()

        label = QtWidgets.QLabel(name, self)
        label.setStyleSheet("QLabel { font-weight: bold; }")

        if "description" in schema:
            self.label.setToolTip(schema['description'])

        button = QtWidgets.QPushButton("Append Item", self)
        button.clicked.connect(self.click_add)

        self.controls.addWidget(label)
        self.controls.addWidget(button)

        self.vbox.addLayout(self.controls)

        self.setLayout(self.vbox)

    def click_add(self):
        # TODO: Support array for "items"
        # TODO: Support additionalItems
        if "items" in self.schema:
            obj = create_widget("Item #%d" % (self.count,), self.schema['items'], self)
            self.count += 1
            self.vbox.addWidget(obj)

    def to_json_object(self):
        out = []
        for i in range(1, self.vbox.count()):
            widget = self.vbox.itemAt(i).widget()
            if "to_json_object" in dir(widget):
                out.append(widget.to_json_object())
        return out


class JsonBoolean(QtWidgets.QCheckBox):
    """
        Widget representing a boolean (CheckBox)
    """
    def __init__(self, name, schema, parent=None):
        QtWidgets.QCheckBox.__init__(self, name, parent)
        self.name = name
        self.schema = schema

        if "description" in schema:
            self.setToolTip(schema['description'])

    def to_json_object(self):
        return bool(self.isChecked())


def create_widget(name, schema, parent=None):
    """
        Create the appropriate widget for a given schema element.
    """
    if "type" not in schema:
        return UnsupportedSchema(name, schema, parent)

    if schema['type'] == "object":
        return JsonObject(name, schema, parent)
    elif schema['type'] == "string":
        return JsonString(name, schema, parent)
    elif schema['type'] == "integer":
        return JsonInteger(name, schema, parent)
    elif schema['type'] == "array":
        return JsonArray(name, schema, parent)
    elif schema['type'] == "number":
        return JsonNumber(name, schema, parent)
    elif schema['type'] == "boolean":
        return JsonBoolean(name, schema, parent)

    # TODO: refs

    return UnsupportedSchema(name, schema, parent)


