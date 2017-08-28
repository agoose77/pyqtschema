#!/usr/bin/env python
"""
pyqtschema - Python Qt JSON Schema Tool

Generate a dynamic Qt form representing a JSON Schema.
Filling the form will generate JSON.
"""

from PyQt5 import QtCore, QtGui, QtWidgets

from qtjsonschema.widgets import create_widget

import sys
sys.excepthook = lambda *a:print(__import__("traceback").format_exc(*a))
class MainWindow(QtWidgets.QWidget):
    schema = None

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)

        self.setWindowTitle("PyQtSchema")

        # Menu bar
        # File
        #  Open
        #  Save
        #  --
        #  Close

        self.menu = QtWidgets.QMenuBar(self)
        self.file_menu = self.menu.addMenu("&File")

        _action_open_schema = QtWidgets.QAction("&Open File", self)
        _action_open_schema.triggered.connect(self._handle_open_json)

        _action_open_json = QtWidgets.QAction("Open &JSON Schema", self)
        _action_open_json.triggered.connect(self._handle_open_schema)

        _action_save = QtWidgets.QAction("&Save", self)
        _action_save.triggered.connect(self._handle_save)

        _action_quit = QtWidgets.QAction("&Close", self)
        _action_quit.triggered.connect(self._handle_quit)

        self.file_menu.addAction(_action_open_json)
        self.file_menu.addAction(_action_open_schema)
        self.file_menu.addAction(_action_save)
        self.file_menu.addSeparator()
        self.file_menu.addAction(_action_quit)

        # Scrollable region for schema form
        self.content_region = QtWidgets.QScrollArea(self)

        label = QtWidgets.QLabel()

        def update():
            from jsonschema.validators import validate
            from jsonschema.exceptions import _Error
            if self.schema_widget is None:
                return

            try:
                validate(self.schema_widget.dump_json_object(), self.schema)
            except _Error:
                label.setText("Object does not validate")
                label.setStyleSheet("QLabel { color: red; }")
            else:
                label.setText("Object validates")
                label.setStyleSheet("QLabel { color: green; }")

        timer = QtCore.QTimer(self)
        timer.setInterval(0.5)
        timer.timeout.connect(update)
        timer.start()


        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.menu)
        vbox.addWidget(label)
        vbox.addWidget(self.content_region)
        vbox.setContentsMargins(0,0,0,0)

        hbox = QtWidgets.QHBoxLayout()
        hbox.setContentsMargins(0,0,0,0)
        hbox.addLayout(vbox)

        self.setLayout(hbox)

    def process_schema(self, file_path):
        """
            Load a schema and create the root element.
        """
        import json
        import collections
        from pathlib import Path

        schema_path = Path(file_path).absolute()
        with open(schema_path) as f:
            _schema = json.loads(f.read(), object_pairs_hook=collections.OrderedDict)


        # Manual validation so we support multiple schema versions
        from jsonschema.validators import validator_for
        cls = validator_for(_schema)
        cls.check_schema(_schema)

        if "title" in _schema:
            self.setWindowTitle("%s - PyQtSchema" % _schema["title"])

        self.schema_widget = create_widget(_schema.get("title", "(root)"), _schema, schema_path.as_uri())
        self.content_region.setWidget(self.schema_widget)
        self.content_region.setWidgetResizable(True)
        self.schema = _schema

    def load_json(self, json_file):
        """
            Load a schema and create the root element.
        """
        import json
        import collections
        with open(json_file) as f:
            data = json.loads(f.read(), object_pairs_hook=collections.OrderedDict)
            # from jsonschema import validate
            # validate(data, self.schema)
            self.schema_widget.load_json_object(data)

    def _handle_open_json(self):
        # Open JSON File
        json_file, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open Schema', filter="JSON File (*.json)")
        if json_file:
            self.load_json(json_file)

    def _handle_open_schema(self):
        # Open JSON Schema
        schema, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open Schema', filter="JSON Schema (*.schema *.json)")
        if schema:
            self.process_schema(schema)

    def _handle_save(self):
        # Save JSON output
        import json
        obj = self.content_region.widget().dump_json_object()
        outfile, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save JSON', filter="JSON (*.json)")
        if outfile:
            with open(outfile, 'w') as f:
                f.write(json.dumps(obj))

    def _handle_quit(self):
        # TODO: Check if saved?
        self.close()



import jsonschema

import click

@click.command()
@click.option('--schema', default=None, help='Schema file to generate an editing window from.')
@click.option('--json', default=None, help='Schema file to generate an editing window from.')
def json_editor(schema, json):
    import sys

    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    main_window.resize(1000,800)

    if schema:
        main_window.process_schema(schema)
        if json:
            main_window.load_json(json)

    app.exec_()


if __name__ == "__main__":
    json_editor()
