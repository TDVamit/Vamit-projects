import os
import sys
import yt_dlp
from datetime import datetime
import difflib
import requests
from urllib.parse import urlparse
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QFileDialog
)
from PySide6.QtGui import QLinearGradient, QBrush, QPalette,QColor
from PySide6.QtCore import QThread, Signal, QObject , Qt
import unicodedata
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import concurrent.futures
import time
import shutil
import csv

class DownloadWorker(QObject):
    progress = Signal(str,str)  # Signal to emit progress (current, total)
    finished = Signal(str)  # Signal to notify when download is done

    def __init__(self):
        super().__init__()


    def sanitize_filename(self,filename):
        # Replace invalid characters with an underscore
        return unicodedata.normalize('NFKD',re.sub(r'[<>:"/\\|?*]', '_', filename))

    def format_filename(self,date, title, extension):
        """Format the filename with the given date, title, and extension."""
        formatted_date = date.strftime("%d-%m-%Y")
        
        # Replace invalid characters with underscores or remove them
        safe_title = "".join(
            c if c.isalnum() or c in " _-" else "_" for c in title
        )
        
        # Construct the final filename
        return self.sanitize_filename(f"{formatted_date} - {safe_title}.{extension}")


    
    def delete_https_subfolders(self,folder_path):
        """
        Scan the given folder and delete any subfolder starting with 'https'.

        :param folder_path: Path to the folder to scan.
        """
        try:
            for root, dirs, files in os.walk(folder_path, topdown=False):
                for dir_name in dirs:
                    if dir_name.startswith("https"):
                        dir_path = os.path.join(root, dir_name)
                        print(f"Deleting folder: {dir_path}")
                        try:
                            shutil.rmtree(dir_path)
                        except OSError as e:
                            print(f"Error deleting folder {dir_path}: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")

    def download_youtube_video(self,url,download_path='yt_downloads',title= None,upload_date=None):
        download_path = os.path.abspath(download_path)
        self.delete_https_subfolders(download_path)
        ischannel = False

        if title and upload_date:
            ischannel = True
            upload_date = datetime.strptime(upload_date, "%Y-%m-%dT%H:%M:%SZ")
            mp4file = os.path.join(download_path,self.format_filename(upload_date,title,'mp4'))
            if os.path.exists(mp4file):
                return


        download_folder = os.path.join(download_path,self.sanitize_filename(url))
        if not os.path.exists(download_folder):
            os.mkdir(download_folder)
        else:
            folder_exsist = True
            times = 0
            while folder_exsist:
                time.sleep(3)
                if not os.path.exists(download_folder):
                    folder_exsist = False
                if times >= 5:
                    os.removedirs(download_folder)
                    folder_exsist = False
                times += 1
                

        """Download a single YouTube video, thumbnail, and description."""
        ydl_opts = {
            'outtmpl': os.path.join(download_folder, 'files.%(ext)s'),
            'format':'bestvideo[ext=mp4][height=1080]+bestaudio[ext=m4a]/best[ext=mp4][height=1080]',
            'writedescription': True,
            'writethumbnail': True
        }
        e_num = 0
        while True:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    if not ischannel:
                        info = ydl.extract_info(url, download=False)
                        title = info.get('title')
                        upload_date = datetime.strptime(info['upload_date'], "%Y%m%d")
                        video_ext = info.get('ext')
                        new_video_name = self.format_filename(upload_date, title, video_ext)
                        if os.path.exists(os.path.join(download_path,new_video_name)):
                            self.finished.emit(url)
                            return

                    info = ydl.extract_info(url, download=True)
                    title = info.get('title')
                    upload_date = datetime.strptime(info['upload_date'], "%Y%m%d")

                    # Rename downloaded video file
                    video_ext = info.get('ext')
                    video_path = os.path.join(download_folder, f"files.{video_ext}")
                    new_video_name = self.format_filename(upload_date, title, video_ext)
                    print("new video name:",new_video_name)
                    shutil.move(video_path, os.path.join(download_path, new_video_name))
                    print(f"Downloaded video: {new_video_name}")
                    
                    # Rename downloaded thumbnail
                    thumbnail_path = os.path.join(download_folder, f"files.webp")
                    if os.path.exists(thumbnail_path):
                        new_thumbnail_name = self.format_filename(upload_date, title, "jpg")
                        shutil.move(thumbnail_path, os.path.join(download_path, new_thumbnail_name))
                        print(f"Downloaded thumbnail: {new_thumbnail_name}")

                    # Rename description info JSON to .txt
                    txt_path = os.path.join(download_folder, f"files.description")
                    if os.path.exists(txt_path):

                        new_description_name = self.format_filename(upload_date, title, "txt")
                        shutil.move(txt_path, os.path.join(download_path, new_description_name))
                        print(f"Saved description as: {new_description_name}")
                    break
            except Exception as e:
                print(str(e))
                if e_num == 0:
                    ydl_opts = {
                        'outtmpl': os.path.join(download_folder, 'files.%(ext)s'),
                        'format':'bestvideo[ext=mp4][height=720]+bestaudio[ext=m4a]/best[ext=mp4][height=720]',
                        'writedescription': True,
                        'writethumbnail': True
                    }
                elif e_num == 1:
                    ydl_opts = {
                        'outtmpl': os.path.join(download_folder, 'files.%(ext)s'),
                        'format':'best',
                        'writedescription': True,
                        'writethumbnail': True
                    }
                elif e_num == 5:
                    if not ischannel:
                        self.finished.emit(url) 
                    return
                e_num += 1
        
        if os.path.exists(download_folder):
            shutil.rmtree(download_folder)
        if not ischannel:
            self.finished.emit(url)        


    def download_channel_videos(self,channel_url,api_key, download_path='yt_downloads'):
        """Download all videos from a YouTube channel."""
        uploads_playlist_id,channel_name = self.get_channel_uploads_playlist_id(channel_url, api_key)
        channel_folder = os.path.join(download_path,self.sanitize_filename(channel_name))
        if not os.path.exists(channel_folder):
            os.mkdir(channel_folder)
        download_path = channel_folder
        if uploads_playlist_id:
            # Step 2: Get all videos from the uploads playlist
            videos = self.get_all_videos_from_playlist(uploads_playlist_id, api_key)
            print(f"Total videos found: {len(videos)}\n")
        else:
            print("Failed to retrieve uploads playlist ID.")

        for i, video in enumerate(videos):
            self.progress.emit(channel_url, f"{i+1}/{len(videos)}")
            self.download_youtube_video(video['url'], download_path, video['title'], video['upload_date'])
            
            # Write data to the CSV file
            csv_file_path = os.path.abspath("video_data.csv")  # Change the file name or path as needed
            self.write_to_csv(csv_file_path, channel_name, video['title'], video['url'])

        #self.parallel_download(videos, download_path, self.download_youtube_video, self.progress,channel_url)

        self.finished.emit(channel_url)

    def write_to_csv(self,file_path, channel_name, title, url):
        # Check if the file exists
        file_exists = os.path.exists(file_path)
        
        # Open the file in append mode
        with open(file_path, mode='a', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            
            # Write header if file doesn't exist
            if not file_exists:
                writer.writerow(["Channel Name", "Video Title", "Video URL"])
            
            # Write the row data
            writer.writerow([channel_name, title, url])


    def download_video(self,video, download_path, download_function):
        """
        Wrapper function to download a video.
        """
        video_link = video['url']
        download_function(video_link, download_path)
        return video_link

    def parallel_download(self,videos, download_path, download_function, progress_signal,url):
        """
        Downloads videos in parallel using ThreadPoolExecutor.
        """
        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(self.download_video, video, download_path, download_function): i
                for i, video in enumerate(videos)
            }

            for future in as_completed(futures):
                i = futures[future]
                try:
                    result = future.result()  # Get the result of the future
                    progress_signal.emit(url,f"{i + 1}/{len(videos)}")
                except Exception as e:
                    progress_signal.emit(url,f"{i + 1}/{len(videos)}")

    def get_channel_uploads_playlist_id(self,channel_url, api_key):
        channel_id = ''
        try:
            parsed_url = urlparse(channel_url)
            # Check if the URL contains '/channel/'
            if "/channel/" in parsed_url.path:
                channel_id = parsed_url.path.split("/channel/")[1].strip("/")
            else:
                print("Invalid URL or not a direct channel URL.")
                return
        except Exception as e:
            print(f"An error occurred: {e}")
            return 
        
        """Fetch the Uploads playlist ID of the channel."""
        base_url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            "part": "snippet,contentDetails",
            "id": channel_id,
            "key": api_key
        }
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        try:
            uploads_playlist_id = data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            channel_name = data["items"][0]["snippet"]["title"]
            return uploads_playlist_id,channel_name
        except (KeyError, IndexError):
            print("Error: Could not find uploads playlist.")
            return None

    def get_all_videos_from_playlist(self, playlist_id, api_key):
        """Fetch all video titles, links, and upload dates from the playlist with parallel requests."""
        base_url = "https://www.googleapis.com/youtube/v3/playlistItems"
        max_results_per_request = 50

        def fetch_page(page_token=None):
            params = {
                "part": "snippet",
                "playlistId": playlist_id,
                "maxResults": max_results_per_request,
                "key": api_key,
                "pageToken": page_token,
            }
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            return response.json()

        # Fetch the first page to get total items and nextPageToken
        initial_data = fetch_page()
        videos = []

        # Collect video details from the initial page
        for item in initial_data["items"]:
            title = item["snippet"]["title"]
            video_id = item["snippet"]["resourceId"]["videoId"]
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            upload_date = item["snippet"]["publishedAt"]  # ISO 8601 format
            videos.append({"title": title, "url": video_url, "upload_date": upload_date})

        next_page_token = initial_data.get("nextPageToken")

        # Collect all subsequent page tokens
        page_tokens = []
        while next_page_token:
            page_tokens.append(next_page_token)
            next_page_data = fetch_page(next_page_token)
            next_page_token = next_page_data.get("nextPageToken")

        # Define a function to fetch a single page's videos
        def fetch_and_parse_videos(page_token):
            data = fetch_page(page_token)
            page_videos = []
            for item in data["items"]:
                title = item["snippet"]["title"]
                video_id = item["snippet"]["resourceId"]["videoId"]
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                upload_date = item["snippet"]["publishedAt"]  # ISO 8601 format
                page_videos.append({"title": title, "url": video_url, "upload_date": upload_date})
            return page_videos

        # Use ThreadPoolExecutor to fetch videos concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_token = {executor.submit(fetch_and_parse_videos, token): token for token in page_tokens}
            for future in as_completed(future_to_token):
                try:
                    videos.extend(future.result())
                except Exception as e:
                    print(f"Error fetching page: {e}")

        return videos

