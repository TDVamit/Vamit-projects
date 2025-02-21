import sys
import os
import subprocess
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QSlider, QLineEdit, QLabel)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtCore import Qt
from moviepy.editor import VideoFileClip, concatenate_videoclips
import pysrt


class VideoEditorApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Video Editor App")
        self.setGeometry(100, 100, 800, 600)

        # Default Intro Video Path
        self.default_intro_path = "E:\\#Mehul\\Extra\\intro.mp4"

        # Layouts
        self.layout = QVBoxLayout()
        self.file_buttons_layout = QHBoxLayout()
        self.control_buttons_layout = QHBoxLayout()

        # Video Player
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.video_widget = QVideoWidget()
        self.media_player.setVideoOutput(self.video_widget)

        # Timeline Slider
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setRange(0, 0)
        self.timeline_slider.sliderMoved.connect(self.set_position)

        # Play/Pause Button
        self.play_pause_button = QPushButton("Play")
        self.play_pause_button.setMaximumWidth(40)
        self.play_pause_button.clicked.connect(self.toggle_play_pause)

        # File Selection Buttons
        self.select_english_video_btn = QPushButton("English Video")
        self.select_hindi_video_btn = QPushButton("Hindi Video")
        self.select_intro_video_btn = QPushButton("Intro Video")
        self.select_srt_btn = QPushButton("SRT File")

        self.select_english_video_btn.clicked.connect(self.select_english_video)
        self.select_hindi_video_btn.clicked.connect(self.select_hindi_video)
        self.select_intro_video_btn.clicked.connect(self.select_intro_video)
        self.select_srt_btn.clicked.connect(self.select_srt_file)

        self.update_button_color(self.select_intro_video_btn, bool(self.default_intro_path))

        # Start and End Selection
        self.start_time_edit = QLineEdit("0.000")
        self.start_time_edit.setMaximumWidth(60)
        self.select_start_btn = QPushButton("{")
        self.select_start_btn.setMaximumWidth(20)
        self.select_start_btn.clicked.connect(self.set_start_timestamp)

        self.end_time_edit = QLineEdit("0.000")
        self.end_time_edit.setMaximumWidth(60)
        self.select_end_btn = QPushButton("}")
        self.select_end_btn.setMaximumWidth(20)
        self.select_end_btn.clicked.connect(self.set_end_timestamp)

        # Export Button
        self.export_btn = QPushButton("Export")
        self.export_btn.setMaximumWidth(50)
        self.export_btn.clicked.connect(self.export_video)

        # Arrange Layouts
        self.layout.addWidget(self.video_widget)
        self.layout.addLayout(self.file_buttons_layout)

        self.file_buttons_layout.addWidget(self.select_english_video_btn)
        self.file_buttons_layout.addWidget(self.select_hindi_video_btn)
        self.file_buttons_layout.addWidget(self.select_intro_video_btn)
        self.file_buttons_layout.addWidget(self.select_srt_btn)

        self.control_buttons_layout.addWidget(self.play_pause_button)
        self.control_buttons_layout.addWidget(self.timeline_slider)
        self.control_buttons_layout.addWidget(self.select_start_btn)
        self.control_buttons_layout.addWidget(self.start_time_edit)
        self.control_buttons_layout.addWidget(QLabel(":"))
        self.control_buttons_layout.addWidget(self.end_time_edit)
        self.control_buttons_layout.addWidget(self.select_end_btn)
        self.control_buttons_layout.addWidget(self.export_btn)

        self.layout.addLayout(self.control_buttons_layout)
        self.setLayout(self.layout)

        # Video & Timestamps
        self.english_video = ""
        self.hindi_video = ""
        self.intro_video = self.default_intro_path if os.path.exists(self.default_intro_path) else ""
        self.srt_file = ""
        self.start_time = None
        self.end_time = None

        # Media Player Signals
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)

    def update_button_color(self, button, is_selected):
        button.setStyleSheet(f"background-color: {'green' if is_selected else 'red'};")

    def select_english_video(self):
        self.english_video, _ = QFileDialog.getOpenFileName(self, "Select English Video", "", "Video Files (*.mp4 *.mkv)")
        self.update_button_color(self.select_english_video_btn, bool(self.english_video))
        if self.english_video:
            self.media_player.setSource(self.english_video)

    def select_hindi_video(self):
        self.hindi_video, _ = QFileDialog.getOpenFileName(self, "Select Hindi Video", "", "Video Files (*.mp4 *.mkv)")
        self.update_button_color(self.select_hindi_video_btn, bool(self.hindi_video))

    def select_intro_video(self):
        self.intro_video, _ = QFileDialog.getOpenFileName(self, "Select Intro Video", "", "Video Files (*.mp4 *.mkv)")
        self.update_button_color(self.select_intro_video_btn, bool(self.intro_video))

    def select_srt_file(self):
        self.srt_file, _ = QFileDialog.getOpenFileName(self, "Select SRT File", "", "Subtitle Files (*.srt)")
        self.update_button_color(self.select_srt_btn, bool(self.srt_file))

    def toggle_play_pause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            self.play_pause_button.setText("Play")
        else:
            self.media_player.play()
            self.play_pause_button.setText("Pause")

    def set_position(self, position):
        self.media_player.setPosition(position)

    def position_changed(self, position):
        self.timeline_slider.setValue(position)

    def duration_changed(self, duration):
        self.timeline_slider.setRange(0, duration)

    def set_start_timestamp(self):
        self.start_time = self.media_player.position() / 1000  # Convert to seconds with milliseconds precision
        self.start_time_edit.setText(f"{self.start_time:.3f}")

    def set_end_timestamp(self):
        self.end_time = self.media_player.position() / 1000  # Convert to seconds with milliseconds precision
        self.end_time_edit.setText(f"{self.end_time:.3f}")

    def export_video(self):
        if not all([self.english_video, self.hindi_video, self.intro_video, self.srt_file]):
            QMessageBox.critical(self, "Error", "Please select all required files before exporting.")
            return

        if float(self.end_time_edit.text()) - float(self.start_time_edit.text()) < 0:
            QMessageBox.critical(self, "Error", "Please select valid start and end time")
            return

        output_video = QFileDialog.getSaveFileName(self, "Save Output Video", "", "Video Files (*.mp4)")[0]

        try:
            # Process Video
            self.process_video(output_video)
            # Process Subtitle
            self.process_srt(output_video)

            QMessageBox.information(self, "Success", "Video and subtitles exported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def process_video(self, output_video):
        combined_video = "combined_temp.mp4"
    
        # Combine Hindi video and English audio
        subprocess.run([
            "ffmpeg", "-i", self.hindi_video, "-i", self.english_video, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
            combined_video, "-y"
        ], check=True)
    
        new_combined_video = VideoFileClip(combined_video)
        before_video = new_combined_video.subclip(0,float(self.start_time_edit.text()))
        intro = VideoFileClip(self.intro_video)
        after_video = new_combined_video.subclip(float(self.end_time_edit.text()), new_combined_video.duration)
        clips = [before_video,intro,after_video]
        final_clip = concatenate_videoclips(clips)

        if output_video:
            final_clip.write_videofile(output_video)

        for clip in clips:
            clip.close()

        os.remove(combined_video)


    def process_srt(self, output_video):
        intro_duration = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            self.intro_video
        ]).decode().strip())

        subs = pysrt.open(self.srt_file)
        srt_save_path = output_video.replace(".mp4",".srt")

        addition_duration = intro_duration - (float(self.end_time_edit.text()) - float(self.start_time_edit.text()))

        start_time_srt = pysrt.SubRipTime.from_ordinal(float(self.start_time_edit.text())*1000)
        end_time_srt = pysrt.SubRipTime.from_ordinal(float(self.end_time_edit.text())*1000)

        modified_subs = pysrt.SubRipFile()

        for sub in subs:
            if sub.end <= start_time_srt:
                # If the subtitle ends before the start time, keep it as is
                modified_subs.append(sub)
            elif sub.start >= end_time_srt:
                # If the subtitle starts after the end time, shift it by addition_duration
                shifted_sub = sub
                shifted_sub.start = pysrt.SubRipTime.from_ordinal(sub.start.ordinal + addition_duration * 1000)
                shifted_sub.end = pysrt.SubRipTime.from_ordinal(sub.end.ordinal + addition_duration * 1000)
                modified_subs.append(shifted_sub)
            elif sub.start < start_time_srt and sub.end > start_time_srt:
                # If the subtitle overlaps the start time, trim it to end at start time
                new_sub = sub
                new_sub.end = start_time_srt  # Trim the end time
                modified_subs.append(new_sub)
            elif sub.start < end_time_srt and sub.end > end_time_srt:
                # If the subtitle overlaps the end time, trim it to start at end time
                shifted_sub = sub
                shifted_sub.start = pysrt.SubRipTime.from_ordinal(end_time_srt.ordinal + addition_duration * 1000)  # Trim the start time
                shifted_sub.end = pysrt.SubRipTime.from_ordinal(sub.end.ordinal + addition_duration * 1000)                
                modified_subs.append(shifted_sub)
            # Any subtitle fully between start_time and end_time is skipped (i.e., removed).

        # Renumber the subtitles and save to a new SRT file
        modified_subs.clean_indexes()
        modified_subs.save(srt_save_path, encoding='utf-8')

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            self.media_player.setPosition(self.media_player.position() + 5)
        elif event.key() == Qt.Key_Left:
            self.media_player.setPosition(self.media_player.position() - 5)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoEditorApp()
    window.show()
    sys.exit(app.exec())
