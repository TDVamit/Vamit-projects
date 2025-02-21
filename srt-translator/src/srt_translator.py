import os
import boto3
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QCheckBox, QScrollArea, QLabel, QMessageBox, QComboBox, QProgressBar
)
import shutil

# Set AWS credentials
os.environ['AWS_ACCESS_KEY_ID'] = 'Your_Key'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'Your_Key'
os.environ['AWS_DEFAULT_REGION'] = 'ap-south-1'

# Initialize Amazon Translate client
translate_client = boto3.client('translate')


class TranslateWorker(QObject):
    current_srt = Signal(str)
    progress = Signal(int)  # Progress percentage signal
    finished = Signal()  # Signal when work is done
    error = Signal(str)  # Signal to communicate errors

    def __init__(self, srt_files, output_dir, languages, available_languages):
        super().__init__()
        self.srt_files = srt_files
        self.output_dir = output_dir
        self.languages = languages
        self.available_languages = available_languages

    def translate_srt(self):
        try:

            for input_path in self.srt_files:
                srt_name = os.path.splitext(os.path.basename(input_path))[0]
                with open(input_path, 'r', encoding='utf-8') as file:
                    content = file.readlines()
                for language in self.languages:
                    language_name = self.available_languages[language]
                    language_folder = os.path.join(self.output_dir, srt_name)
                    os.makedirs(language_folder, exist_ok=True)
                    output_path = rf"{os.path.join(language_folder, f"{srt_name}-{language_name}.srt")}"
                    if not os.path.exists(os.path.join(language_folder,f"{srt_name}.srt")):
                        shutil.copy(input_path,os.path.join(language_folder,f"{srt_name}.srt"))
                    if os.path.exists(output_path):
                        continue
                    self.current_srt.emit(f"{srt_name}-{language_name}.srt")
                    translated_lines = []
                    try:
                        for i,line in enumerate(content):
                            if not line.strip() or line.strip().isdigit() or '-->' in line:
                                translated_lines.append(line)
                            else:
                                translation = translate_client.translate_text(
                                    Text=line.strip(),
                                    SourceLanguageCode='en',
                                    TargetLanguageCode=language
                                )
                                translated_lines.append(translation['TranslatedText'] + '\n')
                            
                            progress = int((i / len(content)) * 100)
                            self.progress.emit(progress)
                    except Exception as e:
                        print("Error in translating:",str(e))
                        with open(os.path.abspath("logs.text"), 'w', encoding='utf-8') as output_file:
                            output_file.writelines(str(e)+ '\n')
                        continue

                    # Save translated SRT
                    
                    with open(output_path, 'w', encoding='utf-8') as output_file:
                        output_file.writelines(translated_lines)


            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class SRTTranslatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SRT Translator")
        self.resize(400, 500)

        self.languages = ['bn', 'gu', 'hi', 'kn', 'ml', 'mr', 'ta', 'ur']
        self.language_names = [
            'Bangla', 'Gujarati', 'Hindi', 'Kannada', 'Malayalam',
            'Marathi','Tamil', 'Urdu'
        ]
        self.available_languages = {  # Mapping of language codes to names
            'af': 'Afrikaans', 'sq': 'Albanian', 'am': 'Amharic', 'ar': 'Arabic', 'hy': 'Armenian',
            'az': 'Azerbaijani', 'bn': 'Bangla', 'bs': 'Bosnian', 'bg': 'Bulgarian', 'ca': 'Catalan',
            'zh': 'Chinese (Simplified)', 'zh-TW': 'Chinese (Traditional)', 'hr': 'Croatian', 'cs': 'Czech',
            'da': 'Danish', 'nl': 'Dutch', 'en': 'English', 'et': 'Estonian', 'fi': 'Finnish', 
            'fr': 'French', 'de': 'German', 'el': 'Greek', 'gu': 'Gujarati', 'ht': 'Haitian Creole',
            'ha': 'Hausa', 'he': 'Hebrew', 'hi': 'Hindi', 'hu': 'Hungarian', 'is': 'Icelandic',
            'id': 'Indonesian', 'ga': 'Irish', 'it': 'Italian', 'ja': 'Japanese', 'kn': 'Kannada',
            'kk': 'Kazakh', 'ko': 'Korean', 'lv': 'Latvian', 'lt': 'Lithuanian', 'mk': 'Macedonian',
            'ms': 'Malay', 'ml': 'Malayalam', 'mt': 'Maltese', 'mr': 'Marathi', 'mn': 'Mongolian',
            'no': 'Norwegian', 'fa': 'Persian', 'pl': 'Polish', 'pt': 'Portuguese', 'ro': 'Romanian',
            'ru': 'Russian', 'sr': 'Serbian', 'sk': 'Slovak', 'sl': 'Slovenian', 'so': 'Somali',
            'es': 'Spanish', 'sw': 'Swahili', 'sv': 'Swedish', 'tl': 'Tagalog', 'ta': 'Tamil',
            'te': 'Telugu', 'th': 'Thai', 'tr': 'Turkish', 'uk': 'Ukrainian', 'ur': 'Urdu',
            'uz': 'Uzbek', 'vi': 'Vietnamese', 'cy': 'Welsh', 'xh': 'Xhosa', 'zu': 'Zulu'
        }
        self.selected_languages = []
        self.srt_files = []
        self.output_dir = None
        self.worker_thread = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Buttons to load SRT files and set output directory
        btn_load_srt = QPushButton("Load SRT Files")
        btn_load_srt.clicked.connect(self.load_srt_files)
        layout.addWidget(btn_load_srt)

        btn_set_output_dir = QPushButton("Set Output Directory")
        btn_set_output_dir.clicked.connect(self.set_output_directory)
        layout.addWidget(btn_set_output_dir)

        # Scrollable list of checkboxes for languages
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout()
        self.checkboxes = []

        for lang, name in zip(self.languages, self.language_names):
            checkbox = QCheckBox(name)
            checkbox.setChecked(True)
            self.checkboxes.append(checkbox)
            self.scroll_layout.addWidget(checkbox)

        scroll_widget.setLayout(self.scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        # Toggle select/deselect all button
        self.btn_select_toggle = QPushButton("Select All")
        self.btn_select_toggle.clicked.connect(self.toggle_select_languages)
        layout.addWidget(self.btn_select_toggle)

        # Add new language
        add_language_layout = QHBoxLayout()
        self.language_dropdown = QComboBox()
        self.language_dropdown.addItems(
            [f"{name} ({code})" for code, name in self.available_languages.items()]
        )
        btn_add_language = QPushButton("Add Language")
        btn_add_language.clicked.connect(self.add_new_language)
        add_language_layout.addWidget(self.language_dropdown)
        add_language_layout.addWidget(btn_add_language)
        layout.addLayout(add_language_layout)

        # Translate button
        btn_translate = QPushButton("Translate")
        btn_translate.clicked.connect(self.start_translation)
        layout.addWidget(btn_translate)

        # Progress bar
        self.current_srt = QLabel("No Srt is being Translated...")
        layout.addWidget(self.current_srt)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def load_srt_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select SRT Files", "", "SRT Files (*.srt)")
        if files:
            self.srt_files = files
            self.status_label.setText(f"Loaded {len(files)} SRT file(s).")

    def set_output_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_dir = directory
            self.status_label.setText(f"Output directory set to: {directory}")

    def toggle_select_languages(self):
        all_checked = all(checkbox.isChecked() for checkbox in self.checkboxes)
        for checkbox in self.checkboxes:
            checkbox.setChecked(not all_checked)
        self.btn_select_toggle.setText("Deselect All" if not all_checked else "Select All")

    def add_new_language(self):
        selected_item = self.language_dropdown.currentText()
        lang_code = selected_item.split('(')[-1][:-1]  # Extract language code
        if lang_code not in self.languages:
            self.languages.append(lang_code)
            checkbox = QCheckBox(selected_item.split('(')[0].strip())
            checkbox.setChecked(True)
            self.checkboxes.append(checkbox)
            self.scroll_layout.addWidget(checkbox)
            self.status_label.setText(f"Added new language: {selected_item}")
        else:
            QMessageBox.warning(self, "Warning", "Language already added!")

    def start_translation(self):
        if not self.srt_files:
            QMessageBox.warning(self, "Warning", "No SRT files loaded!")
            return

        if not self.output_dir:
            QMessageBox.warning(self, "Warning", "Output directory not set!")
            return

        self.selected_languages = [
            lang for checkbox, lang in zip(self.checkboxes, self.languages) if checkbox.isChecked()
        ]

        if not self.selected_languages:
            QMessageBox.warning(self, "Warning", "No languages selected!")
            return

        # Create and start the worker thread
        self.worker = TranslateWorker(self.srt_files, self.output_dir, self.selected_languages,self.available_languages)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.translate_srt)
        self.worker.current_srt.connect(self.update_current_srt)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.translation_finished)
        self.worker.error.connect(self.translation_error)

        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_current_srt(self, current_srt):
        self.current_srt.setText(current_srt)

    def translation_finished(self):
        QMessageBox.information(self, "Success", "Translation complete!")
        self.status_label.setText("Translation complete!")

    def translation_error(self, error_message):
        QMessageBox.critical(self, "Error", f"An error occurred: {error_message}")
        self.status_label.setText("An error occurred during translation.")


if __name__ == "__main__":
    app = QApplication([])
    window = SRTTranslatorApp()
    window.show()
    app.exec()
