import os
import re
import shutil
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QPushButton, QLabel, QProgressBar,
    QFileDialog, QTreeView, QFileSystemModel, QWidget, QMessageBox, QAbstractItemView, QHeaderView
)
from PySide6.QtCore import QDir, Qt, QThread, Signal


class FileCopierThread(QThread):
    progress = Signal(int)

    def __init__(self, selected_folders, destination_folder):
        super().__init__()
        self.selected_folders = selected_folders
        self.destination_folder = destination_folder

    def run(self):
        total_files = 0
        copied_files = 0

        # Count total files
        for folder in self.selected_folders:
            for _, _, files in os.walk(folder):
                total_files += len(files)   

        # Copy files
        for folder in self.selected_folders:
            # Create the root folder in the destination
            root_folder_name = os.path.basename(folder)
            dest_root_folder = os.path.join(self.destination_folder, root_folder_name)
            os.makedirs(dest_root_folder, exist_ok=True)

            for root, dirs, files in os.walk(folder):
                relative_path = os.path.relpath(root, folder)
                dest_path = os.path.join(dest_root_folder, relative_path)
                os.makedirs(dest_path, exist_ok=True)

                for file in files:
                    source_file = os.path.join(root, file)
                    dest_file_name = file

                    if file.endswith(".lnk"):
                        # Extract base name, unique ID, and file extension
                        match = re.search(r"(.+)=\(([\w-]+)\)\.(\w+)\.lnk$", file)
                        if match:
                            base_name, file_id, file_ext = match.groups()
                            original_file = os.path.join("Downloads", f"{file_id}.{file_ext}")
                            dest_file_name = f"{base_name.strip()}.{file_ext}"

                            if os.path.exists(original_file):
                                source_file = original_file
                            else:
                                print(f"Original file not found for shortcut: {file}")
                                continue
                        else:
                            print(f"Invalid shortcut format: {file}")
                            continue

                    dest_file = os.path.join(dest_path, dest_file_name)
                    if os.path.exists(source_file):
                        shutil.copy2(source_file, dest_file)

                    copied_files += 1
                    self.progress.emit(int((copied_files / total_files) * 100))

class CustomFileSystemModel(QFileSystemModel):
    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            file_path = self.filePath(index)
            if file_path.endswith(".lnk"):
                return os.path.basename(file_path)  # Show the actual name of the shortcut
        return super().data(index, role)


class FileCopierApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Copier")
        self.resize(800, 600)

        self.source_folder = os.path.abspath("App Backup")
        self.destination_folder = os.path.abspath("Coppied")
        os.makedirs(self.destination_folder, exist_ok=True)

        self.file_model = CustomFileSystemModel()
        self.file_model.setRootPath(self.source_folder)

        self.tree_view = QTreeView()
        self.tree_view.setModel(self.file_model)
        self.tree_view.setRootIndex(self.file_model.index(self.source_folder))
        self.tree_view.setSelectionMode(QAbstractItemView.MultiSelection)

        # Configure header for proper resizing
        header = self.tree_view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Resize column to fit content

        self.tree_view.selectionModel().selectionChanged.connect(self.highlight_selected)

        self.select_dest_button = QPushButton("Select Destination")
        self.select_dest_button.clicked.connect(self.select_destination)

        self.destination_label = QLabel(f"Destination: {self.destination_folder}")
        self.update_destination_label()

        self.copy_button = QPushButton("Copy Files")
        self.copy_button.clicked.connect(self.copy_files)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        layout = QVBoxLayout()
        layout.addWidget(self.tree_view)
        layout.addWidget(self.destination_label)
        layout.addWidget(self.select_dest_button)
        layout.addWidget(self.copy_button)
        layout.addWidget(self.progress_bar)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)


    def select_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder:
            self.destination_folder = folder
            self.update_destination_label()

    def update_destination_label(self):
        if self.destination_folder:
            self.destination_label.setText(f"Destination: {self.destination_folder}")
            self.destination_label.setStyleSheet("color: green;")
        else:
            self.destination_label.setText("Destination: Not Selected")
            self.destination_label.setStyleSheet("color: red;")

    def highlight_selected(self):
        indexes = self.tree_view.selectionModel().selectedIndexes()
        selected_paths = set(
            self.file_model.filePath(index) for index in indexes if self.file_model.isDir(index)
        )

        for index in self.tree_view.selectedIndexes():
            path = self.file_model.filePath(index)
            is_child_of_selected = any(path.startswith(selected) and path != selected for selected in selected_paths)
            if is_child_of_selected:
                self.tree_view.selectionModel().select(index, QAbstractItemView.Deselect)

        # Highlight selected items in red
        self.tree_view.setStyleSheet("""
            QTreeView::item:selected { background-color: red; }
        """)

    def copy_files(self):
        indexes = self.tree_view.selectionModel().selectedIndexes()
        selected_folders = set(
            self.file_model.filePath(index) for index in indexes if self.file_model.isDir(index)
        )

        if not selected_folders:
            QMessageBox.warning(self, "No Selection", "Please select folders to copy.")
            return

        if not self.destination_folder:
            QMessageBox.warning(self, "No Destination", "Please select a destination folder.")
            return

        self.copy_thread = FileCopierThread(selected_folders, self.destination_folder)
        self.copy_thread.progress.connect(self.update_progress)
        self.copy_thread.finished.connect(self.copy_finished)
        self.copy_button.setEnabled(False)
        self.copy_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def copy_finished(self):
        self.copy_button.setEnabled(True)
        QMessageBox.information(self, "Copy Complete", "All files have been copied.")


if __name__ == "__main__":
    app = QApplication([])
    window = FileCopierApp()
    window.show()
    app.exec()