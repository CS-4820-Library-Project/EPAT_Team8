from PyQt6.uic import loadUi
from PyQt6.QtWidgets import QDialog, QTableWidgetItem, QTextEdit, QComboBox, QWidget
from src.utility.export import export_data
import math


import os

# this class defines the search page please add the search page code here
class searchDisplay(QDialog):
    def __init__(self, widget):
        super(searchDisplay, self).__init__()
        ui_file = os.path.join(os.path.dirname(__file__), "searchDisplay.ui")
        loadUi(ui_file, self)

        # this is the back button that will take to the startscreen from the searchdisplay
        self.backButton.clicked.connect(self.backToStartScreen)
        self.exportButton.clicked.connect(self.export_data_handler)
        self.widget = widget
        self.results = []
        self.original_widget_values = None

    def backToStartScreen(self):
        from src.user_interface.startScreen import startScreen
        backButton = startScreen.get_instance(self.widget)
        self.widget.addWidget(backButton)
        self.widget.setCurrentIndex(self.widget.currentIndex() + 1)

    def display_results_in_table(self, results):
        self.results = results
        self.tableWidget.setRowCount(0)  # Clear existing rows
        self.tableWidget.setColumnCount(len(results[0])) if results else self.tableWidget.setColumnCount(0)

        for row_number, row_data in enumerate(results):
            self.tableWidget.insertRow(row_number)
            for column_number, data in enumerate(row_data):
                self.tableWidget.setItem(row_number, column_number, QTableWidgetItem(str(data)))
        self.update_all_sizes()

    def export_data_handler(self):
        export_data(self.results)

    def update_all_sizes(self):
        original_width = 1200
        original_height = 800
        new_width = self.width() + 25
        new_height = self.height()

        if self.original_widget_values is None:
            # If it's the first run, store the original values
            self.original_widget_values = {}
            for widget in self.findChildren(QWidget):
                self.original_widget_values[widget] = {
                    'geometry': widget.geometry(),
                    'font_size': widget.font().pointSize() if isinstance(widget, (QTextEdit, QComboBox)) else None
                }

        # Iterate through every widget loaded using loadUi
        for widget, original_values in self.original_widget_values.items():
            # Calculate new geometry and size for each widget
            x = int(original_values['geometry'].x() * (new_width / original_width))
            y = int(original_values['geometry'].y() * (new_height / original_height))
            width = int(original_values['geometry'].width() * (new_width / original_width))
            height = int(original_values['geometry'].height() * (new_height / original_height))

            # Set the new geometry and size
            widget.setGeometry(x, y, width, height)

            # If the widget is a QTextEdit or QComboBox, adjust font size
            if isinstance(widget, (QTextEdit, QComboBox)):
                font = widget.font()
                original_font_size = original_values['font_size']
                if original_font_size is not None:
                    font.setPointSize(int(original_font_size * (new_width / original_width)))
                widget.setFont(font)
        
        table_width = int(0.8 * new_width)
        self.tableWidget.setFixedWidth(table_width)

         # Calculate the width for each column
        num_columns = self.tableWidget.columnCount()
        column_width = math.floor(table_width / num_columns) if num_columns > 0 else 0
        column_width -= 16

        # Set the calculated width for each column
        for column_number in range(num_columns):
            self.tableWidget.setColumnWidth(column_number, column_width)

    def resizeEvent(self, event):
        # Override the resizeEvent method to call update_all_sizes when the window is resized
        super().resizeEvent(event)
        self.update_all_sizes()

