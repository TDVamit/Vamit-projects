import sys
import os
import requests
import json
import numpy as np
import base64
import pysrt
import random
import string
import wave
import warnings
import shutil
import bisect
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtWidgets import (
     QDialog,QDialogButtonBox,QListWidget, QListWidgetItem,QComboBox,QGraphicsDropShadowEffect, QCheckBox, QGraphicsView, QGraphicsScene, QGraphicsLineItem,QGraphicsPathItem,QLineEdit, QStyle, QApplication, QMainWindow,QProgressBar, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel, QFileDialog, QMessageBox, QScrollArea, QFrame, QSlider , QGraphicsView, QGraphicsScene
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget,QGraphicsVideoItem
from PySide6.QtCore import QPointF, QThread, Signal, Slot, QUrl, Qt , QTimer, QRect, QUrl, QPoint,QEvent
from PySide6.QtGui import QFont,QShortcut, QTransform, QPalette, QBrush , QIcon,QTextCursor,QImage, QPixmap,QPen, QPainterPath, QColor,QPainter , QKeySequence
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from sklearn.linear_model import LinearRegression
from joblib import dump, load
from pydub import AudioSegment
from moviepy.editor import VideoFileClip, concatenate_videoclips , vfx, AudioFileClip, ColorClip, concatenate_audioclips
import soundfile as sf
import subprocess
import io
from datetime import timedelta
import openai
import time
from mutagen import File
import threading
import re
import boto3
from datetime import datetime
import uuid


os.environ['AWS_ACCESS_KEY_ID'] = ''
os.environ['AWS_SECRET_ACCESS_KEY'] = ''
os.environ['AWS_DEFAULT_REGION'] = 'ap-south-1' 

# AWS Clients
s3_client = boto3.client('s3')
transcribe_client = boto3.client('transcribe')



AudioSegment.converter = "ffmpeg"  


warnings.filterwarnings('ignore', category=FutureWarning, module='transformers.tokenization_utils_base')




class DownloadThread(QThread):
    progress_signal = Signal(int)

    def __init__(self, file_list, local_json_dir):
        super().__init__()
        self.file_list = file_list
        self.local_json_dir = local_json_dir

    def run(self):
        os.makedirs(self.local_json_dir, exist_ok=True)
        max_threads = 5
        with ThreadPoolExecutor(max_threads) as executor:
            future_to_file = {executor.submit(self.download_file, file): file for file in self.file_list}
            for count, future in enumerate(as_completed(future_to_file), 1):
                future.result()
                self.progress_signal.emit(count)

    def download_file(self, file):
        try:
            file_path = os.path.join(self.local_json_dir, file['title'])
            if not os.path.exists(file_path): 
                file.GetContentFile(file_path)
        except Exception as e:
            print(f'Failed to download {file["title"]}: {str(e)}')

class UploadThread(QThread):
    progress_signal = Signal(int)

    def __init__(self, local_json_dir, drive_folder_id):
        super().__init__()
        self.local_json_dir = local_json_dir
        self.drive_folder_id = drive_folder_id

    def run(self):
        gauth = GoogleAuth()
        gauth.LoadCredentialsFile("mycreds.txt")

        if gauth.credentials is None:
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            gauth.Refresh()
        else:
            gauth.Authorize()

        gauth.SaveCredentialsFile("mycreds.txt")
        self.drive = GoogleDrive(gauth)

        file_list = self.drive.ListFile({'q': f"'{self.drive_folder_id}' in parents and trashed=false"}).GetList()
        existing_files = {file['title']: file['id'] for file in file_list}

        json_files = [f for f in os.listdir(self.local_json_dir) if f.endswith('.json')]

        max_threads = 5
        with ThreadPoolExecutor(max_threads) as executor:
            future_to_file = {executor.submit(self.upload_file, file, existing_files): file for file in json_files}
            for count, future in enumerate(as_completed(future_to_file), 1):
                future.result()
                self.progress_signal.emit(count)

    def upload_file(self, file, existing_files):
        try:
            if file not in existing_files:
                file_path = os.path.join(self.local_json_dir, file)
                drive_file = self.drive.CreateFile({'title': file, 'parents': [{'id': self.drive_folder_id}]})
                drive_file.SetContentFile(file_path)
                drive_file.Upload()
        except Exception as e:
            print(f'Failed to upload {file}: {str(e)}')

class Downloadmp3Thread(QThread):
    progress_signal = Signal(int)

    def __init__(self, file_list, local_mp3_dir):
        super().__init__()
        self.file_list = file_list
        self.local_mp3_dir = local_mp3_dir

    def run(self):
        os.makedirs(self.local_mp3_dir, exist_ok=True)
        max_threads = 5
        with ThreadPoolExecutor(max_threads) as executor:
            future_to_file = {executor.submit(self.download_file, file): file for file in self.file_list}
            for count, future in enumerate(as_completed(future_to_file), 1):
                future.result()
                self.progress_signal.emit(count)

    def download_file(self, file):
        try:
            file_path = os.path.join(self.local_mp3_dir, file['title'])
            if not os.path.exists(file_path):  
                file.GetContentFile(file_path)
        except Exception as e:
            print(f'Failed to download {file["title"]}: {str(e)}')

class Uploadmp3Thread(QThread):
    progress_signal = Signal(int)

    def __init__(self, local_mp3_dir, drive_folder_id):
        super().__init__()
        self.local_mp3_dir = local_mp3_dir
        self.drive_folder_id = drive_folder_id

    def run(self):
        gauth = GoogleAuth()
        gauth.LoadCredentialsFile("mycreds.txt")

        if gauth.credentials is None:
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            gauth.Refresh()
        else:
            gauth.Authorize()

        gauth.SaveCredentialsFile("mycreds.txt")
        self.drive = GoogleDrive(gauth)

        file_list = self.drive.ListFile({'q': f"'{self.drive_folder_id}' in parents and trashed=false"}).GetList()
        existing_files = {file['title']: file['id'] for file in file_list}

        mp3_files = [f for f in os.listdir(self.local_mp3_dir) if f.endswith('.mp3')]

        max_threads = 5
        with ThreadPoolExecutor(max_threads) as executor:
            future_to_file = {executor.submit(self.upload_file, file, existing_files): file for file in mp3_files}
            for count, future in enumerate(as_completed(future_to_file), 1):
                future.result()
                self.progress_signal.emit(count)

    def upload_file(self, file, existing_files):
        try:
            if file not in existing_files:
                file_path = os.path.join(self.local_mp3_dir, file)
                drive_file = self.drive.CreateFile({'title': file, 'parents': [{'id': self.drive_folder_id}]})
                drive_file.SetContentFile(file_path)
                drive_file.Upload()
        except Exception as e:
            print(f'Failed to upload {file}: {str(e)}')

class VideoPlayerWorker(QThread):
    position_changed = Signal(int)
    duration_changed = Signal(int)
    MediaStatusChanged = Signal(int)

    def __init__(self, video_widget,ifvideo, volume=1.0):
        super().__init__()
        self.current_new_speed = 1.0
        self.current_speed = 1.0
        self.video_widget = video_widget
        self.video_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.video_player.setAudioOutput(self.audio_output)
        if ifvideo == "True":
            self.video_player.setVideoOutput(self.video_widget)
        self.audio_output.setVolume(volume)
        
        if volume != 0.0 :
            self.is_muted = False
        else :
            self.is_muted = True


        self.video_player.positionChanged.connect(self.position_changed.emit)
        self.video_player.durationChanged.connect(self.duration_changed.emit)
        self.video_player.mediaStatusChanged.connect(self.MediaStatusChanged.emit)

    def set_source(self, video_path):
        self.video_player.setSource(video_path)

    def run(self):
        self.video_player.play()

    def pause(self):
        if self.video_player.playbackState() == QMediaPlayer.PlayingState:
            self.video_player.pause()
        else:
            self.video_player.play()

    def toggle_mute(self):
        if self.is_muted:
            self.audio_output.setVolume(1)
        else:
            self.audio_output.setVolume(0)
        self.is_muted = not self.is_muted

    def stop(self):
        self.video_player.stop()
        self.quit()
        self.wait()

    def set_Position(self, position):
        self.video_player.setPosition(position)


    def is_playing(self):
        return self.video_player.playbackState() == QMediaPlayer.PlayingState

    def setspeed(self,speed):
        self.video_player.setPlaybackRate(speed)
        self.set_speed_again(True)


    def position(self):
        return self.video_player.position()
    
    def set_current_speed(self, speed):
        self.current_new_speed = speed
        self.set_speed_again()
    
    def set_speed_again(self,isplayspeed = False):
        speed = self.video_player.playbackRate()
        orignal_speed = speed/self.current_speed if not isplayspeed else speed
        newspeed = orignal_speed*self.current_new_speed
        self.video_player.setPlaybackRate(newspeed)
        self.current_speed = self.current_new_speed



class MyGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.video_item = QGraphicsVideoItem()
        self.scene.addItem(self.video_item)

        
        self.setMinimumSize(600, 337.5)
        self.video_item.setSize(self.size())

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        transform = QTransform()
        transform.scale(0.96, 0.96)
        self.video_item.setTransform(transform)

    def set_video_output(self, player):
        player.setVideoOutput(self.video_item)


    def resizeEvent(self, event):
        self.setFixedHeight(self.width()/100 * 56.25)
        self.video_item.setSize(self.size())
        super().resizeEvent(event)

class FilePopup(QDialog):
    def __init__(self, files, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Select Files')
        self.setLayout(QVBoxLayout())
        self.file_list = QListWidget()
        self.checkboxes = []
        self.ischecked = False
        
        for file in files:
            item = QListWidgetItem(file)
            self.file_list.addItem(item)
            checkbox = QCheckBox(file)
            item.setCheckState(checkbox.checkState())
            self.checkboxes.append(checkbox)
            self.layout().addWidget(checkbox)
        
        # Add buttons: Select All, Cancel, Done
        button_box = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout().addWidget(button_box)
        
        # Add "Select All" Button
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        self.layout().addWidget(select_all_btn)
        
    def select_all(self):
        for checkbox in self.checkboxes:
            if self.ischecked:
                checkbox.setChecked(False)
            else:
                checkbox.setChecked(True)
        self.ischecked = False if self.ischecked else True

    def get_selected_files(self):
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]

class UploadsrtThread(QThread):
    progress_signal = Signal(int)

    def __init__(self, files, local_dir, folder_id):
        super().__init__()
        self.files = files
        self.local_dir = local_dir
        self.folder_id = folder_id
        self.drive = None 

    def run(self):
        # Authenticate and initialize the GoogleDrive object
        self.drive = self.authenticate_drive()

        existing_files = {file['title']: file['id'] for file in self.drive.ListFile({'q': f"'{self.folder_id}' in parents and trashed=false"}).GetList()}

        max_threads = 5
        with ThreadPoolExecutor(max_threads) as executor:
            future_to_file = {executor.submit(self.upload_file, file, existing_files): file for file in self.files}
            for count, future in enumerate(as_completed(future_to_file), 1):
                future.result()  
                self.progress_signal.emit(count)

    def upload_file(self, file, existing_files):
        try:
            if file in existing_files:
                drive_file = self.drive.CreateFile({'id': existing_files[file]})
            else:
                drive_file = self.drive.CreateFile({'title': file, 'parents': [{'id': self.folder_id}]})
            file_path = os.path.join(self.local_dir, file)
            drive_file.SetContentFile(file_path)
            drive_file.Upload()
        except Exception as e:
            print(f'Failed to upload {file}: {str(e)}')

    def authenticate_drive(self):
        gauth = GoogleAuth()
        gauth.LoadCredentialsFile("mycreds.txt")
        if gauth.credentials is None:
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            gauth.Refresh()
        else:
            gauth.Authorize()
        gauth.SaveCredentialsFile("mycreds.txt")
        return GoogleDrive(gauth)

class DownloadsrtThread(QThread):
    progress_signal = Signal(int)

    def __init__(self, file_list, local_json_dir, folder_id): 
        super().__init__()
        self.file_list = file_list
        self.local_json_dir = local_json_dir
        self.folder_id = folder_id  
        self.drive = self.authenticate_drive()  

    def run(self):
        os.makedirs(self.local_json_dir, exist_ok=True)
        max_threads = 5
        with ThreadPoolExecutor(max_threads) as executor:
            future_to_file = {executor.submit(self.download_file, file): file for file in self.file_list}
            for count, future in enumerate(as_completed(future_to_file), 1):
                future.result()
                self.progress_signal.emit(count)


    def download_file(self, file):
        try:
            file_path = os.path.join(self.local_json_dir, file['title'])  
            if not os.path.exists(file_path): 
                drive_file = self.drive.CreateFile({'id': file['id']}) 
                drive_file.GetContentFile(file_path) 
        except Exception as e:
            print(f'Failed to download {file["title"]}: {str(e)}')



    def authenticate_drive(self):
        gauth = GoogleAuth()
        gauth.LoadCredentialsFile("mycreds.txt")
        if gauth.credentials is None:
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            gauth.Refresh()
        else:
            gauth.Authorize()
        gauth.SaveCredentialsFile("mycreds.txt")
        return GoogleDrive(gauth)


class DeletesrtThread(QThread):
    progress_signal = Signal(int)

    def __init__(self, file_list, local_json_dir, folder_id):  
        super().__init__()
        self.file_list = file_list
        self.local_json_dir = local_json_dir
        self.folder_id = folder_id
        self.drive = self.authenticate_drive()  

    def run(self):
        os.makedirs(self.local_json_dir, exist_ok=True)
        max_threads = 5
        with ThreadPoolExecutor(max_threads) as executor:
            future_to_file = {executor.submit(self.download_file, file): file for file in self.file_list}
            for count, future in enumerate(as_completed(future_to_file), 1):
                future.result()
                self.progress_signal.emit(count)


    def download_file(self, file):
        try:
            drive_file = self.drive.CreateFile({'id': file['id']})  
            drive_file.Delete()  
        except Exception as e:
            print(f'Failed to Delete {file["title"]}: {str(e)}')



    def authenticate_drive(self):
        gauth = GoogleAuth()
        gauth.LoadCredentialsFile("mycreds.txt")
        if gauth.credentials is None:
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            gauth.Refresh()
        else:
            gauth.Authorize()
        gauth.SaveCredentialsFile("mycreds.txt")
        return GoogleDrive(gauth)


class SRTAnalyzer(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.is_muted = False
        self.current_subtitle = None
        self.current_position = 0.0
        self.total_duration = 0.0
        self.play_buttontext = False
        self.isedited = False
        self.active_index = 0
        self.srtduration = []
        self.pixels_per_second = 100
        self.draggingPlayhead = False
        self.audioprogresscount = 0
        self.output_file_path = ''
        silence_audio = AudioSegment.silent(0)
        silence_audio = silence_audio.set_frame_rate(44100)
        self.combined_audio = silence_audio
        self.subtitle_frames = []
        self.audio_length = []
        self.changpron = []
        self.currentprogress = 0
        self.totaldata = 0
        self.isvideoloaded = False
        self.combined_audio_duration = 0
        self.hinditimestamps = []
        self.englishtimestamps = []
        self.undolist = []
        self.isreload = False
        self.isvideoloaded = False
        self.ispronenabled = []


        


    def silent_ffmpeg(self, command):
        subprocess.run(command, creationflags=subprocess.CREATE_NO_WINDOW)

    def load_audio_silently(self, audio_file_path):
        command = [
            "ffmpeg",
            "-i", audio_file_path,
            "-f", "wav",
            "-vn",  # No video
            "pipe:1"  # Output to pipe
        ]
        
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        audio = AudioSegment.from_file(io.BytesIO(result.stdout), format="wav")
        return audio

    def export_audio_silently(self, audio, output_file_path):
        temp_wav_path = "temp_output.wav"
        
        audio.export(temp_wav_path, format="wav")
        
        command = [
            "ffmpeg",
            "-i", temp_wav_path,
            "-ar", "44100",  # Set the sample rate
            "-ac", "2",      # Stereo audio
            "-vn",  # No video
            "-y",  # Overwrite output files
            output_file_path
        ]
        
        subprocess.run(command, creationflags=subprocess.CREATE_NO_WINDOW)

        os.remove(temp_wav_path)

    def load_data(self,directory):
        X = []
        y = []
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                with open(os.path.join(directory, filename), 'r') as f:
                    data = json.load(f)
                    X.append([data['words'], data['characters']])
                    y.append(data['duration'])
        return np.array(X), np.array(y)

    def train_duration_model(self,X, y):
        model = LinearRegression()
        model.fit(X, y)
        return model

    def train_reverse_model(self,X, y):
        reverse_model = LinearRegression()
        reverse_model.fit(y.reshape(-1, 1), X)
        return reverse_model

    

    def save_model(self,model, filename='model.joblib'):
        dump(model, filename)


    def load_model(self,filename):
        return load(filename)
    
    


    def initUI(self):
        self.setWindowTitle("SRT Analyzer")
        self.setGeometry(100, 100, 1400, 800)

        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #f0f0f0;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QTextEdit {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                padding: 8px;
                border-radius: 5px;
                color: #f0f0f0;
            }
            QLineEdit {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                padding: 8px;
                border-radius: 2px;
                color: #f0f0f0;
                text-align:center;
            }
            QLabel {
                border-radius: 2px;
                padding: 10px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #555555;
                height: 10px;
                background: #3c3c3c;
                border-radius: 5px;
            }
            QSlider::handle:horizontal {
                background: #f0f0f0;
                border: 1px solid #555555;
                width: 20px;
                margin: -5px 0;
                border-radius: 10px;
            }
            QScrollArea {
                border: none;
            }
            QScrollBar:vertical {
                background-color: #3c3c3c;
                width: 14px;
                margin: 15px 3px 15px 3px;
                border-radius: 7px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                min-height: 20px;
                border-radius: 7px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: none;
                height: 15px;
                subcontrol-origin: margin;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
          
            QScrollBar:horizontal {
                background-color: #3c3c3c;
                height: 14px;
                margin: 3px 15px 3px 15px;
                border-radius: 7px;
            }
            QScrollBar::handle:horizontal {
                background-color: #555555;
                min-width: 20px;
                border-radius: 7px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                background: none;
                width: 15px;
                subcontrol-origin: margin;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
            QFrame {
                background-color: #3c3c3c;
                border-radius: 10px;
                margin: 5px;
                padding: 5px;
            }
             QProgressBar {
                border-radius: 5px; 
                text-align: right;  
                color: #ffffff;  
            }
        """)

        self.main_layout = QHBoxLayout(self)

        self.left_layout = QVBoxLayout()

        self.loadbuttonlayout = QHBoxLayout()

        self.loadsavedButton = QPushButton("Load Saved SRT")
        self.loadsavedButton.clicked.connect(lambda : self.load_srt(True))
        self.loadbuttonlayout.addWidget(self.loadsavedButton)

        self.loadButton = QPushButton("Load New SRT")
        self.loadButton.clicked.connect(lambda: self.load_srt())
        self.loadbuttonlayout.addWidget(self.loadButton)

        self.left_layout.addLayout(self.loadbuttonlayout)

        # self.ffall= QPushButton("Fast/Slow All")
        # self.left_layout.addWidget(self.ffall)

        self.srtactionbuttons = QHBoxLayout()

        self.updateButton = QPushButton("Save")
        self.updateButton.clicked.connect(self.update_srt)
        self.srtactionbuttons.addWidget(self.updateButton)

        self.SaveButton = QPushButton("Save as")
        self.SaveButton.clicked.connect(self.save_subtitles_as)
        self.srtactionbuttons.addWidget(self.SaveButton)

        self.left_layout.addLayout(self.srtactionbuttons)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)

        self.scroll_area.setWidget(self.scroll_content)
        self.scroll_area.setFixedWidth(500)
        self.left_layout.addWidget(self.scroll_area)
        
        self.need_update = QHBoxLayout()
        self.statusLabel = QLabel("")
        self.need_update.addWidget(self.statusLabel)

        self.left_layout.addLayout(self.need_update)

        self.audiolayout = QHBoxLayout()

        self.generateAudioButton = QPushButton("Generate Audio for All Subtitles")
        self.audiolayout.addWidget(self.generateAudioButton)

        self.convert = QPushButton("Combine Audio")
        self.audiolayout.addWidget(self.convert)
        
        self.left_layout.addLayout(self.audiolayout)

        self.main_layout.addLayout(self.left_layout)

        # Right-side layout for video player
        
        self.video_layout = QVBoxLayout()

        self.loadVideoButton = QPushButton("Load Video")
        self.loadVideoButton.clicked.connect(self.load_video)
        self.video_layout.addWidget(self.loadVideoButton)

        # Mute/Unmute Button

        self.video_area_frame = QFrame(self)
        self.video_area = QFrame(self.video_area_frame)
        self.video_area_frame.setMinimumSize(600, 337.5)
        self.video_area.setMinimumSize(600, 337.5)        

        self.graphics_view = MyGraphicsView(self.video_area)
        self.graphics_view.setMinimumSize(600, 337.5)
        
        self.subtitle_lable = QLabel(self.video_area_frame)
        self.subtitle_lable.setMinimumSize(525, 63.75)
        self.subtitle_lable.setText('')
        self.subtitle_lable.setStyleSheet("font-size: 18px; padding: 0px; margin : 0px; background-color: rgba(0, 0, 0, 100);")
        self.subtitle_lable.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        self.subtitle_lable.setWordWrap(True)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(1)  # Blur amount
        shadow.setOffset(2, 2)    # Shadow offset
        shadow.setColor(QColor(0, 0, 0, 255))  # Shadow color (semi-transparent black)

        self.subtitle_lable.setGraphicsEffect(shadow)        
        
        self.video_layout.addWidget(self.video_area_frame)
        #self.videoWidget.setVisible(False)

        self.video_player_thread1 = self.setup_video_player(self.graphics_view.video_item ,"True")
        self.video_player_thread2 = self.setup_video_player(self.graphics_view.video_item ,"False")
        self.video_player_thread3 = self.setup_video_player(self.graphics_view.video_item ,"False", volume=0.0)

        self.sidler_container = QHBoxLayout()

        # Video control button
        self.play_icon = self.style().standardIcon(QStyle.SP_MediaPlay)
        self.pause_icon = self.style().standardIcon(QStyle.SP_MediaPause)
        self.play_pause_button = QPushButton()
        self.play_pause_button.setIcon(self.play_icon)
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.sidler_container.addWidget(self.play_pause_button)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)

        self.timestamp = QLabel('00:00:000 / 00:00:000')
        self.timestamp.setFixedSize(140, 40)

        self.mute_button = QPushButton("🎙️")
        self.mute_button.clicked.connect(self.toggle_mute)

        self.greaterslowmo = QPushButton("<")
        self.greaterslowmo.setStyleSheet("QPushButton { font-size: 12x; padding: 1px; margin : 0px; color: grey; border-radius : 2px; } QPushButton:hover {background-color: #4a4a4a;}")

        self.slowmo = QPushButton("<")
        self.slowmo.setStyleSheet("QPushButton { font-size: 12x; padding: 1px; margin : 0px; color: grey;border-radius : 2px; } QPushButton:hover {background-color: #4a4a4a;}")
    
        self.speedlable = QLineEdit("1.0")
        self.speedlable.setAlignment(Qt.AlignCenter)
        self.speedlable.setFixedSize(20, 20)
        self.speedlable.setStyleSheet("QLineEdit {font-size: 12px; padding: -1px; margin : 0px;color: grey; background-color: #2b2b2b; text-align: center; }" )
        self.speedlable.update()
        self.ff = QPushButton(">")
        self.ff.setStyleSheet("QPushButton { font-size: 12x; padding: 1px; margin : 0px; color: grey; border-radius : 2px;} QPushButton:hover {background-color: #4a4a4a;}")

        self.greaterff = QPushButton(">")
        self.greaterff.setStyleSheet("QPushButton { font-size: 12x; padding: 1px; margin : 0px; color: grey; border-radius : 2px;} QPushButton:hover {background-color: #4a4a4a;}")      
        
        self.speedlable.editingFinished.connect(lambda : self.change_speed(0,self.speedlable))
        self.greaterslowmo.clicked.connect(lambda: self.change_speed(-0.5,self.speedlable))
        self.slowmo.clicked.connect(lambda: self.change_speed(-0.1,self.speedlable))
        self.ff.clicked.connect(lambda: self.change_speed(0.1,self.speedlable))
        self.greaterff.clicked.connect(lambda: self.change_speed(0.5,self.speedlable))
        self.sidler_container.addWidget(self.slider)
        self.sidler_container.addWidget(self.timestamp)
        self.sidler_container.addWidget(self.mute_button)
        self.sidler_container.addWidget(self.greaterslowmo)
        self.sidler_container.addWidget(self.slowmo)
        self.sidler_container.addWidget(self.speedlable)
        self.sidler_container.addWidget(self.ff)
        self.sidler_container.addWidget(self.greaterff)

        
        self.video_layout.addLayout(self.sidler_container)

        self.video_player_thread1.position_changed.connect(self.position_changed)
        self.video_player_thread1.duration_changed.connect(self.duration_changed)
        self.video_player_thread1.position_changed.connect(self.sync_subtitles)
        self.video_player_thread1.position_changed.connect(self.sync_time)
        
        # Timeline Display

        self.timelinescrollArea = QScrollArea()
        self.timelinescrollArea.setWidgetResizable(True)
        self.timelinescrollArea.setMinimumSize(600 , 112.5)
        self.timelinescrollAreaLayout = QVBoxLayout()
      
        self.timelinescrollAreaWidget = QWidget()
        self.timelinescrollAreaWidget.setLayout(self.timelinescrollAreaLayout)
        self.timelinescrollArea.setWidget(self.timelinescrollAreaWidget)

        self.timelinelayout = QVBoxLayout()
        self.timelinelayout.setSpacing(0)  # Ensure no space between subtitle boxes
        self.timelinelayout.setContentsMargins(0, 0, 0, 0)
        
        self.timeline = QHBoxLayout()
        #self.timeline.setStyleSheet("background-color: #2b2b2b;")
        self.timeline.setSpacing(0)  # Ensure no space between subtitle boxes
        self.timeline.setContentsMargins(0, 0, 0, 0)
        self.timelinelayout.addLayout(self.timeline)

        # Playhead
        self.playhead = QLabel(self.timelinescrollAreaWidget)
        self.playhead.setStyleSheet("background-color: red;")
        self.playhead.setGeometry(QRect(0, 0, 2, 250))
        self.playheadTimer = QTimer()
        self.playheadTimer.timeout.connect(self.updatePlayhead)
        self.playhead.raise_()

        # Lower Subtitle Boxes
        self.subtitleLayout = QHBoxLayout()
        self.subtitleLayout.setSpacing(0)  # Ensure no space between subtitle boxes
        self.subtitleLayout.setContentsMargins(0, 0, 0, 0)  # Ensure no margins
        self.timelinelayout.addLayout(self.subtitleLayout)
        self.timelinescrollAreaLayout.addLayout(self.timelinelayout)
        self.timelinescrollAreaLayout.setContentsMargins(0, 0, 0, 0)

        self.video_layout.addWidget(self.timelinescrollArea)

        self.videooptions = QHBoxLayout()
        
        self.generatesubs = QPushButton("Generate Subtitle")
        self.generatesubs.clicked.connect(self.generate_subtitle)
        self.videooptions.addWidget(self.generatesubs)

        self.exportvideo = QPushButton("Export")
        self.exportvideo.clicked.connect(self.export_video)
        self.videooptions.addWidget(self.exportvideo)        
        
        self.video_layout.addLayout(self.videooptions)

        self.video_layout.setAlignment(Qt.AlignTop)

        self.main_layout.addLayout(self.video_layout)

        self.right_layout = QVBoxLayout()
        self.right_layout_widget = QWidget()
        self.right_layout_widget.setLayout(self.right_layout)
        self.right_layout_scroll_area = QScrollArea()
        self.right_layout_scroll_area.setWidgetResizable(True)
        self.right_layout_scroll_area.setFixedWidth(320)
        self.right_layout_scroll_area.setWidget(self.right_layout_widget)
        self.right_layout_scroll_area.setContentsMargins(0, 0, 0, 0)  # Ensure no margins
        self.right_layout_scroll_area.setStyleSheet("QScrollArea { padding: 0px; margin: 0px; font-size: 12px;}")  # Remove padding and margin from label
        
        self.topheading = QLabel("SETTINGS")
        self.topheading.setAlignment(Qt.AlignCenter)
        self.topheading.setFixedHeight(50)
        self.topheading.setStyleSheet("background-color: #2b2b2b; font-size: 17px; font-family: bold;")
        self.right_layout.addWidget(self.topheading)

        Gray_area = QFrame()
        Gray_area.setFixedWidth(280)
        self.changeintrolayout = QVBoxLayout(Gray_area)

        headinglayout = QHBoxLayout()

        self.chnageintrocheck = QCheckBox()
        self.chnageintrocheck.setFixedSize(16,16)
        headinglayout.addWidget(self.chnageintrocheck)
        self.changeintro = QLabel("Change Intro")
        self.changeintro.setAlignment(Qt.AlignCenter)
        self.changeintro.setStyleSheet(" font-size: 15px")
        headinglayout.addWidget(self.changeintro)
        headinglayout.setAlignment(Qt.AlignCenter)
        self.changeintrolayout.addLayout(headinglayout)

        lablelayout = QHBoxLayout()
        lablelayout.addWidget(QLabel("Start Time     "))
        lablelayout.addWidget(QLabel("   End Time"))
        self.changeintrolayout.addLayout(lablelayout)
        lablelayout.setAlignment(Qt.AlignCenter)

        timestamp_container = QHBoxLayout()
        self.leftcropbutton = QPushButton("{")
        self.rightcropbutton = QPushButton("}")
        self.timestamp_start_label = QLineEdit("00:00:00,000")
        self.timestamp_start_label.setReadOnly(True)
        timestamp_diveder_label = QLabel(" :")
        self.timestamp_end_label = QLineEdit("00:00:00,000")
        self.timestamp_end_label.setReadOnly(True)
        self.timestamp_start_label.setStyleSheet("font-size: 12px; padding: 1px; margin : 0px;color: grey; background-color: #2b2b2b; text-align: center;" )
        timestamp_diveder_label.setStyleSheet("font-size: 12x; padding: 1px; margin : 0px;" )
        self.timestamp_end_label.setStyleSheet("font-size: 12px; padding: 1px; margin : 0px;color: grey; background-color: #2b2b2b; text-align: center;" )
        self.leftcropbutton.setStyleSheet("QPushButton { font-size: 12x; padding: 1px; margin : 0px; color: grey; padding-bottom :3px} QPushButton:hover {background-color: #4a4a4a;}")
        self.rightcropbutton.setStyleSheet("QPushButton { font-size: 12x; padding: 1px; margin : 0px; color: grey; padding-bottom :3px} QPushButton:hover {background-color: #4a4a4a;}")

        self.leftcropbutton.clicked.connect(lambda: self.settime(self.timestamp_end_label,self.timestamp_start_label))
        self.rightcropbutton.clicked.connect(lambda: self.settime(self.timestamp_end_label,self.timestamp_start_label,True))

        self.timestamp_start_label.setFixedWidth(75)
        self.timestamp_end_label.setFixedWidth(75)

        self.timestamp_start_label.setAlignment(Qt.AlignCenter)
        self.timestamp_end_label.setAlignment(Qt.AlignCenter)

        timestamp_container.addWidget(self.leftcropbutton)
        timestamp_container.addWidget(self.timestamp_start_label)
        timestamp_container.addWidget(timestamp_diveder_label)
        timestamp_container.addWidget(self.timestamp_end_label)
        timestamp_container.addWidget(self.rightcropbutton)
        timestamp_container.setAlignment(Qt.AlignCenter)

        self.changeintrolayout.addLayout(timestamp_container)

        self.right_layout.addWidget(Gray_area)
        
        Gray_area = QFrame()
        Gray_area.setFixedWidth(280)

        self.word_pron_area = QVBoxLayout(Gray_area)

        # Words and Pronunciations Section
        self.words_pron_label = QLabel("Words and Pronunciations")
        self.word_pron_area.addWidget(self.words_pron_label)

        # Scrollable list for Words and Pronunciations
        self.scroll_area_wordpron = QScrollArea()
        self.scroll_area_wordpron.setWidgetResizable(True)
        self.scroll_area_wordpron.setContentsMargins(0,0,0,0)
        self.scroll_area_wordpron.setStyleSheet("padding : 0px; margin : 0px;")
        self.scroll_area_wordpron.setFixedHeight(150)
        self.words_layout = QVBoxLayout()

        # Add row for adding new word and pronunciation
        add_row = QHBoxLayout()
        self.new_word_edit = QLineEdit()
        self.new_word_edit.setPlaceholderText("Enter new word")
        self.new_pron_edit = QLineEdit()
        self.new_pron_edit.setPlaceholderText("Enter pronunciation")

        self.pron_buttons_layout = QVBoxLayout()

        self.pron_options = QComboBox(self)
        self.pron_options.addItem("IPA")
        self.pron_options.addItem("Arpabet")
        self.pron_options.setStyleSheet('border-radius : 1px;')

        font = QFont()
        font.setPointSize(5) 
        self.pron_options.setFont(font)

        # Connect the dropdown menu to a method
        #self.pron_options.currentIndexChanged.connect(self.pron_format)

        self.pron_buttons_layout.addWidget(self.pron_options)

        self.add_word_button = QPushButton("Add")
        self.add_word_button.clicked.connect(self.add_word_pron)
        self.add_word_button.setFixedSize(60,12)
        self.add_word_button.setStyleSheet('font-size : 7px ; border-radius : 1px;')

        self.pron_buttons_layout.addWidget(self.add_word_button)
        
        add_row.addWidget(self.new_word_edit)
        add_row.addWidget(self.new_pron_edit)
        add_row.addLayout(self.pron_buttons_layout)
        
        self.word_pron_area.addLayout(add_row)

        # Existing Words and Pronunciations (will be loaded from sheet)
        self.words_widget = QWidget()
        self.words_widget.setLayout(self.words_layout)
        self.scroll_area_wordpron.setWidget(self.words_widget)
        self.word_pron_area.addWidget(self.scroll_area_wordpron)

        self.right_layout.addWidget(Gray_area)

        Gray_area = QFrame()
        Gray_area.setFixedWidth(280)

        self.commands_gray_layout = QVBoxLayout(Gray_area)

        # Commands Section
        self.commands_label = QLabel("Commands")
        self.commands_gray_layout.addWidget(self.commands_label)

        # Add row for adding new command
        add_command_row = QHBoxLayout()
        self.new_command_edit = QTextEdit()
        self.new_command_edit.setPlaceholderText("Enter new command")
        self.new_command_edit.setMaximumHeight(100)
        self.add_command_button = QPushButton("Add")
        self.add_command_button.clicked.connect(self.add_command)
        
        add_command_row.addWidget(self.new_command_edit)
        add_command_row.addWidget(self.add_command_button)
        
        self.commands_gray_layout.addLayout(add_command_row)

        # Scrollable list for commands
        self.commands_layout = QVBoxLayout()
        self.commands_widget = QWidget()
        self.commands_widget.setLayout(self.commands_layout)
        self.commands_scroll_area = QScrollArea()
        self.commands_scroll_area.setWidgetResizable(True)
        self.commands_scroll_area.setWidget(self.commands_widget)
        self.commands_scroll_area.setFixedHeight(150)
        self.commands_gray_layout.addWidget(self.commands_scroll_area)

        self.right_layout.addWidget(Gray_area)


        Gray_area = QFrame()
        Gray_area.setFixedWidth(280)

        self.trainmodel = QVBoxLayout(Gray_area)
        
        self.ModelTraining = QLabel("MODEL TRAINING")
        self.ModelTraining.setAlignment(Qt.AlignCenter)
        self.ModelTraining.setStyleSheet(" font-size: 15px")
        self.trainmodel.addWidget(self.ModelTraining)

        self.Trainingstatus = QLabel("For Duration,Charcters,Words Prediction")
        self.Trainingstatus.setWordWrap(True)
        self.Trainingstatus.setAlignment(Qt.AlignCenter)
        self.trainmodel.addWidget(self.Trainingstatus)

        self.progress_bar = QProgressBar(self)
        self.trainmodel.addWidget(self.progress_bar)
        
        self.uploadjsons = QPushButton("Upload Jsons")
        self.uploadjsons.clicked.connect(self.start_upload)
        self.trainmodel.addWidget(self.uploadjsons)
        
        self.downloadjsons = QPushButton("Download Jsons")
        self.downloadjsons.clicked.connect(self.start_download)
        self.trainmodel.addWidget(self.downloadjsons)
        
        self.trainbutton = QPushButton("Train New Model")
        self.trainbutton.clicked.connect(self.train_model)
        self.trainmodel.addWidget(self.trainbutton)
        self.trainmodel.setAlignment(Qt.AlignTop)

        self.right_layout.addWidget(Gray_area)
        
        Gray_area = QFrame()
        Gray_area.setFixedWidth(280)
        self.mp3drive = QVBoxLayout(Gray_area)
        
        self.mp3lable = QLabel("Mp3 Drive Options")
        self.mp3lable.setAlignment(Qt.AlignCenter)
        self.mp3lable.setStyleSheet(" font-size: 15px")
        self.mp3drive.addWidget(self.mp3lable)

        self.mp3_progress_bar = QProgressBar(self)
        self.mp3drive.addWidget(self.mp3_progress_bar)
        
        self.uploadmp3 = QPushButton("Upload MP3")
        self.uploadmp3.clicked.connect(self.start_upload_mp3)
        self.mp3drive.addWidget(self.uploadmp3)
        
        self.downloadmp3 = QPushButton("Download MP3")
        self.downloadmp3.clicked.connect(self.start_download_mp3)
        self.mp3drive.addWidget(self.downloadmp3)

        self.right_layout.addWidget(Gray_area)

        
        Gray_area = QFrame()
        Gray_area.setFixedWidth(280)
        self.currentsrtdrive = QVBoxLayout(Gray_area)
        
        self.currentsrtlable = QLabel("Current Srt Drive Options")
        self.currentsrtlable.setAlignment(Qt.AlignCenter)
        self.currentsrtlable.setStyleSheet(" font-size: 15px")
        self.currentsrtdrive.addWidget(self.currentsrtlable)

        self.cur_progress_bar = QProgressBar(self)
        self.currentsrtdrive.addWidget(self.cur_progress_bar)
        
        self.uploadsrt = QPushButton("Upload Srt")
        self.uploadsrt.clicked.connect(self.open_upload_dialog)
        self.currentsrtdrive.addWidget(self.uploadsrt)
        
        self.downloadsrt = QPushButton("Download Srt")
        self.downloadsrt.clicked.connect(self.open_download_dialog)
        self.currentsrtdrive.addWidget(self.downloadsrt)

        self.deletesrt = QPushButton("Delete Srt")
        self.deletesrt.clicked.connect(self.open_delete_dialog)
        self.currentsrtdrive.addWidget(self.deletesrt)

        self.right_layout.addWidget(Gray_area)

        Gray_area = QFrame()
        Gray_area.setFixedWidth(280)

        self.keys_area = QVBoxLayout(Gray_area)
        
        self.elevenlabs_key_label = QLabel("Elevenlabs Key: ")
        self.elevenlabs_key_edit = QLineEdit()
        self.elevenlabs_key_edit.editingFinished.connect(lambda : self.keyedited(self.elevenlabs_key_edit,'elevenlabs_key'))
        self.keys_area.addWidget(self.elevenlabs_key_label)
        self.keys_area.addWidget(self.elevenlabs_key_edit)

        self.chatgpt_key_label = QLabel("ChatGPT Key: ")
        self.chatgpt_key_edit = QLineEdit()
        self.chatgpt_key_edit.editingFinished.connect(lambda : self.keyedited(self.chatgpt_key_edit,'chatgpt_key'))
        self.keys_area.addWidget(self.chatgpt_key_label)
        self.keys_area.addWidget(self.chatgpt_key_edit)
        
        # Voice ID and Assistant ID Section
        self.voice_id_label = QLabel("Voice ID: ")
        self.voice_id_edit = QLineEdit()
        self.voice_id_edit.editingFinished.connect(lambda : self.keyedited(self.voice_id_edit,'voice_id'))
        self.keys_area.addWidget(self.voice_id_label)
        self.keys_area.addWidget(self.voice_id_edit)

        self.assistant_id_label = QLabel("Assistant ID: ")
        self.assistant_id_edit = QLineEdit()
        self.assistant_id_edit.editingFinished.connect(lambda : self.keyedited(self.assistant_id_edit,'assistant_id'))
        self.keys_area.addWidget(self.assistant_id_label)
        self.keys_area.addWidget(self.assistant_id_edit)

        gap_widget = QWidget()
        self.keys_area.addWidget(gap_widget)

        # Save Button
        self.save_button = QPushButton("Save Data")
        self.save_button.setFixedWidth(245)
        self.keys_area.addWidget(self.save_button)
        self.save_button.clicked.connect(self.save_data)

        self.right_layout.addWidget(Gray_area)


        self.right_layout.setAlignment(Qt.AlignTop)
        #self.right_layout.setAlignment(Qt.AlignCenter)
        
        # Add the right layout to the main layout (right side)
        self.main_layout.addWidget(self.right_layout_scroll_area)

        self.timelinescrollAreaWidget.mousePressEvent = self.jumpPlayhead

        undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_shortcut.activated.connect(self.undo_action)

        # Right Arrow key (Move to the next subtitle, for example)
        right_arrow_shortcut = QShortcut(QKeySequence(Qt.Key_Right), self)
        right_arrow_shortcut.activated.connect(self.moveright)

        # Left Arrow key (Move to the previous subtitle)
        left_arrow_shortcut = QShortcut(QKeySequence(Qt.Key_Left), self)
        left_arrow_shortcut.activated.connect(self.moveleft)

        space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        space_shortcut.activated.connect(self.toggle_play_pause)

        plus_shortcut = QShortcut(QKeySequence(Qt.Key_Plus), self)
        #plus_shortcut.activated.connect(self.zoom_in)

        # Minus key (-) for zooming out
        minus_shortcut = QShortcut(QKeySequence(Qt.Key_Minus), self)
        #minus_shortcut.activated.connect(self.zoom_out)
        self.WEB_APP_URL= '' #you app script web app url
        self.words_prons = []
        self.GPTcommands = []
        self.load_details()
        
    
    def settime(self,timestampend_lable,timestampstart_lable,isend=False):
        position = self.get_playhead_x_position()*10
        timestr = timestampstart_lable.text()
        hours, minutes, seconds = timestr.split(":")
        seconds, milliseconds = seconds.split(",")
        hours = int(hours)
        minutes = int(minutes)
        seconds = int(seconds)
        milliseconds = int(milliseconds)
        startmilliseconds = (hours * 3600 * 1000) + (minutes * 60 * 1000) + (seconds * 1000) + milliseconds

        timestr = timestampend_lable.text()
        hours, minutes, seconds = timestr.split(":")
        seconds, milliseconds = seconds.split(",")
        hours = int(hours)
        minutes = int(minutes)
        seconds = int(seconds)
        milliseconds = int(milliseconds)
        endmilliseconds = (hours * 3600 * 1000) + (minutes * 60 * 1000) + (seconds * 1000) + milliseconds

        if isend:
            if position > startmilliseconds:
                timestampend_lable.setText(self.format_time_h(position))
        else:
            if position < endmilliseconds:
                timestampstart_lable.setText(self.format_time_h(position))

    def keyedited(self,lable,lablename):
        text = lable.text()
        if lablename == 'elevenlabs_key':
            self.elevenlabs_key_edit.setText(text)
            self.full_elevenlabs_key = self.YOUR_XI_API_KEY = text 
            
        elif lablename == 'chatgpt_key':
            self.chatgpt_key_edit.setText(text)
            self.CHATGPT_APi = self.full_chatgpt_key = text

        elif lablename == 'voice_id':
            self.VOICE_ID = self.voice_id  = text
            self.voice_id_edit.setText(self.voice_id )

        elif lablename == 'assistant_id':
            self.VOICE_ID = self.voice_id  = text
            self.assistant_id_edit.setText(self.assistant_id)
        

    def add_word_pron(self):
            word = self.new_word_edit.text().strip()
            pronunciation = self.new_pron_edit.text().strip()
            format = self.pron_options.currentText()
            format = 'ipa' if format == 'IPA' else 'cmu-arpabet'
            if word and pronunciation and format:
                self.add_word_pron_row(word, pronunciation,format , add_to_top=True)
                self.new_word_edit.clear()
                self.new_pron_edit.clear()

                threading.Thread(target=self.post_data, args=({"action": "add", "type": "word_pron", "word": word, "pronunciation": pronunciation},)).start()

    def add_word_pron_row(self, word, pronunciation, format, add_to_top=False):
        row_widget = QWidget()
        row_widget.setContentsMargins(0,0,0,0)
        row_widget.setStyleSheet("padding : 0px; margin : 0px;")
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0,0,0,0)
        word_label = QLabel(word)
        word_label.setStyleSheet("border-radius:3px; padding :2px ; font-size: 10px;")
        pron_label = QLabel(pronunciation)
        pron_label.setStyleSheet("border-radius:3px; padding :2px ; font-size: 10px;")
        format_label = QLabel(format)
        format_label.setStyleSheet("border-radius:3px; padding :2px ; font-size: 10px;")
        
        action_button_layout = QVBoxLayout()
        ispronenabled = QCheckBox()
        ispronenabled.setChecked(True)
        ispronenabled.stateChanged.connect(lambda state : self.ispronenabledcheck(state,[word,pronunciation,format]))
        action_button_layout.addWidget(ispronenabled)
        delete_button = QPushButton("🗙")
        delete_button.setContentsMargins(0,0,0,0)
        delete_button.setFixedWidth(18)
        delete_button.setStyleSheet("border-radius: 1px; padding-bottom :3px ; margin:0px; font-size: 9px;")
        delete_button.clicked.connect(lambda: self.delete_word_pron(row_widget, word,pronunciation,format))
        action_button_layout.addWidget(delete_button)
        row_layout.addLayout(action_button_layout)
        row_layout.addWidget(word_label)
        row_layout.addWidget(pron_label)
        row_layout.addWidget(format_label)
        
        
        row_widget.setLayout(row_layout)
        self.words_prons.append([word,pronunciation,format])

        if add_to_top:
            self.words_layout.insertWidget(0, row_widget)  # Insert at the top of the list
        else:
            self.words_layout.addWidget(row_widget)
    
    def ispronenabledcheck(self,state,wordpron):
        if state != 2:
            index = self.words_prons.index(wordpron)
            self.words_prons.pop(index)
        else :
            self.words_prons.append(wordpron)

    def delete_word_pron(self, row_widget, word,pronunciation,format):
        self.words_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        self.words_prons.pop(self.words_prons.index([word,pronunciation,format]))
        # Remove from Google Sheet asynchronously
        threading.Thread(target=self.post_data, args=({"action": "delete", "type": "word_pron", "word": word},)).start()

    def add_command(self):
        command = self.new_command_edit.toPlainText().strip()
        if command:
            # Add new command to the UI (at the top of the list)
            self.add_command_row_ui(command, add_to_top=True)
            self.new_command_edit.clear()
            
            # Add to Google Sheet asynchronously
            threading.Thread(target=self.post_data, args=({"action": "add", "type": "command", "command": command},)).start()

    def add_command_row_ui(self, command, add_to_top=False):
        row_widget = QWidget()
        row_widget.setContentsMargins(0,0,0,0)
        row_widget.setStyleSheet("padding : 0px; margin : 0px;")
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0,0,0,0)
        command_label = QLabel(command)
        command_label.setStyleSheet("border-radius:3px; padding :2px ; font-size: 10px;")
        command_label.setWordWrap(True)
        delete_button = QPushButton("Delete")
        delete_button = QPushButton("🗙")
        delete_button.setContentsMargins(0,0,0,0)
        delete_button.setFixedWidth(18)
        delete_button.setStyleSheet("border-radius: 1px; padding-bottom :3px ; margin:0px; font-size: 9px;")
        delete_button.clicked.connect(lambda: self.delete_command(row_widget, command))

        row_layout.addWidget(command_label)
        row_layout.addWidget(delete_button)

        row_widget.setLayout(row_layout)
        
        self.GPTcommands.append(command)

        if add_to_top:
            self.commands_layout.insertWidget(0, row_widget)  # Insert at the top of the list
        else:
            self.commands_layout.addWidget(row_widget)

    def delete_command(self, row_widget, command):
        self.commands_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        self.GPTcommands.pop(self.GPTcommands.index(command))
        # Remove from Google Sheet asynchronously
        threading.Thread(target=self.post_data, args=({"action": "delete", "type": "command", "command": command},)).start()

    def load_details(self):
        try:
            response = requests.get(self.WEB_APP_URL)
            data = response.json()

            self.full_elevenlabs_key = data["APIs"]["Elevenlabs"]
            self.YOUR_XI_API_KEY = self.full_elevenlabs_key
            self.full_chatgpt_key = data["APIs"]["ChatGPT"]
            self.CHATGPT_APi = self.full_chatgpt_key
            self.elevenlabs_key_edit.setText(self.full_elevenlabs_key)
            self.chatgpt_key_edit.setText(self.full_chatgpt_key)

            self.voice_id = data["VoiceID"]
            self.VOICE_ID = self.voice_id 
            self.assistant_id = data["AssistantID"]
            self.Assistance_id = self.assistant_id
            self.voice_id_edit.setText(self.voice_id )
            self.assistant_id_edit.setText(self.assistant_id)

            for word, pronunciation,format in data["WordsPronunciations"]:
                if word and pronunciation and format:
                    self.add_word_pron_row(word, pronunciation,format)

            for command in data["Commands"]:
                if command:
                    self.add_command_row_ui(command)

        except Exception as e:
            print(f"Error loading data: {e}")
            QMessageBox.critical(self, "Error", "Failed to load data from the Google Sheet.")

    def save_data(self):
        updated_data = {
            "APIs": {
                "Elevenlabs": self.full_elevenlabs_key,  # Use full key, not truncated
                "ChatGPT": self.full_chatgpt_key         # Use full key, not truncated
            },
            "VoiceID": self.voice_id,
            "AssistantID": self.assistant_id,
            "WordsPronunciations": self.words_prons,
            "Commands" : self.GPTcommands
        }

        response = requests.post(self.WEB_APP_URL, json=updated_data)
        if response.status_code == 200:
            print("Data saved successfully.")
        else:
            print(f"Failed to save data. Status code: {response.status_code}")

    def post_data(self, data):
        data = {
                    "APIs": {
                        "Elevenlabs": self.full_elevenlabs_key,  # Use full key, not truncated
                        "ChatGPT": self.full_chatgpt_key         # Use full key, not truncated
                    },
                    "VoiceID": self.voice_id,
                    "AssistantID": self.assistant_id,
                    "WordsPronunciations": self.words_prons,
                    "Commands" : self.GPTcommands
                }
        try:
            response = requests.post(self.WEB_APP_URL, json=data)
            if response.status_code != 200:
                print(f"Failed to update Google Sheet. Status code: {response.status_code}")
        except Exception as e:
            print(f"Error posting data: {e}")

    def truncate_key(self, key):
        """ Truncate API key for display purposes """
        return f"{key[:5]}{'*' * (len(key) - 10)}{key[-5:]}" if len(key) > 15 else key

    def authenticate_drive(self):
        gauth = GoogleAuth()
        gauth.LoadCredentialsFile("mycreds.txt")
        if gauth.credentials is None:
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            gauth.Refresh()
        else:
            gauth.Authorize()
        gauth.SaveCredentialsFile("mycreds.txt")
        return GoogleDrive(gauth)
    

    def open_upload_dialog(self):
        local_dir = 'current_srt'
        srt_files = [f for f in os.listdir(local_dir) if f.endswith('.srt')]
        if not srt_files:
            QMessageBox.information(self, 'No Files', 'No SRT files found.')
            return

        popup = FilePopup(srt_files, self)
        if popup.exec_():
            selected_files = popup.get_selected_files()
            if selected_files:
                self.upload_srt_files(selected_files, local_dir)

    def open_download_dialog(self):
        folder_id = ''  # Your folder ID
        
        self.drive = self.authenticate_drive()
        # Fetch the file list from Google Drive
        file_list = self.drive.ListFile({'q': f"'{folder_id}' in parents and trashed=false"}).GetList()

        # Ensure file_list contains dictionaries with 'id' and 'title'
        files = [{'id': file['id'], 'title': file['title']} for file in file_list]

        if not files:
            QMessageBox.information(self, 'No Files', 'No SRT files found on Drive.')
            return
        filetitles = [ file['title'] for file in file_list]
        popup = FilePopup(filetitles, self)
        if popup.exec_():
            selected_files = popup.get_selected_files()
            filtered_files = [file for file in files if file['title'] in selected_files]
            if selected_files:
                self.download_srt_files(filtered_files)

    def open_delete_dialog(self):
        folder_id = ''  # Your folder ID
        
        self.drive = self.authenticate_drive()
        # Fetch the file list from Google Drive
        file_list = self.drive.ListFile({'q': f"'{folder_id}' in parents and trashed=false"}).GetList()

        # Ensure file_list contains dictionaries with 'id' and 'title'
        files = [{'id': file['id'], 'title': file['title']} for file in file_list]

        if not files:
            QMessageBox.information(self, 'No Files', 'No SRT files found on Drive.')
            return
        filetitles = [ file['title'] for file in file_list]
        popup = FilePopup(filetitles, self)
        if popup.exec_():
            selected_files = popup.get_selected_files()
            filtered_files = [file for file in files if file['title'] in selected_files]
            if selected_files:
                self.delete_srt_files(filtered_files)


    def upload_srt_files(self, files, local_dir):
        self.srttotlen = len(files)
        self.upload_thread = UploadsrtThread(files, local_dir, '# Your folder ID')
        self.upload_thread.progress_signal.connect(self.update_progress_srt)
        self.upload_thread.finished.connect(self.on_upload_complete_srt)
        self.upload_thread.start()

    def download_srt_files(self, files):
        self.srttotlen = len(files)
        self.download_thread = DownloadsrtThread(files,'current_srt','# Your folder ID')
        self.download_thread.progress_signal.connect(self.update_progress_srt)
        self.download_thread.finished.connect(self.on_download_complete_srt)
        self.download_thread.start()

    def delete_srt_files(self, files):
        self.srttotlen = len(files)
        self.delete_thread = DeletesrtThread(files,'current_srt','1')
        self.delete_thread.progress_signal.connect(self.update_progress_srt)
        self.delete_thread.finished.connect(self.on_delete_complete_srt)
        self.delete_thread.start()

    def update_progress_srt(self, value):
        value = value/self.srttotlen * 100
        self.cur_progress_bar.setValue(value)

    def on_upload_complete_srt(self):
        QMessageBox.information(self, 'Upload Complete', 'SRT files uploaded successfully.')

    def on_download_complete_srt(self):
        QMessageBox.information(self, 'Download Complete', 'SRT files downloaded successfully.')

    def on_delete_complete_srt(self):
        QMessageBox.information(self, 'Delete Complete', 'SRT files delete successfully.')

    @Slot(int)
    def update_progress(self, count):
        self.progress_bar.setValue(count)        
    
    def update_mp3_progress(self, count):
        self.mp3_progress_bar.setValue(count)  

    def resizeEvent(self, event):
        self.video_area.setFixedSize(self.video_area_frame.width(),self.video_area_frame.width()/100 * 56.25)
        self.video_area_frame.setFixedHeight(self.video_area_frame.width()/100 * 56.25)
        self.graphics_view.setFixedSize(self.video_area_frame.width(),self.video_area_frame.width()/100 * 56.25)
        self.subtitle_lable.setFixedSize(self.video_area_frame.width()/100*87.5,self.subtitle_lable.height())
        self.timelinescrollArea.setFixedHeight(self.timelinescrollArea.width()/100 * 18.75)
        self.subtitle_lable.move(self.video_area_frame.width()/16, self.video_area.height() - self.subtitle_lable.height() -self.video_area_frame.width()/16)

        super().resizeEvent(event)

    def start_download(self):
        # Authenticate and create PyDrive client
        gauth = GoogleAuth()
        gauth.LoadCredentialsFile("mycreds.txt")

        if gauth.credentials is None:
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            gauth.Refresh()
        else:
            gauth.Authorize()

        gauth.SaveCredentialsFile("mycreds.txt")
        drive = GoogleDrive(gauth)

        # Fetch file list
        folder_id = '# Your folder ID'
        file_list = drive.ListFile({'q': f"'{folder_id}' in parents and trashed=false"}).GetList()

        # Start download thread
        self.progress_bar.setMaximum(len(file_list))
        self.download_thread = DownloadThread(file_list, 'downloaded_jsons')
        self.download_thread.progress_signal.connect(self.update_progress)
        self.download_thread.finished.connect(self.on_download_complete)
        self.download_thread.start()

    def start_download_mp3(self):
        # Authenticate and create PyDrive client
        gauth = GoogleAuth()
        gauth.LoadCredentialsFile("mycreds.txt")

        if gauth.credentials is None:
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            gauth.Refresh()
        else:
            gauth.Authorize()

        gauth.SaveCredentialsFile("mycreds.txt")
        drive = GoogleDrive(gauth)

        # Fetch file list
        folder_id = '# Your folder ID'
        file_list = drive.ListFile({'q': f"'{folder_id}' in parents and trashed=false"}).GetList()

        # Start download thread
        self.mp3_progress_bar.setMaximum(len(file_list))
        self.download_thread = Downloadmp3Thread(file_list, 'generated_audio')
        self.download_thread.progress_signal.connect(self.update_mp3_progress)
        self.download_thread.start()

    def start_upload(self):
        local_json_dir = 'downloaded_jsons'
        drive_folder_id = '# Your folder ID'

        # Start upload thread
        json_files = [f for f in os.listdir(local_json_dir) if f.endswith('.json')]
        self.progress_bar.setMaximum(len(json_files))
        self.upload_thread = UploadThread(local_json_dir, drive_folder_id)
        self.upload_thread.progress_signal.connect(self.update_progress)
        self.upload_thread.finished.connect(self.on_upload_complete)
        self.upload_thread.start()

    def start_upload_mp3(self):
        local_mp3_dir = 'generated_audio'
        drive_folder_id = '# Your folder ID'

        # Start upload thread
        mp3_files = [f for f in os.listdir(local_mp3_dir) if f.endswith('.mp3')]
        self.mp3_progress_bar.setMaximum(len(mp3_files))
        self.upload_thread = Uploadmp3Thread(local_mp3_dir, drive_folder_id)
        self.upload_thread.progress_signal.connect(self.update_mp3_progress)
        self.upload_thread.start()

    def on_download_complete(self):
        self.Trainingstatus.setText("Download complete.")

    def on_upload_complete(self):
        self.Trainingstatus.setText("Upload complete.")



    def train_model(self):

        if os.path.exists(r'duration_model.joblib'):
            os.remove(r'duration_model.joblib')
        if os.path.exists(r'reverse_model.joblib'):
            os.remove(r'reverse_model.joblib')
        duration_model_filename = 'duration_model.joblib'
        reverse_model_filename = 'reverse_model.joblib'
            
        data_dir = 'downloaded_jsons'  # Replace with your directory path
        X, y = self.load_data(data_dir)
        
        # Train and save the models
        duration_model = self.train_duration_model(X, y)
        reverse_model = self.train_reverse_model(X, y)
        
        self.save_model(duration_model, duration_model_filename)
        self.save_model(reverse_model, reverse_model_filename)
        self.Trainingstatus.setText("Models trained and saved to file.")

    def add_silence(self, duration):
        silence = wave.open('silence.wav', 'wb')
        silence.setnchannels(1)
        silence.setsampwidth(2)
        silence.setframerate(44100)
        silence.writeframes(b'\x00\x00' * int(44100 * duration))
        silence.close()
        
        with open('silence.wav', 'rb') as f:
            silence_bytes = f.read()
        
        return silence_bytes

    def createSubtitleBox(self, width, text):
        box = QFrame()
        box.setFixedSize(width, 50)
        box.setStyleSheet("color: black; background-color: lightblue; border-radius: 5px; padding: 0px; margin: 0px;")  # Remove padding and margin
        label = QLabel(text[:10] + '...' if len(text) > 10 else text, box)
        label.setContentsMargins(0, 0, 0, 0)  # Ensure no margins
        label.setStyleSheet("padding: 3px; margin: 0px;")  # Remove padding and margin from label
        box.layout = QVBoxLayout()
        box.layout.setSpacing(0)
        box.layout.setContentsMargins(0, 0, 0, 0)  # Ensure no margins in layout
        box.layout.addWidget(label)
        box.setLayout(box.layout)
        return box

    def empty_directory(self,directory):
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)

    def clear_layout(self, layout):
        # Clear layout efficiently
        for i in reversed(range(layout.count())):
            item = layout.itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()  # Mark the widget for deletion
                    layout.removeWidget(widget)

    def load_srt(self,saved = False , srt = None):
        self.clear_layout_from_index(self.scroll_layout,0)
        self.clear_layout_from_index(self.subtitleLayout,0)
        self.clear_layout(self.timeline)
        self.subtitle_frames = []
        self.total_eng_audio_duration = []
        self.hinditimestamps = []
        self.englishtimestamps = []
        self.current_subtitle = None
        self.changpron = []
        self.audio_length = []
        self.srtids = []
        self.elements = []

        current_srt_dir = 'current_srt'

        # Get original file path
        if not saved :
            original_file_path, _ = QFileDialog.getOpenFileName(self, "Open SRT File", "", "SRT Files (*.srt)")
        else :
            if srt == None:
                original_file_path, _ = QFileDialog.getOpenFileName(
                    self,
                    "Open SRT File",
                    'current_srt',  # Set the initial directory here
                    "SRT Files (*.srt)"
                )
            else : 
                original_file_path = srt
        
        if original_file_path and not saved:  # Check if a file was selected
            srt_name = os.path.basename(original_file_path)
            temp_file_path = os.path.join(current_srt_dir, srt_name)
            
            # Create 'current_srt' directory if it doesn't exist
            os.makedirs(current_srt_dir, exist_ok=True)
            
            # Clear the directory and copy the file
            #self.empty_directory(current_srt_dir)
            shutil.copyfile(original_file_path, temp_file_path)
            self.srt_file_name = temp_file_path
        else :
            self.srt_file_name = os.path.join(current_srt_dir, os.path.basename(original_file_path))

        if not self.srt_file_name:
            return  # Exit if no file is selected

        # Open SRT file and prepare variables
        srt_name = os.path.basename(self.srt_file_name).replace(".srt", "")
        self.subs = pysrt.open(self.srt_file_name)




        start_time = self.subs[0].start.to_time()
        end_time = self.subs[-1].end.to_time()

        # Convert time to seconds
        start_seconds = start_time.hour * 3600 + start_time.minute * 60 + start_time.second + start_time.microsecond / 1e6
        end_seconds = end_time.hour * 3600 + end_time.minute * 60 + end_time.second + end_time.microsecond / 1e6

        # Calculate the total duration in seconds
        total_duration_seconds = end_seconds - start_seconds
        self.slider.setRange(0, total_duration_seconds if not self.isvideoloaded else total_duration_seconds*1000)
        self.timeline_length = 100*total_duration_seconds

        gap_widget = QWidget()# Empty widget to represent gap
        gap_widget.setFixedSize(50, 30)
        gap_widget.setContentsMargins(0, 0, 0, 0)
        gap_widget.setStyleSheet("padding: 0px; margin: 0px;")
        self.timeline.addWidget(gap_widget)
        
        for i in range(int(total_duration_seconds)+1):
            current_time = QLabel(' '+self.format_time_s(i+1))
            current_time.setStyleSheet("background-color: #2b2b2b ; padding: 0px; margin: 0px; text-align: center;")
            dash = QLabel('     |')
            dash.setStyleSheet("background-color: #2b2b2b ; padding: 0px; margin: 0px; text-align: center;")
            container = QWidget()
            timelayout = QVBoxLayout(container)
            timelayout.addWidget(current_time)
            timelayout.addWidget(dash)
            timelayout.setSpacing(0)
            timelayout.setContentsMargins(0, 0, 0, 0)
            timelayout.setAlignment(Qt.AlignCenter)
            container.setStyleSheet("background-color: #2b2b2b ; padding: 0px; margin: 0px; text-align: center;")
            container.setContentsMargins(0, 0, 0, 0)
            container.setFixedSize(100, 30)
            self.timeline.addWidget(container)
        
        

        self.current_position = 0
        self.total_duration = total_duration_seconds
        self.total_eng_audio_duration = 0

        # Analyze sentences and check for audio files if directory exists
        for i, sub in enumerate(self.subs):
            
            audio_path = f"generated_audio/{sub.text.translate(str.maketrans({":": "_", "?": '', "*": "_", "\\": "_"}))}.mp3"
            if os.path.exists(audio_path):
                try:
                    audio_file = File(audio_path)
                    duration = audio_file.info.length
                    self.audio_length.append(duration)

                except Exception as e:
                     print(f"Error processing {audio_path}: {e}")
                     self.audio_length.append(0)
            else: 
                self.audio_length.append(0)
            
            self.analyze_sentence(sub, i)    

        self.isreload = True


    def clear_layout_from_index(self, layout, start_index):
        for i in reversed(range(start_index, layout.count())):
            item = layout.itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()  # Mark the widget for deletion
                    layout.removeWidget(widget)

    def analyze_sentence(self, sub, index , key = None):

        key = uuid.uuid4() if key == None else key 
        self.srtids.insert(index,key)
        twice_index = index*2
        self.changpron.insert(index, False)

        start = sub.start.ordinal
        end = sub.end.ordinal
    
        if index == 0:
            gap_widget = QWidget()

            if start > 0:
                gap_duration = start/1000
                gap_width = round(gap_duration * self.pixels_per_second)
                gap_widget.setFixedSize(gap_width, 50)
                self.subtitleLayout.insertWidget(0, gap_widget)
                self.hinditimestamps.insert(0,(0,start/1000))
                self.englishtimestamps.insert(0,(0,start/1000))
                self.total_eng_audio_duration += gap_duration
            else:
                self.subtitleLayout.insertWidget(0, gap_widget)
                gap_widget.setVisible(False)
                self.hinditimestamps.insert(0,(0,0))
                self.englishtimestamps.insert(0,(0,0))

        
        duration = (end - start) /1000
        box_width = round(duration * self.pixels_per_second)# Ensure consistent scaling
        subtitle_text = sub.text.replace('\n', ' ')  # Replace newlines with spaces
        subtitle_box = self.createSubtitleBox(box_width, subtitle_text)
        eng_audio_start = self.total_eng_audio_duration
        self.total_eng_audio_duration += self.audio_length[index]
        
        self.subtitleLayout.insertWidget(index*2+1,subtitle_box)
        self.hinditimestamps.insert(index*2+1,(start/1000,end/1000))
        self.englishtimestamps.insert(index*2+1,(eng_audio_start ,self.total_eng_audio_duration))

        self.subtitleLayout.setContentsMargins(0, 0, 0, 0)  # Ensure no margins in layout
        gap_widget = QWidget()# Empty widget to represent gap

        if index+1 < len(self.subs):
                next_start = self.subs[index + 1].start.ordinal
                eng_gap_start = self.total_eng_audio_duration
                gap_duration = (next_start - end)/1000
                self.total_eng_audio_duration = self.total_eng_audio_duration+gap_duration
                if gap_duration > 0:
                    gap_width = round(gap_duration * self.pixels_per_second)
                    gap_widget.setFixedSize(gap_width, 50)
                    self.subtitleLayout.insertWidget(index*2+2,gap_widget)
                    self.hinditimestamps.insert(index*2+2,(end/1000,next_start/1000))
                    self.englishtimestamps.insert(index*2+2,(eng_gap_start,self.total_eng_audio_duration))
                else:
                    self.subtitleLayout.insertWidget(index*2+2,gap_widget)
                    self.hinditimestamps.insert(index*2+2,(end/1000,next_start/1000))
                    self.englishtimestamps.insert(index*2+2,(eng_gap_start,self.total_eng_audio_duration))
                    gap_widget.setVisible(False)
          
        
        sentence = sub.text.strip()
        srt_duration = sub.duration.seconds + sub.duration.milliseconds / 1000.0
        calculated_duration = self.calculate_duration(sentence)
        characters = len(sentence)
        words = len(sentence.split())

        calculated_characters,calculated_words = self.calculate_Characters_words(srt_duration)
     
        container = QFrame()
        container.setFixedHeight(225)
        container_layout = QHBoxLayout(container)
        left_container_frame = QFrame()
        left_container = QVBoxLayout(left_container_frame)

        editText = QTextEdit(sentence)

        left_container.addWidget(editText)

        Characters_ratio_label = QLabel(f"{characters} / {calculated_characters} c")
        words_ratio_label = QLabel(f"{words} / {calculated_words} w")
        aibutton = QPushButton('AI')
        Characters_ratio_label.setAlignment(Qt.AlignCenter)
        words_ratio_label.setAlignment(Qt.AlignCenter)
        Characters_ratio_label.setStyleSheet("font-size: 12px; padding: 2px; margin : 2px;color: grey; border: 0px;")
        words_ratio_label.setStyleSheet("font-size: 12px; padding: 2px; margin : 2px;color: grey; border: 0px;")
        aibutton.setStyleSheet("QPushButton { font-size: 12px; padding: 2px; margin : 2px;color: grey; border: 0px; border-radius : 1px;} QPushButton:hover {background-color: #4a4a4a;}")
        left_container_frame.setStyleSheet("border: 1px solid #555555; padding:0px; margin: 0px;")
        editText.setStyleSheet("border: 0px; padding:0px; margin: 0px;")


        
        ratio_container= QHBoxLayout()
        ratio_container.addWidget(Characters_ratio_label)
        ratio_container.addWidget(words_ratio_label)
        ratio_container.addWidget(aibutton)
        left_container.addLayout(ratio_container)
        left_container.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(left_container_frame)
        
        right_container = QVBoxLayout()

        top_container = QHBoxLayout()
        
        self.isff = QCheckBox("Change Pron.")
        top_container.addWidget(self.isff)
        for i in self.words_prons :
            if re.search(fr"\b{i[0]}\b" , sentence):
                self.isff.setChecked(True)
                self.changpron[index] = True
        self.isff.setStyleSheet("background-color: rgba(0, 0, 0, 0);")   
        # split Button
        self.cutButton = QPushButton("</>")
        self.cutButton.setStyleSheet("QPushButton { font-size: 12x; padding: 1px; margin : 0px; color: grey; text-align: center; } QPushButton:hover {background-color: #4a4a4a;}")
        top_container.addWidget(self.cutButton)
        self.deleteButton = QPushButton("🗙")
        self.deleteButton.setStyleSheet("QPushButton { font-size: 12x; padding: 1px; margin : 0px; color: grey; text-align: center; } QPushButton:hover {background-color: #4a4a4a;}")
        top_container.addWidget(self.deleteButton)        

        right_container.addLayout(top_container)

        timestamp_container = QHBoxLayout()
        self.leftcropbutton = QPushButton("{")
        self.rightcropbutton = QPushButton("}")
        timestamp_start_label = QLineEdit(self.format_timestamp(sub.start))
        timestamp_diveder_label = QLabel(":")
        timestamp_end_label = QLineEdit(self.format_timestamp(sub.end))
        timestamp_start_label.setStyleSheet("font-size: 12px; padding: 1px; margin : 0px;color: grey; background-color: #2b2b2b; text-align: center;" )
        timestamp_diveder_label.setStyleSheet("font-size: 12x; padding: 1px; margin : 0px;" )
        timestamp_end_label.setStyleSheet("font-size: 12px; padding: 1px; margin : 0px;color: grey; background-color: #2b2b2b; text-align: center;" )
        self.leftcropbutton.setStyleSheet("QPushButton { font-size: 12x; padding: 1px; margin : 0px; color: grey; } QPushButton:hover {background-color: #4a4a4a;}")
        self.rightcropbutton.setStyleSheet("QPushButton { font-size: 12x; padding: 1px; margin : 0px; color: grey; } QPushButton:hover {background-color: #4a4a4a;}")

        timestamp_start_label.setFixedWidth(75)
        timestamp_end_label.setFixedWidth(75)

        timestamp_start_label.setAlignment(Qt.AlignCenter)
        timestamp_end_label.setAlignment(Qt.AlignCenter)

        timestamp_container.addWidget(self.leftcropbutton)
        timestamp_container.addWidget(timestamp_start_label)
        timestamp_container.addWidget(timestamp_diveder_label)
        timestamp_container.addWidget(timestamp_end_label)
        timestamp_container.addWidget(self.rightcropbutton)
        
        right_container.addLayout(timestamp_container)

        formatted_srt_duration = self.format_time(srt_duration)
        formatted_calculated_duration = self.format_time(calculated_duration)

        duration_ratio_label = QLabel(f"{formatted_calculated_duration} / {formatted_srt_duration} sec")

        audio_duration_label = QLabel("No Audio")
        duration_ratio_label.setAlignment(Qt.AlignCenter)

        audio_duration_label.setAlignment(Qt.AlignCenter)
        duration_ratio_label.setStyleSheet("font-size: 12px; padding: 0px; margin : 0px;" )
        audio_duration_label.setStyleSheet("font-size: 12px; padding: 1px; margin : 0px;color: grey;" )
        

        right_container.addWidget(audio_duration_label)
        right_container.addWidget(duration_ratio_label)

        regenerate_button = QPushButton("Regenerate Audio")
        right_container.addWidget(regenerate_button)
        
        play_button = QPushButton("Play")
        right_container.addWidget(play_button)
   
        if self.play_buttontext:
            play_button.setText("Play")
        
            
        right_container.setAlignment(Qt.AlignCenter)
        container_layout.addLayout(right_container)

        if self.scroll_layout.count() > twice_index:
            self.scroll_layout.insertWidget(twice_index,container)
        else:
            self.scroll_layout.addWidget(container)

        srtbutton_container_frame = QFrame()
        srtbutton_container_frame.setFixedHeight(80)
        srtbutton_container_frame.setStyleSheet("background-color: #2b2b2b;")

        srtbutton_container = QHBoxLayout(srtbutton_container_frame)

        end = sub.end.ordinal / 1000.0
        next_start = self.subs[index + 1].start.ordinal / 1000.0 if index+1 < len(self.subs) else sub.end.ordinal / 1000.0

        add_srt_button = QPushButton("Add Sub")
        srtbutton_container.addWidget(add_srt_button)
        add_srt_button.setVisible(False)
        merge_srt_button = QPushButton("↑ Merge Sub ↓")
        srtbutton_container.addWidget(merge_srt_button)
        merge_srt_button.setVisible(False)

        if next_start - end > 1 :
            add_srt_button.setVisible(True)
        if index +1 != len(self.subs) :
            merge_srt_button.setVisible(True)

            
        if self.scroll_layout.count() > twice_index+1:
            self.scroll_layout.insertWidget(twice_index+1,srtbutton_container_frame)
        else:
            self.scroll_layout.addWidget(srtbutton_container_frame)

        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_layout.setAlignment(Qt.AlignCenter)
        


        
        if os.path.exists(f"generated_audio/{sub.text.translate(str.maketrans({":": "_", "?": '', "*": "_", "\\": "_"}))}.mp3"):
            if self.audio_length[index] != 0:
                audio_duration_label.setText(f"🎙{self.audio_length[index]}s")
                if self.audio_length[index] > duration:
                    audio_duration_label.setStyleSheet("font-size: 12px; padding: 1px; margin : 0px;color: red;" )
                else:
                    audio_duration_label.setStyleSheet("font-size: 12px; padding: 1px; margin : 0px;color: grey;" )
                    
            play_button.setStyleSheet('border: 0 ; color: black; background-color: lightblue;')
        else:
            play_button.setStyleSheet('border: 1px solid #555555; color: white; background-color: rgba(0, 0, 0, 0);')

        self.subtitle_frames.insert(index,(sub, container,srtbutton_container_frame,subtitle_box,gap_widget ))
        self.srtduration.insert(index,srt_duration)
        self.elements.insert(index,(editText,timestamp_start_label,timestamp_end_label))

        add_srt_button.clicked.connect(lambda: self.addsub(key))
        self.isff.stateChanged.connect(lambda state, i=key : self.isffcheck(state,i))
        self.cutButton.clicked.connect(lambda: self.cutTime(key))
        self.deleteButton.clicked.connect(lambda: self.deletesub(key))
        self.leftcropbutton.clicked.connect(lambda: self.croptime(key,False))
        self.rightcropbutton.clicked.connect(lambda: self.croptime(key))
        play_button.clicked.connect(lambda: self.play_audio(key, sub, play_button))
        self.video_player_thread2.MediaStatusChanged.connect(lambda status: self.check_media_status(status, play_button))
        regenerate_button.clicked.connect(lambda: self.generate_audio(key,play_button,audio_duration_label))
        try:
            merge_srt_button.clicked.connect(lambda: self.mergesubs(key))
        except:
            None
        aibutton.clicked.connect(lambda: self.aisubtitle(key))
        editText.textChanged.connect(lambda: self.update_duration_on_edit(editText,words_ratio_label,Characters_ratio_label,calculated_characters,calculated_words,duration_ratio_label,formatted_srt_duration,srt_duration,sub,calculated_duration,key))
        timestamp_start_label.editingFinished.connect(lambda: self.timestamp_edit(sub,key))
        timestamp_end_label.editingFinished.connect(lambda: self.timestamp_edit(sub,key,True))
        self.generateAudioButton.clicked.connect(lambda: self.generate_audio_for_all(sub, key, play_button, audio_duration_label))
        self.convert.clicked.connect(lambda: self.convert_to_audio(key))

    def timestamp_edit(self,sub,key,isend = False):
        index = self.srtids.index(key)
        timestamp_lable = self.elements[index][1] if isend else self.elements[index][2]
        timestr = timestamp_lable.text()
        hours, minutes, seconds = timestr.split(":")
        seconds, milliseconds = seconds.split(",")

        hours = int(hours)
        minutes = int(minutes)
        seconds = int(seconds)
        milliseconds = int(milliseconds)
        
        # Calculate the total milliseconds
        total_milliseconds = (hours * 3600 * 1000) + (minutes * 60 * 1000) + (seconds * 1000) + milliseconds
        next_start = self.subs[index+1].start.ordinal if index < len(self.subs)-1 else self.subs[index].end.ordinal+1000
        prev_end = self.subs[index-1].end.ordinal if index != 0 else 0
        if total_milliseconds > next_start and isend:
            timestamp_lable.setText(self.format_time_h(next_start-10))
            total_milliseconds = next_start -10
        elif total_milliseconds < prev_end and not isend:
            timestamp_lable.setText(self.format_time_h(prev_end+10))
            total_milliseconds = prev_end +10

        self.croptime(sub,key,timestamp_lable,isend,total_milliseconds)

    def aisubtitle(self, key):
        index = self.srtids.index(key)
        editText = self.elements[index][0]
        subtitle = editText.toPlainText().strip()
        text = subtitle
        next_subtitle = self.subs[index+1].text if index < len(self.subs)-1 else ''
        prev_subtitle = self.subs[index-1].text if index > 0 else ''
        start = self.subs[index].start.ordinal /1000
        end = self.subs[index].end.ordinal /1000
        data = [(0,0,prev_subtitle),(start,end,subtitle),(0,0,next_subtitle)]
        subtitle = self.process_segment( 1, data)[3]
        editText.setText(subtitle)
        self.subs[index].text = subtitle
        self.undolist.append(('aisub',key,text))
        

    def changetext(self,key,text):
        index = self.srtids.index(key)
        editText = self.elements[index][0]
        editText.setText(text)
        self.subs[index].text = text

    def undo_action(self):
        action = self.undolist.pop()
        if action[0] == 'mergesubs':
            self.cutTime(action[1],action[2],action[3],action[4],action[5],True,action[6])
        elif action[0] == 'cutTime' : 
            self.mergesubs(action[1],True)
        elif action[0] == 'croptime' :
            self.croptime(action[1],action[2],action[3],True)
        elif action[0] == 'deletesub' :
            self.addsub(action[1],action[2],action[3],action[4],True,action[5])
        elif action[0] == 'addsub' :
            self.deletesub(action[1],True)
        elif action[0] == 'aisub' :
            self.changetext(action[1],action[2])


    def mergesubs(self, key, isundo=False):
        index = self.srtids.index(key)
        timestamp_end_label = self.elements[index][2]
        editText = self.elements[index][0]
        next_gap = round((self.subs[index+2].start.ordinal/1000 - self.subs[index+1].end.ordinal/1000) * self.pixels_per_second) if index+2 < len(self.subs) else 0
        gap = round((self.subs[index+1].start.ordinal/1000 - self.subs[index].end.ordinal/1000) * self.pixels_per_second)
        next_subtitle = self.subs[index+1]
        end_time = self.subs[index].end.ordinal
        start_time = self.subs[index+1].start.ordinal
        timestamp_end_label.setText(self.format_time_h(next_subtitle.end.ordinal))
        
        cur_text = self.subs[index].text.strip()
        cursor_end = len(cur_text)
        next_text = next_subtitle.text.strip()
        merged_text = f"{cur_text}{next_text}"

        self.subs[index].end = self.subs[index+1].end
        self.subs[index].text = merged_text
        next_index = index+1        

        self.subtitle_frames[index+1][1].deleteLater()  
        self.scroll_layout.removeWidget(self.subtitle_frames[index+1][1])

        self.subtitle_frames[index+1][2].deleteLater()  
        self.scroll_layout.removeWidget(self.subtitle_frames[index+1][2])

        self.subtitle_frames[index+1][3].deleteLater()  
        self.subtitleLayout.removeWidget(self.subtitle_frames[index+1][3])


        self.subtitle_frames[index+1][4].deleteLater()  
        self.subtitleLayout.removeWidget(self.subtitle_frames[index+1][4])

        self.subtitleLayout.removeWidget(self.subtitle_frames[index][3])
        self.subtitleLayout.removeWidget(self.subtitle_frames[index][4])
        
        self.subtitle_frames[index][4].setFixedSize(next_gap,50)

        duration = (self.subs[index].end.ordinal - self.subs[index].start.ordinal ) /1000

        box_width = round(duration * self.pixels_per_second)

        self.subtitle_frames[index][3].setFixedSize(box_width, 50)

        self.subtitleLayout.insertWidget((index*2)+1 , self.subtitle_frames[index][4])
        self.subtitleLayout.insertWidget((index*2)+1 , self.subtitle_frames[index][3])
        self.subtitle_frames[index][4].setVisible(True)
        next_key = self.srtids[index+1]

        self.subs.pop(next_index)
        self.srtids.pop(next_index)
        self.elements.pop(next_index)
        self.subtitle_frames.pop(next_index)
        self.changpron.pop(next_index)
        self.audio_length.pop(next_index)
        self.current_subtitle = None

        audio_path = f"generated_audio/{merged_text.translate(str.maketrans({":": "_", "?": '', "*": "_", "\\": "_"}))}.mp3"

        if os.path.exists(audio_path):
            try:
                audio_file = File(audio_path)
                duration = audio_file.info.length
                self.audio_length[index] = duration

            except Exception as e:
                    print(f"Error processing {audio_path}: {e}")
                    self.audio_length[index] = 0
        else: 
            self.audio_length[index] = 0

        editText.setText(merged_text)

        self.timelinescrollArea.update()
        self.scroll_area.update()

        if not isundo :
            self.undolist.append(('mergesubs',key,cursor_end,end_time,start_time,gap,next_key))


    def cutTime(self,key,cursorp = None ,end_time = None, start_time = None, gap = 0, isundo = False, current_key = None):
        index = self.srtids.index(key)
        editText = self.elements[index][0]
        timestamp_end_label = self.elements[index][2]
        position = self.get_playhead_x_position()*10  # position in seconds
        start = self.subs[index].start.ordinal
        end = self.subs[index].end.ordinal
        if end > position > start:
            cursor = editText.textCursor() 
            cursor_position = cursor.position() if cursorp == None else cursorp
            if cursor_position == 0:
                cursor_position = int(len(editText.toPlainText())/2)
            text = editText.toPlainText()
            text_before = text[:cursor_position]
            text_after= text[cursor_position:]
            cut_time = self.format_time_h(position)
            timestamp_end_label.setText(cut_time)
            editText.setText(text_before)
            
            new_sub = pysrt.SubRipItem(
                index= index+1,  # Index for the new subtitle (can be adjusted)
                start= pysrt.SubRipTime.from_ordinal(position if start_time == None else start_time),  
                end= self.subs[index].end,   
                text= text_after
            )
            editText.setText(text_before)
            timestamp_end_label.setText(self.format_time_h(position if end_time == None else end_time))            
            
            self.subs[index].text = text_before
            self.subs[index].end = pysrt.SubRipTime.from_ordinal(position if end_time == None else end_time)
            self.subs.insert(index+1 , new_sub)

            
            duration = (self.subs[index].end.ordinal - self.subs[index].start.ordinal ) /1000

            box_width = round(duration * self.pixels_per_second)

            self.subtitle_frames[index][3].setFixedSize(box_width, 50)

            audio_path = f"generated_audio/{text_before.translate(str.maketrans({":": "_", "?": '', "*": "_", "\\": "_"}))}.mp3"
            if os.path.exists(audio_path):
                try:
                    audio_file = File(audio_path)
                    duration = audio_file.info.length
                    self.audio_length[index] = duration

                except Exception as e:
                        print(f"Error processing {audio_path}: {e}")
                        self.audio_length[index] = 0
            else: 
                self.audio_length[index] = 0

            
            if current_key != None:
                self.analyze_sentence(new_sub,index+1,current_key)
            else:
                self.analyze_sentence(new_sub,index+1)
            if gap > 0 :
                self.subtitleLayout.removeWidget(self.subtitle_frames[index][4])
                self.subtitle_frames[index][4].setFixedSize(gap,50)
                self.subtitleLayout.insertWidget((index*2)+2,self.subtitle_frames[index][4])
                self.subtitle_frames[index][4].setVisible(True)
            else:
                self.subtitle_frames[index][4].setFixedSize(0,50)
                self.subtitle_frames[index][4].setVisible(False)

            if not isundo :
                self.undolist.append(('cutTime',key))
        
    def deletesub(self, key , isundo = False):
        index = self.srtids.index(key)
        if index == 0:
            return
        text = self.subs[index].text
        start = self.subs[index].start.ordinal
        end = self.subs[index].end.ordinal

        self.subtitle_frames[index][1].deleteLater()  
        self.scroll_layout.removeWidget(self.subtitle_frames[index][1])

        self.subtitle_frames[index][2].deleteLater()  
        self.scroll_layout.removeWidget(self.subtitle_frames[index][2])

        self.subtitle_frames[index][3].deleteLater()  
        self.subtitleLayout.removeWidget(self.subtitle_frames[index][3])

        self.subtitle_frames[index][4].deleteLater()  
        self.subtitleLayout.removeWidget(self.subtitle_frames[index][4])
        
        if index != 0 :
            self.subtitleLayout.removeWidget(self.subtitle_frames[index-1][4])
            self.subtitle_frames[index-1][4].setVisible(True)
            duration = (self.subs[index+1].start.ordinal - self.subs[index-1].end.ordinal) /1000

            box_width = round(duration * self.pixels_per_second)

            self.subtitle_frames[index-1][4].setFixedSize(box_width, 50)

            self.subtitleLayout.insertWidget(((index-1)*2)+2 , self.subtitle_frames[index-1][4] )
            if duration > 1:
                self.subtitle_frames[index-1][2].children()[1].setVisible(True)
        else:
            gap_widget =  self.subtitleLayout.itemAt(0).widget()
            gap_widget.setVisible(True)
            self.subtitleLayout.removeWidget(gap_widget)

            duration = self.subs[index+1].start.ordinal /1000

            box_width = round(duration * self.pixels_per_second)
            gap_widget.setFixedSize(box_width, 50)

            self.subtitleLayout.insertWidget(0 , gap_widget)


        self.subs.pop(index)
        self.srtids.pop(index)
        self.elements.pop(index)
        self.subtitle_frames.pop(index)
        self.changpron.pop(index)
        self.audio_length.pop(index)
        self.current_subtitle = None

        self.timelinescrollArea.update()
        self.scroll_area.update()
        
        
        if not isundo :
            self.undolist.append(('deletesub',self.srtids[index-1],text,start,end,key))
    
    def addsub(self,key,text ='', nstart = None ,nend = None,isundo = False,current_key = None):
        index = self.srtids.index(key)
        next_start = self.subs[index+1].start.ordinal if index < len(self.subs) - 1 else self.subs[index].end.ordinal
        end = self.subs[index].end.ordinal 
        new_sub = pysrt.SubRipItem(
                index= index+1,  # Index for the new subtitle (can be adjusted)
                start= pysrt.SubRipTime.from_ordinal(end if nstart == None else nstart),  
                end= pysrt.SubRipTime.from_ordinal(next_start if nend == None else nend),   
                text= text
        )
        if index+1 < len(self.subs):
            self.subs.insert(index+1 , new_sub)
            self.audio_length.insert(index+1, 0)
            self.subtitle_frames[index][2].children()[1].setVisible(False)
            if current_key != None:
                self.analyze_sentence(new_sub,index+1,current_key)
            else:
                self.analyze_sentence(new_sub,index+1)
            gap = 0 if nstart == None else round((nstart - end)/1000 * self.pixels_per_second)
            if gap > 0 :
                self.subtitleLayout.removeWidget(self.subtitle_frames[index][4])
                self.subtitle_frames[index][4].setFixedSize(gap,50)
                self.subtitleLayout.insertWidget((index*2)+2,self.subtitle_frames[index][4])
                self.subtitle_frames[index][4].setVisible(True)
            else:
                self.subtitle_frames[index][4].setFixedSize(0,50)
                self.subtitle_frames[index][4].setVisible(False)
        if not isundo:
            self.undolist.append(('addsub',self.srtids[index+1]))



    def croptime(self,key, isend =True, positionP = None , isundo = False):
        index = self.srtids.index(key)
        timestamp_label = self.elements[index][1] if isend else self.elements[index][2]
        position = self.get_playhead_x_position()*10 if positionP == None else positionP
        start = self.subs[index].start.ordinal
        next_start = self.subs[index+1].start.ordinal if index < len(self.subs) - 1 else self.subs[index].end.ordinal
        prev_end = self.subs[index-1].end.ordinal if index != 0 else 0
        end = self.subs[index].end.ordinal
        if next_start >= position >= start and isend :
            self.subs[index].end = pysrt.SubRipTime.from_ordinal(position)
            timestamp_label.setText(self.format_time_h(position))
            srt_duration = (position - start) /1000
            gap_duration = (next_start - position) /1000
            box_width = round(srt_duration * self.pixels_per_second)
            gap_width = round(gap_duration * self.pixels_per_second)
            subtitlebox = self.subtitle_frames[index][3]
            gap_widget = self.subtitle_frames[index][4]
            self.subtitleLayout.removeWidget(subtitlebox)
            self.subtitleLayout.removeWidget(gap_widget)
            subtitlebox.setFixedSize(box_width, 50)
            gap_widget.setFixedSize(gap_width, 50)
            gap_widget.setVisible(True)
            self.subtitleLayout.insertWidget((index*2)+1,gap_widget)
            self.subtitleLayout.insertWidget((index*2)+1,subtitlebox)
            if gap_duration > 1:
                self.subtitle_frames[index][2].children()[1].setVisible(True)
            else :
                self.subtitle_frames[index][2].children()[1].setVisible(False)
            if not isundo:
                self.undolist.append(('croptime',key,True,end))
        elif (not isend) and end >= position >= prev_end:
            self.subs[index].start = pysrt.SubRipTime.from_ordinal(position)
            timestamp_label.setText(self.format_time_h(position))
            srt_duration = (end - position) /1000
            gap_duration = (position - prev_end) /1000
            box_width = round(srt_duration * self.pixels_per_second)
            gap_width = round(gap_duration * self.pixels_per_second)
            subtitlebox = self.subtitle_frames[index][3]
            gap_widget = self.subtitle_frames[index-1][4] if index > 0 else self.subtitleLayout.itemAt(0).widget()
            self.subtitleLayout.removeWidget(subtitlebox)
            self.subtitleLayout.removeWidget(gap_widget)
            subtitlebox.setFixedSize(box_width, 50)
            gap_widget.setFixedSize(gap_width, 50)
            gap_widget.setVisible(True)
            self.subtitleLayout.insertWidget((index*2),subtitlebox)
            self.subtitleLayout.insertWidget((index*2) if index > 0 else 0,gap_widget)
            if gap_duration > 1 and index > 0:
                self.subtitle_frames[index-1][2].children()[1].setVisible(True)
            else :
                self.subtitle_frames[index-1][2].children()[1].setVisible(False)
            if not isundo :
                self.undolist.append(('croptime',key,False,start))

        self.timelinescrollArea.update()
        self.scroll_area.update()

    def update_duration_on_edit(self, editText,words_ratio_label,Characters_ratio_label,calculated_characters,calculated_words,duration_ratio_label,formatted_srt_duration,srt_duration,sub,calculated_duration,key):
        index = self.srtids.index(key)
        self.isedited = True
        self.updateButton.setStyleSheet('border: 0 ; color: black; background-color: lightblue;')
        sentence = editText.toPlainText().strip()

        self.subtitle_lable.setText(sentence)
        characters = len(sentence)
        words = len(sentence.split())
        calculated_duration_n = self.calculate_duration(sentence)
        formatted_calculated_duration = self.format_time(calculated_duration_n)
        Characters_ratio_label.setText(f"{characters} / {calculated_characters} c")
        words_ratio_label.setText(f"{words} / {calculated_words} w")
        duration_ratio_label.setText(f"{formatted_calculated_duration} / {formatted_srt_duration} sec")
        sub.text = sentence
        start = self.subs[index].start.ordinal
        end = self.subs[index].end.ordinal
        position = start + ((end - start) /2)
        self.set_position(int(position),True)
        self.timelinescrollArea.ensureWidgetVisible(self.playhead)
        

    def isffcheck(self, state, key):
        index = self.srtids.index(key)
        if state == 2:
            self.changpron[index] = True
        else:
            self.changpron[index] = False

    def calculate_duration(self, sentence):
        model = self.load_model('duration_model.joblib')
        words = len(sentence.split())
        characters = len(sentence)
        features = np.array([[words, characters]])
        return model.predict(features)[0] - 0.15

    def calculate_Characters_words(self, duration):
        model = self.load_model('reverse_model.joblib')
        features = np.array([[duration]])
        predicted_counts = model.predict(features)
        words, characters = predicted_counts[0]
        return int(round(characters)), int(round(words))

    def format_timestamp(self, subrip_time):
        timestamp = subrip_time.to_time()
        return timestamp.strftime("%H:%M:%S,%f")[:-3]

    def format_time(self, time_in_seconds):
        minutes = int(time_in_seconds // 60)
        seconds = int(time_in_seconds % 60)
        milliseconds = int((time_in_seconds * 1000) % 1000)
        return f"{seconds:02}.{milliseconds:03}"
    
    def format_time_s(self, time_in_seconds):
        minutes = int(time_in_seconds // 60)
        seconds = int(time_in_seconds % 60)
        milliseconds = int((time_in_seconds * 1000) % 1000)
        return f"{minutes:02}:{seconds:02}"

    def format_time_m(self, time_in_seconds):
        minutes = int(time_in_seconds // 60)
        seconds = int(time_in_seconds % 60)
        milliseconds = int((time_in_seconds * 1000) % 1000)
        return f"{minutes:02}:{seconds:02}:{milliseconds:03}"
    
    def format_time_h(self, time_in_seconds):
        time_in_seconds = time_in_seconds /1000
        hours = int(time_in_seconds / 3600)
        minutes = int(time_in_seconds // 60)
        seconds = int(time_in_seconds % 60)
        milliseconds = int((time_in_seconds * 1000) % 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    def update_srt(self):
        self.updateButton.setStyleSheet('border: 0 ; color: white; background-color: #3c3c3c;')
        self.subs.save(self.srt_file_name)
        #self.reload_srt()

        
    def save_subtitles_as(self):
        new_file_name, _ = QFileDialog.getSaveFileName(
            None, "Save Subtitles As", "", "SubRip Subtitle Files (*.srt)"
        )

        if not new_file_name:
            return

        self.subs.save(new_file_name)

    def export_subtitles(self):
        new_file_name, _ = QFileDialog.getSaveFileName(
            None, "Save Subtitles As", "", "SubRip Subtitle Files (*.srt)"
        )
        self.subs.save('temp srt')
        self.subt = pysrt.open('temp srt')

        if not new_file_name:
            return

        self.subt.save(new_file_name)
   

    def generate_audio(self, key, play_button,audio_duration_label):
        index = self.srtids.index(key)
        text = self.subs[index].text
        if self.changpron[index]:
            for i in self.words_prons:
                text = re.sub(rf"\b{(i[0])}\b",f"<phoneme alphabet='{(i[2])}' ph='{(i[1])}'>{(i[0])}</phoneme>", text)
        print(text)
        prev_text = self.subs[index - 1].text if index > 0 and self.subs[index - 1].text != '' else " "
        next_text = self.subs[index + 1].text if index < len(self.subs) - 1 and self.subs[index - 1].text != '' else " "
        srt_name = srt_name = os.path.basename(self.srt_file_name).replace(".srt", "")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.VOICE_ID}/with-timestamps"
        headers = {
            "Content-Type": "application/json",
            "xi-api-key": self.YOUR_XI_API_KEY
        }

        modelid = "eleven_turbo_v2" if self.changpron[index] else "eleven_turbo_v2_5"
 
        data = {
            "text": text,
            "model_id": modelid,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
            "previous_text": prev_text,
            "next_text": next_text
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code != 200:
            print(f"Error encountered, status: {response.status_code}, content: {response.text}")
            return

        json_string = response.content.decode("utf-8")
        response_dict = json.loads(json_string)

        sentence = ''.join(response_dict["alignment"]['characters'])
        words = len(sentence.split())
        characters = len(sentence)
        sub_duration = response_dict["alignment"]['character_end_times_seconds'][-1]
        filename = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8)) + '.json'

        
        json_data = {
        "characters":response_dict["alignment"]['characters'],
        "character_start_times_seconds":response_dict["alignment"]['character_start_times_seconds'],
        "character_end_times_seconds":response_dict["alignment"]['character_end_times_seconds'],
        "sentence": sentence,
        "words": words,
        "characters": characters,
        "duration": sub_duration
        }
        if "character_end_times_seconds" not in response_dict["alignment"]:
            print(f"Key 'character_end_times_seconds' noffowrdt found in response. Full response: {response_dict}")
            return

        audio_bytes = base64.b64decode(response_dict["audio_base64"])
        
        newpath = f'generated_audio'
        newpath2 = f'downloaded_jsons'
        
        if not os.path.exists(newpath):
            os.makedirs(newpath)
            
        if not os.path.exists(newpath2):
            os.makedirs(newpath2)
            
        with open(f'downloaded_jsons/{filename}', 'w') as json_file:
            json.dump(json_data, json_file, indent=4)

        with open(f"generated_audio/{self.subs[index].text.translate(str.maketrans({":": "_", "?": '', "*": "_", "\\": "_"}))}.mp3", 'wb') as f:
            f.write(audio_bytes)

        # Updating duration with the response
        self.audio_length[index] = sub_duration
        audio_duration_label.setText(f"🎙{sub_duration}s")
        duration = (self.subs[index].end.ordinal - self.subs[index].start.ordinal)/1000
        if sub_duration > duration:
            audio_duration_label.setStyleSheet("font-size: 12px; padding: 1px; margin : 0px;color: red;" )
        else:
            audio_duration_label.setStyleSheet("font-size: 12px; padding: 1px; margin : 0px;color: grey;" )
        self.isff.setChecked(True)
        play_button.setStyleSheet('border: 0 ; color: black; background-color: lightblue;')
        
    def change_speed(self,speedfactor, lable = None):
        try:
            current_speed = float(lable.text()) if lable != None else 1
        except:
            lable.setText(str(1))
            current_speed = 1.0
        current_speed = round( current_speed + speedfactor ,1 )
        if current_speed <= 0.0:
                current_speed = 0.1
        lable.setText(str(current_speed))
        self.video_player_thread1.set_current_speed(current_speed)
        self.video_player_thread3.set_current_speed(current_speed)

    def generate_audio_for_all(self,sub, key, play_button, duration_ratio_label):
        index = self.srtids.index(key)
        if os.path.exists(f"generated_audio/{self.subs[index].text.translate(str.maketrans({":": "_", "?": '', "*": "_", "\\": "_"}))}.mp3"):
            return
        else:
            self.generate_audio(key, play_button, duration_ratio_label)

        
    def check_media_status(self, status, play_button):
        if status == QMediaPlayer.EndOfMedia:
            self.play_buttontext = True
            if self.video_player_thread2.is_playing():
                self.video_player_thread2.pause()
                play_button.setText("Play")
                        

    def play_audio(self,key, sub, play_button):
        if self.video_player_thread2.is_playing():
            self.video_player_thread2.pause()
            play_button.setText("Play")
        else:
            srt_name = os.path.basename(self.srt_file_name).replace(".srt", "")
            file_path = f"generated_audio/{sub.text.translate(str.maketrans({":": "_", "?": '', "*": "_", "\\": "_"}))}.mp3"
            if os.path.exists(file_path):
                self.video_player_thread2.set_source(file_path)
                self.video_player_thread2.video_player.play()
                play_button.setText(f"Pause")
            

    def load_video(self):
        try:
            srt_name = os.path.basename(self.srt_file_name).replace(".srt", "")
        except:
            pass
        self.video_file_name, _ = QFileDialog.getOpenFileName(self, "Open Video File", "", "Video Files (*.mp4 *.avi *.mkv)")
        if self.video_file_name:
            self.video_player_thread1.set_source(self.video_file_name)
            self.isvideoloaded = True
            try:
                self.video_player_thread3.set_source(f'combined_audio/{srt_name}_combined_video.mp4')
            except:
                pass
            self.play_pause_button.setIcon(self.play_icon)


    def toggle_play_pause(self):
        if self.isvideoloaded:
            if self.video_player_thread1.is_playing():
                self.video_player_thread1.pause()
                self.video_player_thread3.pause()
                self.play_pause_button.setIcon(self.play_icon)
                self.playheadTimer.stop()
            else:
                self.video_player_thread1.video_player.play()
                self.video_player_thread3.video_player.play()
                self.play_pause_button.setIcon(self.pause_icon)
                self.playheadTimer.start(100)

    def toggle_mute(self):
        if self.is_muted:
            self.video_player_thread1.toggle_mute()
            self.video_player_thread3.toggle_mute()
            self.mute_button.setStyleSheet("background-color: #3c3c3c;")
        else:
            self.video_player_thread1.toggle_mute()
            self.video_player_thread3.toggle_mute()
            self.mute_button.setStyleSheet("background-color: #2b2b2b;")
            
        self.is_muted = not self.is_muted

    def position_changed(self, position):
        self.slider.setValue(position)
        self.current_position = position / 1000  # Convert to seconds
        self.update_display()
        self.updatePlayhead()
        

    def duration_changed(self, duration):
        self.slider.setRange(0, duration)
        self.total_duration = duration / 1000  # Convert to seconds
        self.update_display()

    def update_display(self):
        self.changed_current_position = self.format_time_m(self.current_position)
        self.changed_total_duration = self.format_time_m(self.total_duration)
        current_pos_str = self.changed_current_position
        total_dur_str = self.changed_total_duration
        self.timestamp.setText(f"{current_pos_str} / {total_dur_str}")

    def set_position(self, position,isjump = False):
        self.video_player_thread1.set_Position(position)
        if self.isvideoloaded or isjump :
            self.updatePlayheadPosition(position/1000)
            self.current_position = position/1000
            self.sync_subtitles(position)
            self.sync_dub(position)
        else:
            self.updatePlayheadPosition(position)
            self.current_position = position
            self.sync_subtitles(position*1000)
            self.sync_dub(position*1000)

        self.update_display()
        self.timelinescrollArea.ensureWidgetVisible(self.playhead)


    def updatePlayheadPosition(self, position):
        self.playhead.move(position * 100, self.playhead.y())  # 30 pixels per second
        self.playhead.raise_()

    def updatePlayhead(self):
        position = self.video_player_thread1.position() / 1000  # convert to seconds
        self.updatePlayheadPosition(position)
        self.timelinescrollArea.ensureWidgetVisible(self.playhead)

    def get_playhead_x_position(self):
        return self.playhead.x()

    def moveright(self):
        position = self.get_playhead_x_position() + 10
        seconds = position / 100
        self.slider.setValue(round(seconds))  # Sync video slider
        self.set_position(round(seconds * 1000),True)
        self.current_position = seconds

        self.update_display()   
        # self.playhead.move(position, self.playhead.y())
        # self.playhead.raise_()
        self.timelinescrollArea.ensureWidgetVisible(self.playhead)

    def moveleft(self):
        position = self.get_playhead_x_position() - 10
        seconds = position / 100
        self.slider.setValue(round(seconds))  # Sync video slider
        self.set_position(round(seconds * 1000),True)
        self.current_position = seconds

        self.update_display()
        # self.playhead.move(position, self.playhead.y())
        # self.playhead.raise_()
        self.timelinescrollArea.ensureWidgetVisible(self.playhead)

    def jumpPlayhead(self, event):
            
        x = event.position().x()
        seconds = x / 100 # Convert position to seconds
        #self.updatePlayheadPosition(seconds)  # Move playhead visually
        self.slider.setValue(round(seconds))  # Sync video slider
        self.set_position(round(seconds * 1000),True)
        self.current_position = seconds

        self.update_display()


    def sync_subtitles(self, position):
        if len(self.subs) > 0:
            current_time = position / 1000  # Convert from milliseconds to seconds

            times = [sub.start.ordinal / 1000 for sub, _,__,___,____ in self.subtitle_frames]  # Convert start times to seconds
            index = bisect.bisect_right(times, current_time) - 1
            if index >= 0 and index < len(self.subtitle_frames):
                sub, frame,_,__,___ = self.subtitle_frames[index]
                start_time = sub.start.ordinal / 1000  # Convert to seconds
                end_time = sub.end.ordinal / 1000  # Convert to seconds

                if start_time <= current_time <= end_time:
                    if self.current_subtitle != frame:
                        if self.current_subtitle:
                            self.current_subtitle.setStyleSheet("background-color: #3c3c3c; color: #f0f0f0;")
                        self.subtitle_lable.setText(sub.text)
                        frame.setStyleSheet("background-color: #2c3e50; color: white;")
                        self.scroll_area.ensureWidgetVisible(frame)
                        self.current_subtitle = frame
                else:
                    if self.current_subtitle:
                        self.current_subtitle.setStyleSheet("background-color: #3c3c3c; color: #f0f0f0;")
                        self.current_subtitle = None
                        self.subtitle_lable.setText('')

    def sync_time(self, position):
        if len(self.subs) > 0:
            current_time = position / 1000  # Convert from milliseconds to seconds
            stimes = [sub.start.ordinal / 1000 for sub, _,__,___,____ in self.subtitle_frames]  # Convert start times to seconds
            etimes = [sub.end.ordinal / 1000 for sub, _,__,___,____ in self.subtitle_frames]  # Convert start times to seconds
            index = bisect.bisect_right(stimes, current_time) - 1
            if stimes[index]<current_time<etimes[index]:
                srt_duration = etimes[index] - stimes[index]
                speed = srt_duration / self.audio_length[index] if self.audio_length[index] > 0 else 1
                self.video_player_thread1.setspeed(speed)
            else:
                self.video_player_thread1.setspeed(1)

    def sync_dub(self, position):
        if len(self.subs) > 0:
            current_time = position / 1000  # Convert from milliseconds to seconds

            stimes = [sub[0] for sub in self.hinditimestamps]  # Convert start times to seconds
            etimes = [sub[1] for sub in self.hinditimestamps]  # Convert start times to seconds
            index = bisect.bisect_right(stimes, current_time) - 1
            if stimes[index]<current_time<etimes[index]:
                hindi_srt_duration = etimes[index] - stimes[index]
                english_srt_duration = self.englishtimestamps[index][1] - self.englishtimestamps[index][0]
                hinpos =  current_time - stimes[index] 
                endpos = hinpos/hindi_srt_duration * english_srt_duration
                endpos = self.englishtimestamps[index][0] + endpos
                
                self.video_player_thread3.set_Position(int(endpos*1000))



    def convert_to_audio(self ,key):
        index = self.srtids.index(key)
        newpath = f'combined_audio'
        srt_name = os.path.basename(self.srt_file_name).replace(".srt", "")

        if index == 0 and os.path.exists(f'combined_audio/{srt_name}_combined_audio.mp3'):
            os.remove(f'combined_audio/{srt_name}_combined_audio.mp3')
            self.progress_bar.setMaximum(100)
            self.audioprogresscount = 0
            self.progress_bar.setValue(0)
            silence_audio = AudioSegment.silent(0)
            silence_audio = silence_audio.set_frame_rate(44100)
            self.combined_audio = silence_audio

            
        if not os.path.exists(newpath):
            os.makedirs(newpath)


        if os.path.exists(f"generated_audio/{self.subs[index].text.translate(str.maketrans({":": "_", "?": '', "*": "_", "\\": "_"}))}.mp3"):
            audio_file_path = f"generated_audio/{self.subs[index].text.translate(str.maketrans({":": "_", "?": '', "*": "_", "\\": "_"}))}.mp3"
        else:
            return
        
        audio = self.load_audio_silently(audio_file_path)
        audio = audio.set_frame_rate(44100)
        audio_length = len(audio) / 1000.0
        start = self.subs[index].start.ordinal / 1000.0
        end = self.subs[index].end.ordinal / 1000.0
        srt_duration = end - start
        next_start = self.subs[index + 1].start.ordinal / 1000.0 if index+1 < len(self.subs) else self.subs[index].end.ordinal / 1000.0

        if index == 0 :
            if self.subs[index].start.ordinal != 0:
                silence_duration = self.subs[index].start.ordinal
                silence_audio = AudioSegment.silent(silence_duration)
                silence_audio = silence_audio.set_frame_rate(44100)
                audio = silence_audio + audio

            
        audio = self.combined_audio + audio

       
            
        silence_duration =  next_start - end 
        
        
        silence_audio = AudioSegment.silent(silence_duration*1000)
        silence_audio = silence_audio.set_frame_rate(44100)

        if silence_duration > 0:
            self.combined_audio = audio + silence_audio
        else :
            self.combined_audio = audio
        self.combined_audio = self.combined_audio.set_frame_rate(44100)
        
        if index == len(self.subs) - 1 :
            self.output_file_path = f'combined_audio/{srt_name}_combined_audio.mp3'
            self.combined_audio.export(self.output_file_path, format="mp3")
            audio_file_path = self.output_file_path  # This is your generated mp3 file
            output_video_path = f'combined_audio/{srt_name}_combined_video.mp4'  # Path to the output video file

            audio_clip = AudioFileClip(audio_file_path)

            blank_video = ColorClip(size=(1280, 720), color=(0, 0, 0), duration=audio_clip.duration)

            blank_video = blank_video.set_fps(24)

            video_with_audio = blank_video.set_audio(audio_clip)

            video_with_audio.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
            #self.video_player_thread3.set_source(f'combined_audio/{srt_name}_combined_video.mp4')

        self.audioprogresscount = self.audioprogresscount +1
        self.audioprogresscountp = 100/len(self.audio_length)*self.audioprogresscount
        self.progress_bar.setValue(self.audioprogresscountp)  
    
    def export_video(self):
        newpath = f'temp_video'
        self.temp_video_directory = newpath
        self.output_path =  QFileDialog.getSaveFileName(self, "Save Output Video", "", "Video Files (*.mp4 *.avi *.mov)")[0]
        base_name = os.path.splitext(self.output_path)[0]
        new_file_name = base_name + ".srt"
        self.subs.save('temp srt')
        self.subt = pysrt.open('temp srt')

        if not new_file_name:
            return

        if not os.path.exists(newpath):
            os.makedirs(newpath)

        timestr = self.timestamp_start_label.text()
        hours, minutes, seconds = timestr.split(":")
        seconds, milliseconds = seconds.split(",")
        hours = int(hours)
        minutes = int(minutes)
        seconds = int(seconds)
        milliseconds = int(milliseconds)
        startmilliseconds = (hours * 3600 * 1000) + (minutes * 60 * 1000) + (seconds * 1000) + milliseconds
        durationchanged = False
        timestr = self.timestamp_end_label.text()
        hours, minutes, seconds = timestr.split(":")
        seconds, milliseconds = seconds.split(",")
        hours = int(hours)
        minutes = int(minutes)
        seconds = int(seconds)
        milliseconds = int(milliseconds)
        endmilliseconds = (hours * 3600 * 1000) + (minutes * 60 * 1000) + (seconds * 1000) + milliseconds
        intro_duration = endmilliseconds - startmilliseconds
        changeintro = self.chnageintrocheck.isChecked() and intro_duration > 0
        
        self.videoprogresscount = 0
        video = VideoFileClip(self.video_file_name)
        videoclips = []
        self.progress_bar.setMaximum(100)
        totalduration = 0
        currentduration = 0 
        for i, sub in enumerate(self.subs):
            start = sub.start.ordinal/1000
            end = sub.end.ordinal/1000
            srt_duration = end - start
            next_start = self.subs[i+1].start.ordinal / 1000.0 if i+1 < len(self.subs) else sub.end.ordinal / 1000.0
            
            if i == 0 and sub.start.ordinal != 0 :
                clip = video.subclip(0, start)
                clip_duration = clip.duration*1000
                totalduration += clip_duration
                currentduration += clip_duration
                if currentduration >= startmilliseconds and not durationchanged and changeintro:
                    durationchanged = True
                    clipf = video.subclip(0,int(startmilliseconds/1000))
                    clipf2 = video.subclip(int(endmilliseconds/1000),start)
                    introcombined = [clipf,VideoFileClip('new_intro.mp4'),clipf2]
                    clip = concatenate_videoclips(introcombined, method="compose")
                    clip = VideoFileClip('new_intro.mp4') if clipf.duration < 0.5 or clipf2.duration < 0.5 else clip
                    totalduration -= clip_duration
                    totalduration += clip.duration
                videoclips.append(clip)
                
                
            self.subt[i].start = pysrt.SubRipTime.from_ordinal(totalduration)
            speed = srt_duration / self.audio_length[i]
            clip = video.subclip(start,end).fx(vfx.speedx, speed)
            clip_duration = clip.duration*1000
            totalduration += clip_duration
            currentduration += srt_duration*1000
            self.subt[i].end = pysrt.SubRipTime.from_ordinal(totalduration)
            videoclips.append(clip)
                

            if next_start - end > 0:
                clip = video.subclip(end,next_start)
                clip_duration = clip.duration*1000
                currentduration += clip_duration
                if currentduration >= startmilliseconds and not durationchanged and changeintro:
                    startmilliseconds = totalduration + (startmilliseconds - end*1000)
                    endmilliseconds = startmilliseconds + intro_duration
                    durationchanged = True
                    clipg = video.subclip(end,startmilliseconds/1000)
                    clipg2 = video.subclip(endmilliseconds/1000, next_start)
                    introcombined = [clipg,VideoFileClip('new_intro.mp4'),clipg2]
                    clip = concatenate_videoclips(introcombined)
                    clip = VideoFileClip('new_intro.mp4') if clipg.duration < 0.5 or clipg2.duration < 0.5 else clip
                    clip_duration = clip.duration*1000
                totalduration += clip_duration
                videoclips.append(clip)
            else:
                if end < self.total_duration and i+1 == len(self.subs):
                    clip = video.subclip(end,self.total_duration)
                    clip_duration = clip.duration*1000
                    totalduration += clip_duration
                    currentduration += clip_duration
                    videoclips.append(clip)
                    
                    
            self.videoprogresscount += 1
            print(self.videoprogresscount,'/',len(self.audio_length))
            self.videoprogresscountp = 100/len(self.audio_length)*self.videoprogresscount
            self.progress_bar.setValue(self.videoprogresscountp )

        finalvideo= concatenate_videoclips(videoclips, method="compose")
        srt_name = os.path.basename(self.srt_file_name).replace(".srt", "")
        audio_path = f'combined_audio/{srt_name}_combined_audio.mp3'
        combined_audio = AudioFileClip(audio_path)
        audio_before = combined_audio.subclip(0,startmilliseconds/1000)
        audio_after = combined_audio.subclip(endmilliseconds/1000,combined_audio.duration)
        intro_audio = AudioFileClip("new_intro.mp3")
        new_audio = concatenate_audioclips([audio_before,intro_audio,audio_after]) if changeintro else combined_audio
        finalvideo = finalvideo.set_audio(new_audio)
        finalvideo.write_videofile(self.output_path)

        self.subt.save(new_file_name)

    def time_in_range(self, start, end, time):
        """Check if a time (seconds) falls within the given start and end times (seconds)."""
        return start <= time <= end

    def segment_has_no_subtitles(self, segments, subtitle_list):
        """Check which segments have no subtitles from the provided subtitle list."""
        no_subtitle_segments = []

        for segment in segments:
            segment_start, segment_end = segment
            has_subtitle = False
            
            for subtitle in subtitle_list:
                subtitle_start = subtitle[0]
                subtitle_end = subtitle[1]
                
                if (self.time_in_range(segment_start, segment_end, subtitle_start) or
                    self.time_in_range(segment_start, segment_end, subtitle_end) or
                    (segment_start <= subtitle_start and segment_end >= subtitle_end)):
                    has_subtitle = True
                    break
            
            if not has_subtitle:
                no_subtitle_segments.append(segment)

        return no_subtitle_segments
    
    def generate_subtitle(self):

        video_clip = VideoFileClip(self.video_file_name)
        audio_clip = video_clip.audio
        
        audio_clip.write_audiofile("temp_audio.mp3", codec="mp3")
        audiofile = open("temp_audio.mp3", "rb")
        # audio_clip.write_audiofile("temp_audio.wav")
        # audio = AudioSegment.from_file("temp_audio.wav", format = 'mp3')
        # segments = self.detect_speech(audio)


        subtitles = self.audiototext(audiofile)
        print("All subtitles genrated")
        # segments = self.segment_has_no_subtitles(segments,subtitles)

        # trimmed_clips = [audio_clip.subclip(start, end) for start, end in segments]
        # trimmed_clipsn=[]

        # for i in trimmed_clips :
        #     i.write_audiofile("temp_audio.wav")
        #     audio = open("temp_audio.wav", "rb")
        #     trimmed_clipsn.append(audio)

        # subtitles_left = []

        # for i in trimmed_clipsn:
        #     subtitlparts = self.audiototext(i)
        #     subtitles_left= subtitles_left + subtitlparts

        # combined_subtitles = subtitles + subtitles_left

        # subtitles = sorted(combined_subtitles, key=lambda x: x[0])

        subs = self.convert_to_srt(subtitles)
        srt_save_path = 'current_srt/' + os.path.basename(self.video_file_name).replace(".mp4", ".srt")

        subs.save(srt_save_path)

        self.load_srt(True,srt_save_path)

       
    def upload_to_s3(self, audio_file_obj, bucket_name):
        """Uploads the audio file to S3."""
        file_name = f"audio_upload_{int(time.time())}.mp3"
        s3_client.upload_fileobj(audio_file_obj, bucket_name, file_name)
        audio_uri = f"s3://{bucket_name}/{file_name}"
        print(f"Uploaded {file_name} to S3 bucket {bucket_name}")
        return audio_uri


    def start_transcription(self, audio_s3_uri, job_name, language_code='hi-IN'):
        """Starts a transcription job on AWS Transcribe."""
        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': audio_s3_uri},
            MediaFormat='mp3',
            LanguageCode=language_code
        )
        print(f"Started transcription job: {job_name}")


    def wait_for_transcription(self, job_name):
        """Waits for the transcription job to complete."""
        while True:
            status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
            if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
                return status
            print("Waiting for transcription to complete...")
            time.sleep(10)


    def get_transcription_result(self, job_name):
        """Fetches the transcription result from AWS Transcribe and returns the transcript as JSON."""
        result = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        transcript_uri = result['TranscriptionJob']['Transcript']['TranscriptFileUri']
        
        transcript_response = requests.get(transcript_uri)
        
        if transcript_response.status_code == 200:
            transcript_data = transcript_response.json()
            return transcript_data
        else:
            raise Exception(f"Failed to fetch transcript from {transcript_uri}, Status Code: {transcript_response.status_code}")

    def clear_s3_bucket(self,bucket_name):
        """Deletes all files from the specified S3 bucket."""
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name)
            
            if 'Contents' in response:
                objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
                
                s3_client.delete_objects(
                    Bucket=bucket_name,
                    Delete={'Objects': objects_to_delete}
                )
                print(f"Deleted all files from S3 bucket {bucket_name}")
            else:
                print(f"No files found in S3 bucket {bucket_name} to delete.")

        except Exception as e:
            print(f"Error while clearing S3 bucket: {e}")
    
    
    def audiototext(self, audio):

        bucket_name = "gpworksaudiofiletotranscribe"

        audio_s3_uri = self.upload_to_s3(audio, bucket_name)

        job_name = f"transcription_job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.start_transcription(audio_s3_uri, job_name)

        result = self.wait_for_transcription(job_name)

        data = self.get_transcription_result(job_name)

        self.clear_s3_bucket(bucket_name)

        data = self.combine_segments(data)


        subtitles = []
        self.totaldata = len(data)
        with open('transcription.json','w') as json_file:
            json.dump(data,json_file, indent=4)
 
        print('json dumped')
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_index = {executor.submit(self.process_segment, i, data): i for i in range(len(data))}
            
            self.currentprogress = 0

            for future in concurrent.futures.as_completed(future_to_index):
                i, start, end, text = future.result()  # Get the result from each future
                subtitles.append((i, start, end, text))  # Append with index to maintain order

        subtitles.sort(key=lambda x: x[0])

        subtitles = [(start, end, text) for _, start, end, text in subtitles]
        with open('subtitle.json','w') as json_file:
            json.dump(subtitles,json_file, indent=4)
 
        print('json dumped')
        
        return subtitles

    def process_segment(self, i, data):
        client = openai.OpenAI(api_key=self.CHATGPT_APi)
        thread = client.beta.threads.create()
        underlimit = False
        loopindex = 0
        retries = 0
        max_retries = 5  # Max retries on rate limit

        prev_text = data[i - 1][2] if i > 0 else ''
        next_text = data[i + 1][2] if i < len(data) - 1 else ''
        calculated_characters, calculated_words = self.calculate_Characters_words(data[i][1] - data[i][0])
        calculated_characters += int(calculated_characters/100 * 30)
        calculated_words += int(calculated_words/100 * 30)

        while not underlimit:
            if loopindex == 0:
                content = f'''
                    prev text: {prev_text}
                    current text: {data[i][2]}
                    next text: {next_text}
                    word limit: {calculated_words}
                    character limit: {calculated_characters}
                '''
            elif loopindex == 3:
                underlimit = True
                self.currentprogress += 1
                return (i, data[i][0], data[i][1], data[i][2])
            else:
                content = 'smaller'

            try:
                message = client.beta.threads.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=content
                )
                
                run = client.beta.threads.runs.create_and_poll(
                    thread_id=thread.id,
                    assistant_id= self.Assistance_id,
                    instructions= ', '.join(self.GPTcommands)
                )

                if run.status == 'completed':
                    messages = client.beta.threads.messages.list(thread_id=thread.id)
                    try:
                        response = messages.data[0].content[0].text.value
                    except:
                        loopindex += 1
                        pass
                    characters = len(response)
                    words = len(response.split())

                    if (characters > calculated_characters or words > calculated_words )and loopindex < 5:
                        loopindex += 1
                    else:
                        try:
                            underlimit = True
                            self.currentprogress += 1
                            print(self.currentprogress ,'/',self.totaldata)
                            return (i, data[i][0], data[i][1], response)
                        except:
                            print('error in this = ',response)
                            loopindex += 1
                else:
                    print('waiting....')
                    time.sleep(3)
                    if run.status == 'completed':
                        messages = client.beta.threads.messages.list(thread_id=thread.id)
                        response = messages.data[0].content[0].text.value
                        characters = len(response)
                        words = len(response.split())

                        if characters > calculated_characters or words > calculated_words:
                            loopindex += 1
                        else:
                            try:
                                underlimit = True
                                self.currentprogress += 1
                                print(self.currentprogress ,'/',self.totaldata)
                                return (i, data[i][0], data[i][1], response)
                            except:
                                print('error in this = ',response)
                                loopindex += 1
                    else:
                        self.currentprogress += 1
                        return (i, data[i][0], data[i][1], data[i][2])



            except openai.RateLimitError:
                retries += 1
                if retries <= max_retries:
                    wait_time = 2 ** retries  # Exponential backoff (e.g., 2s, 4s, 8s)
                    print(f"Rate limit hit. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print("Max retries reached. Skipping this segment.")
                    break  
        print('nothing')
        self.currentprogress += 1
        return (i, data[i][0], data[i][1], data[i][2])
          
            
    def combine_segments(self,data):
        max_words = 20
        combined_segments = []

        current_start = None
        current_end = None
        current_text = ""

        for word in data['results']['items']:
            if current_text == "":
                if not (word["type"] == "punctuation"):
                    current_start = float(word["start_time"])
                    current_end = float(word["end_time"])
                    current_text = word["alternatives"][0]["content"]
                else:
                    pass
            else:
                if word["alternatives"][0]["content"] == "।":
                    combined_segments.append((current_start, current_end, current_text))
                    current_end = None
                    current_start = None
                    current_text = ""
                elif len(current_text.split()) >= max_words:
                    combined_segments.append((current_start, current_end, current_text))
                    current_end = None
                    current_start = None
                    current_text = ""
                elif word["type"] == "punctuation":
                    current_text += " " + word["alternatives"][0]["content"]
                    combined_segments.append((current_start, current_end, current_text))
                    current_end = None
                    current_start = None
                    current_text = ""
                else :
                    try:
                        current_end = float(word["end_time"])
                    except:
                        pass
                    current_text += " " + word["alternatives"][0]["content"]
        
        return combined_segments
    
    def convert_to_srt(self, subtitles):
        subs = pysrt.SubRipFile()
        
        for index, (start_time, end_time, subtitle_text) in enumerate(subtitles):
            start_timedelta = self.seconds_to_timedelta(start_time)
            end_timedelta = self.seconds_to_timedelta(end_time)
            
            sub = pysrt.SubRipItem(index=index,
                                start= self.timedelta_to_subriptime(start_timedelta),
                                end= self.timedelta_to_subriptime(end_timedelta),
                                text=subtitle_text)
            subs.append(sub)
        
        return subs
    
    def seconds_to_timedelta(self, seconds):
        return timedelta(seconds=seconds)

    def timedelta_to_subriptime(self, timedelta_obj):
        total_seconds = int(timedelta_obj.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        milliseconds = timedelta_obj.microseconds // 1000
        return pysrt.SubRipTime(hours=hours, minutes=minutes, seconds=seconds, milliseconds=milliseconds)


    def setup_video_player(self, video_widget,ifvideo, volume=1.0):
        video_player_worker = VideoPlayerWorker(video_widget,ifvideo, volume)
        video_player_worker.start()
        return video_player_worker

    def closeEvent(self, event):
        # Ensure threads are properly stopped
        self.video_player_thread1.stop()
        self.video_player_thread2.stop()
        self.video_player_thread3.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SRTAnalyzer()
    window.show()
    sys.exit(app.exec())