# GUI Class
class YouTubeDownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader")
        self.setGeometry(100, 100, 500, 300)
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.threads = {}
        self.elements = {}

        # Layouts
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Download Path
        path_layout = QHBoxLayout()
        path_label = QLabel("Download Path:")
        self.path_input = QLineEdit(os.path.join( os.getcwd(),'yt_downloads'))
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_download_path)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_button)
        main_layout.addLayout(path_layout)

        # Input URL
        api_layout = QHBoxLayout()
        api_label = QLabel("Youtube Data Api:")
        self.api_input = QLineEdit("place your Youtube Api here")
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_input)
        main_layout.addLayout(api_layout)


        # Download Main Channel
        main_path_layout = QHBoxLayout()
        main_path_label = QLabel("Download Main Channel")
        self.main_browse_button = QPushButton("Download")
        self.main_browse_button.clicked.connect(self.download_main_channel)
        main_path_layout.addWidget(main_path_label)
        main_path_layout.addWidget(self.main_browse_button)
        main_layout.addLayout(main_path_layout)

        # Download Yellow Channel
        yellow_path_layout = QHBoxLayout()
        yellow_path_label = QLabel("Download Yellow Channel")
        self.yellow_browse_button = QPushButton("Download")
        self.yellow_browse_button.clicked.connect(self.download_yellow_channel)
        yellow_path_layout.addWidget(yellow_path_label)
        yellow_path_layout.addWidget(self.yellow_browse_button)
        main_layout.addLayout(yellow_path_layout)

        # Download Small Channel
        small_path_layout = QHBoxLayout()
        small_path_label = QLabel("Download Small Channel")
        self.small_browse_button = QPushButton("Download")
        self.small_browse_button.clicked.connect(self.download_small_channel)
        small_path_layout.addWidget(small_path_label)
        small_path_layout.addWidget(self.small_browse_button)
        main_layout.addLayout(small_path_layout)

        # Input URL
        url_layout = QHBoxLayout()
        url_label = QLabel("YouTube URL:")
        self.url_input = QLineEdit()
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        main_layout.addLayout(url_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.single_video_button = QPushButton("Download Video")
        self.channel_videos_button = QPushButton("Download Channel")
        self.single_video_button.clicked.connect(self.download_video)
        self.channel_videos_button.clicked.connect(self.download_channel)
        button_layout.addWidget(self.single_video_button)
        button_layout.addWidget(self.channel_videos_button)
        main_layout.addLayout(button_layout)

    def browse_download_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if path:
            self.path_input.setText(path)

    def download_video(self):
        url = self.url_input.text()
        download_path = self.path_input.text()
        self.elements[url]=self.single_video_button.setEnabled(False)
        self.single_video_button.setEnabled(False)
        if url:
            try:
                self.executor.submit(self.Download_video_thread,url, download_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred: {e}")
        else:
            QMessageBox.warning(self, "Input Error", "Please provide a valid YouTube URL.")

    def download_channel(self):
        url = self.url_input.text()
        self.elements[url] = self.channel_videos_button
        self.channel_videos_button.setEnabled(False)
        api = self.api_input.text()
        download_path = self.path_input.text()
        if url:
            if not 'channel' in url:
                QMessageBox.critical(self, "Input Error", f"Please Enter Valid Channel Url")
            else:
                try:
                    self.executor.submit(self.Download_channel_thread,url,api, download_path)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"An error occurred: {e}")
        else:
            QMessageBox.warning(self, "Input Error", "Please provide a valid YouTube URL.")
    
    def download_main_channel(self):
        url = "https://www.youtube.com/channel/UC_4NoVAkQzeSaxCgm-to25A/" # replace with your channel link
        self.elements[url] = self.main_browse_button
        self.main_browse_button.setEnabled(False)
        api = self.api_input.text()
        download_path = self.path_input.text()
        if url:
            try:
                self.executor.submit(self.Download_channel_thread,url,api, download_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred: {e}")
        else:
            QMessageBox.warning(self, "Input Error", "Please provide a valid YouTube URL.")

    def download_yellow_channel(self):
        url = "https://www.youtube.com/channel/UCrOmFbHgf_k4pk-jYRmyhjw/" # replace with your channel link
        self.elements[url] = self.yellow_browse_button
        self.yellow_browse_button.setEnabled(False)
        api = self.api_input.text()
        download_path = self.path_input.text()
        if url:
            try:
                self.executor.submit(self.Download_channel_thread,url,api, download_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred: {e}")
        else:
            QMessageBox.warning(self, "Input Error", "Please provide a valid YouTube URL.")

    def download_small_channel(self):
        url = "https://www.youtube.com/channel/UC1FfoXAlTmo_jGtTG_bw3bA/" # replace with your channel link
        self.elements[url] = self.small_browse_button
        self.small_browse_button.setEnabled(False)
        api = self.api_input.text()
        download_path = self.path_input.text()
        if url:
            try:
                self.executor.submit(self.Download_channel_thread,url,api, download_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred: {e}")
        else:
            QMessageBox.warning(self, "Input Error", "Please provide a valid YouTube URL.")

    def Download_video_thread(self,url,download_path):
        thread = QThread()
        self.threads[url] = thread
        worker = DownloadWorker()
        worker.moveToThread(thread)
        worker.finished.connect(self.video_download_complete)
        thread.started.connect(worker.download_youtube_video(url, download_path))
        thread.start()

    def Download_channel_thread(self,url,api, download_path):
        thread = QThread()
        self.threads[url] = thread
        worker = DownloadWorker()
        worker.moveToThread(thread)
        worker.progress.connect(self.update_progress)
        thread.started.connect(worker.download_channel_videos(url,api, download_path))
        thread.start()

    def update_progress(self,url,progress):
        """Update button text and color dynamically based on progress."""
        # Extract progress values
        current, total = map(int, progress.split('/'))
        ratio = current / total if total > 0 else 0

        # Update button text
        button = self.elements[url]
        button.setText(progress)

        # Create a gradient based on the progress ratio
        gradient = QLinearGradient(0, 0, button.width(), 0)
        gradient.setColorAt(0.0, Qt.green)  # Start with green
        gradient.setColorAt(ratio, Qt.green)  # End green at the progress point
        gradient.setColorAt(ratio, QColor("#1e1e1e"))  # Start default color
        gradient.setColorAt(1.0, QColor("#1e1e1e"))  # End with default

        # Apply gradient to the button
        palette = button.palette()
        palette.setBrush(QPalette.Button, QBrush(gradient))
        button.setPalette(palette)
        button.setAutoFillBackground(True)

    def video_download_complete(self,url):
        video_download_button = self.elements[url]
        video_download_button.setEnabled(True)
        thread = self.threads[url]
        thread.quit()
        thread.wait()
        QMessageBox.information(self, "Success", "Video downloaded successfully!")

    def channel_download_complete(self,url):
        """Handle the completion of a download."""
        # Simulate stopping the thread (replace with actual logic)
        thread = self.threads[url]
        if thread:
            thread.quit()
            thread.wait()

        # Update the button to indicate completion
        button = self.elements[url]
        button.setText("Download complete. Download again?")

        # Change button color to #3c3c3c
        palette = button.palette()
        palette.setColor(QPalette.Button, QColor("#3c3c3c"))
        button.setPalette(palette)
        button.setAutoFillBackground(True)

        # Show a success message
        QMessageBox.information(self, "Success", "Channel downloaded successfully!")



# Main
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubeDownloaderApp()
    window.show()
    sys.exit(app.exec())

