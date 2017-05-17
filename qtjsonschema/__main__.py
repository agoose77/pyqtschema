#!/usr/bin/env python
"""
pyqtschema - Python Qt JSON Schema Tool

Generate a dynamic Qt form representing a JSON Schema.
Filling the form will generate JSON.
"""

from PyQt5 import QtCore, QtGui, QtWidgets

from qtjsonschema.widgets import create_widget

class MainWindow(QtWidgets.QWidget):

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

        _action_open = QtWidgets.QAction("&Open Schema", self)
        _action_open.triggered.connect(self._handle_open)

        _action_save = QtWidgets.QAction("&Save", self)
        _action_save.triggered.connect(self._handle_save)

        _action_quit = QtWidgets.QAction("&Close", self)
        _action_quit.triggered.connect(self._handle_quit)

        self.file_menu.addAction(_action_open)
        self.file_menu.addAction(_action_save)
        self.file_menu.addSeparator()
        self.file_menu.addAction(_action_quit)

        # Scrollable region for schema form
        self.content_region = QtWidgets.QScrollArea(self)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.menu)
        vbox.addWidget(self.content_region)
        vbox.setContentsMargins(0,0,0,0)

        hbox = QtWidgets.QHBoxLayout()
        hbox.setContentsMargins(0,0,0,0)
        hbox.addLayout(vbox)

        self.setLayout(hbox)

    def process_schema(self, schema):
        """
            Load a schema and create the root element.
        """
        import json
        import collections
        with open(schema) as f:
            _schema = json.loads(f.read(), object_pairs_hook=collections.OrderedDict)

        from jsonschema import Draft4Validator
        Draft4Validator.check_schema(_schema)

        if "title" in _schema:
            self.setWindowTitle("%s - PyQtSchema" % _schema["title"])

        self.content_region.setWidget(create_widget(_schema.get("title", "(root)"), _schema))
        self.content_region.setWidgetResizable(True)

    def _handle_open(self):
        # Open JSON Schema
        schema, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open Schema', filter="JSON Schema (*.schema *.json)")
        if schema:
            self.process_schema(schema)

    def _handle_save(self):
        # Save JSON output
        import json
        obj = self.content_region.widget().to_json_object()
        outfile, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save JSON', filter="JSON (*.json)")
        if outfile:
            with open(outfile, 'w') as f:
                f.write(json.dumps(obj))

    def _handle_quit(self):
        # TODO: Check if saved?
        self.close()


import click

@click.command()
@click.option('--schema', default=None, help='Schema file to generate an editing window from.')
def json_editor(schema):
    import sys
    print(sys.argv)

    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()

    if schema:
        main_window.process_schema(schema)

    sys.exit(app.exec_())


if __name__ == "__main__":
    json_editor()
