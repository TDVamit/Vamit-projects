import os
import re
import json
import requests
import time
from PySide6.QtWidgets import QCheckBox, QScrollArea, QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QMessageBox,QHBoxLayout
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from PySide6.QtCore import QThread, Signal, QObject , Qt
import win32com.client
import yt_dlp
import urllib.parse
import shutil
from datetime import date as dt,datetime
import xml.etree.ElementTree as ET
import subprocess
from pymediainfo import MediaInfo


now = datetime.now()
date_time_str = now.strftime("%Y-%m-%d %H:%M:%S") 
# Function to sanitize directory name
# Function to sanitize directory and file names
def sanitize_directory_name(name):
    # Replace invalid characters, including commas, with underscores
    name = re.sub(r'[<>:"/\\|?*\t]', '_', name)
    name = re.sub(r'[^\w\-. ]', '_', name)
    # Trim any extra whitespace characters
    name = name.strip()
    # If the name exceeds a reasonable length, truncate it
    return name[:150]

# Session with retries and timeouts
def create_session(retries=4, backoff_factor=0.3):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(500, 502, 503, 504)
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def requests_session_with_retries(retries=5, backoff_factor=1, status_forcelist=(500, 502, 504)):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

class DownloadWorker(QObject):
    progress = Signal(int,int, int)  # Signal to emit progress (current, total)
    status = Signal(int,str)  # Signal to emit status updates
    finished = Signal(int)  # Signal to notify when download is done

    def __init__(self,course_id, folder_id,parent_dir, headers ):
        super().__init__()
        self.headers = headers
        self.token_index = 0
        self.log_file = 'logs.txt'


    def fetch_folder_contents(self, course_id, folder_id, parent_dir, retry_attempts=5):
         # Regex to capture positive/negative numbers at the end of the name
        number_pattern = re.compile(r'(-?\d+)(?=\.\w+$|$)')
        # Regex to capture unique IDs in the format (id) at the end of the name
        # Updated pattern to capture unique IDs in the format '=id' at the end of the name
        id_pattern = re.compile(r'=*\(([^)]+)\)(?=\.\w+$|$)')

        folder_names = {}

        # Walk through all the files and folders in the directory
        for item_name in os.listdir(parent_dir):
            item_path = os.path.join(parent_dir, item_name)
            value = None  # Default value if no number or ID is found
            
            # For files, remove the extension first
            if os.path.isfile(item_path):
                name_without_extension, _ = os.path.splitext(item_name)
                name_without_extension, _ = os.path.splitext(name_without_extension)
                # Try to match a number at the end
                number_match = number_pattern.search(name_without_extension)
                # Try to match a unique ID (in parentheses) at the end
                id_match = id_pattern.search(name_without_extension)
            else:
                # For folders, directly search for a number
                number_match = number_pattern.search(item_name)
                id_match = None  # Folders don't have IDs, only numbers

            if number_match:
                value = int(number_match.group(1))  # Extract the number
            elif id_match:
                value = id_match.group(1)  # Extract the unique ID
            
            if value != None:
                folder_names[value] = item_path
        
        try:
            url = f'https://api.classplusapp.com/v2/course/content/get?courseId={course_id}&folderId={folder_id}&storeContentEvent=false&isDiy=1&offset=0&limit=10&isSubContent=false'
            response = requests.get(url, headers=self.headers)
            response_data = response.json()
            if response_data['status'] != 'success':
                raise Exception(f"Failed to fetch folder ID {folder_id}, status not success")
            
            folders_data = response_data['data']['courseContent']
            if len(folders_data) >= 10: 
                fetchmore = True
            else:
                fetchmore = False
            offset = 10
            while(fetchmore):
                url = f'https://api.classplusapp.com/v2/course/content/get?courseId={course_id}&folderId={folder_id}&storeContentEvent=false&isDiy=1&offset={offset}&limit=10&isSubContent=false'
                response = requests.get(url, headers=self.headers)
                response_data = response.json()
                if response_data['status'] != 'success':
                    raise Exception(f"Failed to fetch folder ID {folder_id}, status not success,{response_data}")
                print("Fetching ....",course_id,folder_id)
                new_folders_data = response_data['data']['courseContent']
                folders_data.extend(new_folders_data)
                offset += 10
                if len(new_folders_data) < 10:
                    fetchmore = False
                    
            if retry_attempts == 5:
                self.status.emit(course_id,f'0/{len(folders_data)}')
                

        except Exception as e:
            error = f"{date_time_str}-Error fetching folder contents for folder ID {folder_id} folder paths {parent_dir}: {str(e)}"
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(error + '\n')
            print(error)
            if retry_attempts > 0:
                time.sleep(2)
                self.fetch_folder_contents(course_id, folder_id, parent_dir, retry_attempts=retry_attempts-1)
            else:
                current_progress = 1
                self.progress.emit(course_id,current_progress,1)
                self.finished.emit(course_id)
                print(f"Failed to fetch folder ID {folder_id} after retrying. Moving on.")
            # Use a ThreadPoolExecutor to parallelize video downloads
        
        current_progress = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # A dictionary to hold futures for video downloads
            download_futures = []
            for folder in folders_data:
                try:
                    if 'format' in folder:
                        # Parallelize file download
                        future = executor.submit(self.download_file, folder, parent_dir, folder_names)
                        download_futures.append(future)
                    elif 'resources' in folder:
                        folder_name = sanitize_directory_name(folder['name'])
                        subfolder_dir = f'{parent_dir}/{folder_name} {folder['id']}'
                        
                        if not os.path.exists(subfolder_dir):
                            if not folder['id'] in folder_names:
                                os.makedirs(subfolder_dir)
                            else:
                                os.rename(folder_names[folder['id']],subfolder_dir)
                                folder_names.pop(folder['id'])
                        else:
                            folder_names.pop(folder['id'])
                        # Recursively fetch subfolder contents
                        self.fetch_folder_contents(course_id, folder['id'], subfolder_dir, 5)
                    elif 'vidKey' in folder and 'contentHashId' in folder and 'uuid' in folder:
                        future = executor.submit(self.download_drm_video_and_create_shortcut,folder,parent_dir,folder_names)
                        download_futures.append(future)
                    elif 'vidKey' in folder and 'contentHashId' in folder :
                        future = executor.submit(self.download_video, folder, parent_dir, folder_names)
                        download_futures.append(future)
                    
                except Exception as e:
                    error = f"{date_time_str}-Error at fetching or Downloading file {folder['name']}:{str(e)}"
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(error + '\n')
                    print(error)

            # Wait for all downloads to complete
            for future in concurrent.futures.as_completed(download_futures):
                current_progress += 1
                self.progress.emit(course_id, current_progress, len(folders_data))
                future.result()  # This will raise any exceptions that occurred during download
        self.finished.emit(course_id)

    def download_file(self, folder, parent_dir,folder_names, retry_attempts=5, backoff_factor=1):
        try:
            url = folder['url']
            original_filename = url.split("/")[-1]
            file_extension = os.path.splitext(original_filename)[1]
            folderid = os.path.splitext(original_filename)[0]
            filename = sanitize_directory_name(folder['name']) + f" =({folderid}){file_extension}"
            new_filename = os.path.abspath(f'Downloads/{folderid}{file_extension}')
            temp_filename = new_filename+".temp"
            shortcut_path = f'{parent_dir}/{filename}.lnk'

            if os.path.exists(new_filename):
                return

            else:
                loop = True
                times = 0
                while loop:
                    if times == 7:
                        os.remove(temp_filename)
                    print("waiting for file delete...",temp_filename)
                    time.sleep(2)
                    if not os.path.exists(temp_filename):
                        loop = False
                    times +=1

            if not os.path.exists(temp_filename) and not os.path.exists(new_filename):
                with open(temp_filename, "w") as file:
                    file.write("temp")

        except Exception as e:
            error = f"{date_time_str}-Failed to name file: {str(e)}"
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(error + '\n')
            print(error)
        if not os.path.exists(new_filename):
            if not folderid in folder_names:            
                try:
                    session = requests_session_with_retries(retry_attempts, backoff_factor)
                    response = session.get(url, stream=True)  # Stream response to download in chunks

                    if response.status_code == 200:
                        with open(new_filename, 'wb') as f:
                            f.write(response.content)
                        self.create_shortcut(new_filename,shortcut_path)
                    else:
                        error = f"{date_time_str}-Failed to download file: {url}"
                        with open(self.log_file, 'a', encoding='utf-8') as f:
                            f.write(error + '\n')
                        print(error)
                except Exception as e:
                    error = f"{date_time_str}-Error downloading file: {str(e)}"
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(error + '\n')
                    print(error)
            else:
                try:
                    os.rename(folder_names[folderid], shortcut_path)
                except Exception as e:
                    error = f"{date_time_str}-Error at renaming and poping file : {str(e)}"
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(error + '\n')
                    print(error)
        else:
            self.create_shortcut(new_filename,shortcut_path)
            
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

    def get_video_duration(self,video_path):

        """Returns the duration of the video in seconds."""
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        try:
            return float(result.stdout.strip())
        except ValueError:
            return None

    def time_str_to_seconds(self,time_str):
        """Converts HH:MM:SS time string to total seconds."""
        h, m, s = map(int, time_str.split(":"))
        return h * 3600 + m * 60 + s
    
    def is_video_shorter(self,video_path, duration_str):
        """Checks if the video is shorter than the given duration string."""
        video_duration = self.get_video_duration(video_path)
        if video_duration is None:
            return True  # Error in fetching duration
        timeint = self.time_str_to_seconds(duration_str)
        if -100 <= (video_duration - timeint) <= 100:
            return False
        else:
            print(video_duration,timeint)
            return True

        
    
    def download_video(self,folder, parent_dir,folder_names):
        vidKey = folder['vidKey']
        hashid = folder['contentHashId']
        if hashid == None:
            return
        hashid = urllib.parse.quote(hashid, safe='')
        name = sanitize_directory_name(folder['name'])
        uuid = folder['uuid'] if 'uuid' in folder else "" 
        shortcut_name = f"{name}=({vidKey}).mp4.lnk"  # Shortcut file format
        shortcut_path = os.path.join(parent_dir, shortcut_name) # Full shortcut path
        download_path = os.path.join(os.path.abspath('Downloads'), f'{vidKey}.mp4')
        duration = folder['duration']

        try:
            if os.path.exists(download_path):
                print("video already found...",vidKey)
                if self.is_video_shorter(download_path, duration):
                    error = f"{date_time_str}-shorter video found: {shortcut_path},{vidKey}"
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(error + '\n')
                    print(error)
                    os.remove(download_path)
                else:
                    if not(os.path.exists(shortcut_path)):
                        self.create_shortcut(download_path, shortcut_path)
                        return
            else:
                error = f"{date_time_str}-no video found: {shortcut_path},{vidKey}"
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(error + '\n')
                print(error)
            
        except Exception as e:
            error = f"{date_time_str}-Error at poping item from dict : {shortcut_path},{vidKey},{str(e)}"
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(error + '\n')
            print(error)


        if 'isAgora' in folder:
            url = f'https://api.classplusapp.com/cams/uploader/video/jw-signed-url?liveSessionId={hashid}&isAgora={folder['isAgora']}'
        else:
            return
            url = f'https://api.classplusapp.com/cams/uploader/video/jw-signed-url?contentId={hashid}'
            
        if uuid == "":
            retry_request = True
            while retry_request:
                tokens = [] #place your used based tokens here
                if self.token_index > len(tokens) - 1:
                    retry_request = False


                local_headers = {
                    "accept": "application/json, text/plain, */*",
                    "accept-encoding": "gzip, deflate, br, zstd",
                    "accept-language": "en",
                    "origin": "https://learn.mathscare.com",
                    "priority": "u=1, i",
                    "referer": "https://learn. mathscare.com/",
                    "region": "IN",
                    "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="132", "Google Chrome";v="132"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "cross-site",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
                    "x-access-token" : tokens[self.token_index]
                }

                response = requests.get(url, headers=local_headers)
                if response.status_code != 200:
                    self.token_index += 1
                    print(response.text)
                    if not retry_request:
                        error = f"{date_time_str}-Failed to retrieve M3U8 URL from API: {response.text}"
                        with open(self.log_file, 'a', encoding='utf-8') as f:
                            f.write(error + '\n')
                        raise Exception(f"Failed to retrieve M3U8 URL from API: {response.text}")
                else:
                    retry_request = False
                    error = f"{date_time_str}-Failed to retrieve M3U8 URL from API: {response.text}"
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(error + '\n')
                    print(error)

            
            data = response.json()    
            m3u8_url = data.get('url')
            if not m3u8_url:
                error = f"{date_time_str}-No M3U8 URL found in API response : {response.text}"
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(error + '\n')
                raise Exception(error)
            self.download_and_create_shortcut('Downloads',vidKey,shortcut_path,m3u8_url)


    
    def run_command(self,command):
        """Runs a shell command and prints its output."""
        try:
            result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(result.stdout.decode())
        except subprocess.CalledProcessError as e:
            error = f"{date_time_str}-Error running command: {command}\n{e.stderr.decode()}"
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(error + '\n')
            print(error)

    def get_video_resolution(self,video_file):
        try:
            media_info = MediaInfo.parse(video_file)
            for track in media_info.tracks:
                if track.track_type == "Video":
                    return track.width, track.height
            error = f"{date_time_str}-No video stream found in manifest"
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(error + '\n')
            raise ValueError("No video stream found.")
        except Exception as e:
            error = f"{date_time_str}-Error getting video resolution from manifest: {str(e)}"
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(error + '\n')
            print(error)
            return None

    def parse_manifest(self,mpd_file):
        root = ET.fromstring(mpd_file.text)
        """Parse the MPD content and extract KID and media filenames."""
        # Namespace mapping to avoid long URIs
        ns = {'ns': 'urn:mpeg:dash:schema:mpd:2011', 'cenc': 'urn:mpeg:cenc:2013'}
        
        
        media_info = {}  # List to store media info (type, filename, KID)
        
        # Iterate over AdaptationSets
        for adaptation_set in root.findall('.//ns:AdaptationSet', ns):
            content_type = adaptation_set.get('contentType')
            # Find ContentProtection with cenc:default_KID
            ContentProtection = adaptation_set.find('.//ns:ContentProtection', ns)
            # print(ContentProtection)
            kid_element = ContentProtection.attrib['{urn:mpeg:cenc:2013}default_KID'].replace('-', '')
            if kid_element is not None:
                kid = kid_element
            else:
                error = f"{date_time_str}-Warning: No 'cenc:default_KID' found for {content_type} adaptation set."
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(error + '\n')
                print(error)
                continue
            
            if content_type == "video":
                if adaptation_set.get('maxWidth') is not None:
                    details = f'{adaptation_set.get('maxWidth')}x{adaptation_set.get('maxHeight')}'
                else :
                    details = f'{adaptation_set.get('width')}x{adaptation_set.get('height')}'
                media_info[details] = kid
            else:
                media_info["audio"] = kid
        
        return media_info
    
    def download_drm_video_and_create_shortcut(self,folder,parent_dir,folder_names):
        if folder['uuid'] == "":
            self.download_video(folder,parent_dir,folder_names)
            return
        video_folder = 'Downloads'
        vidname = folder['vidKey']
        hashid = folder['contentHashId']
        if hashid == None:
            return
        hashid = urllib.parse.quote(hashid, safe='')
        name = sanitize_directory_name(folder['name'])
        shortcut_name = f"{name}=({vidname}).mp4.lnk"
        download_name = f"{name}=({vidname}).mp4"
        shortcut_path = os.path.join(parent_dir, shortcut_name)
        download_path = os.path.join(os.path.abspath('Downloads'), download_name)
        duration = folder['duration']

        try:
            if os.path.exists(download_path):
                print("video already found...",vidname)
                if self.is_video_shorter(download_path, duration):
                    error = f"{date_time_str}-shorter video found: {shortcut_path},{vidname}"
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(error + '\n')
                    print(error)
                    os.remove(download_path)
                else:
                    if not(os.path.exists(shortcut_path)):
                        self.create_shortcut(download_path, shortcut_path)
                        return
            else:
                error = f"{date_time_str}-no video found: {shortcut_path},{vidname}"
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(error + '\n')
                print(error)
            
        except Exception as e:
            error = f"{date_time_str}-Error at poping item from dict : {shortcut_path},{vidname},{str(e)}"
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(error + '\n')
            print(error)

        url_api = f'https://api.classplusapp.com/cams/uploader/video/jw-signed-url?contentId={hashid}'
        
        internal_folder = os.path.join(video_folder,vidname)

        if not os.path.exists(os.path.join(video_folder, f"{vidname}.mp4")):
            try:
                if not os.path.exists(video_folder):
                    os.makedirs(video_folder)
                if not os.path.exists(internal_folder):
                    os.makedirs(internal_folder)
                else:
                    loop = True
                    times = 0
                    while loop:
                        if times == 20:
                            shutil.rmtree(internal_folder)
                            os.makedirs(internal_folder)
                            loop = False
                        print("Waiting for drm delete...",internal_folder)
                        time.sleep(3)
                        if not os.path.exists(internal_folder):
                            loop = False
                        times +=1
            except Exception as e :
                error = f"{date_time_str}-Error at Creating Download video Folder :{str(e)}"
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(error + '\n')
                print(error)

            video_file = os.path.join(internal_folder, f"{vidname}")
            tries = 5
            while tries:
                url_results = None
                try:
                    CDRM_API = 'https://cdrm-project.com/api/decrypt'

                    local_headers_drm = {
                        "accept": "*/*",
                        "accept-encoding": "gzip, deflate, br, zstd",
                        "accept-language": "en-US,en;q=0.9",
                        "access-control-request-headers": "content-type",
                        "access-control-request-method": "POST",
                        "origin": "https://classplusapp.com",
                        "priority": "u=1, i",
                        "referer": "https://classplusapp.com/",
                        "sec-fetch-dest": "empty",
                        "sec-fetch-mode": "cors",
                        "sec-fetch-site": "cross-site",
                        "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
                        'x-access-token' : self.headers['x-access-token']
                    }
                    nolicence = False
                    url_results = requests.get(url_api,headers = local_headers_drm)
                    if not('drmUrls' in url_results.json()):
                        print("Only url found:",url_results.json()["url"])
                        self.download_video(folder,parent_dir,folder_names)
                        return
                    
                    elif not('licenseUrl' in url_results.json()["drmUrls"]):
                        print("Only DRM url found:",url_results.json()["drmUrls"]['manifestUrl'])
                        nolicence = True
                    
                    manifesturl = url_results.json()["drmUrls"]['manifestUrl']
                    
                    if not nolicence:
                        licenceurl = url_results.json()["drmUrls"]['licenseUrl']
                        manifest_result= requests.get(manifesturl,headers = local_headers_drm)
                        key_info = self.parse_manifest(manifest_result)

                        xml = ET.fromstring(manifest_result.text)
                        namespaces = {
                            '': 'urn:mpeg:dash:schema:mpd:2011',  # Default namespace
                            'cenc': 'urn:mpeg:cenc:2013'
                        }
                        pssh_elements = xml.findall('.//cenc:pssh', namespaces)
                        pssh = pssh_elements[-2].text.strip()

                        print("Downloading video and audio files...")
                        manifesturl = f'"{manifesturl}"'
                        command = f"yt-dlp --allow-unplayable -f m4a,mp4 -o {video_file}_encrypted.%(ext)s {manifesturl}"
                        self.run_command(command)


                        json_data = {
                            'pssh': pssh,
                            'licurl': licenceurl,
                            'headers': str(local_headers_drm),
                        }

                        resolution = self.get_video_resolution(f"{video_file}_encrypted.mp4")
                        video_resolution = f'{resolution[0]}x{resolution[1]}'

                        decryption_results = requests.post(CDRM_API,headers=local_headers_drm, json=json_data)

                        if video_resolution in key_info:
                            video_key = key_info[video_resolution]
                        else:
                            if list(key_info)[0] != 'audio':
                                video_key = key_info[list(key_info)[0]]
                            else:
                                video_key = key_info[list(key_info)[1]]

                        audio_key = key_info['audio']
                        keys = decryption_results.json()["message"].split('\n')
                        video_decryption_key = None
                        for key in keys:
                            if video_key in key:
                                video_decryption_key = key
                            elif audio_key in key:
                                audio_decryption_key = key
                            # Step 3: Decrypt files
                        if video_decryption_key == None:
                            print("Video Key Not Found... - Resolution:",resolution," key info:",key_info,' keys:',keys)
                            video_decryption_key = decryption_results.json()["message"].split('\n')[0]
                        if audio_decryption_key == None:
                            print("Audio Key Not Found... - Resolution:",resolution," key info:",key_info,' keys:',keys)
                            audio_decryption_key = decryption_results.json()["message"].split('\n')[1]
                        decrypted_mp4 = f"{video_file}_decrypted.mp4"
                        decrypted_m4a = f"{video_file}_decrypted.m4a"
                        print("Decrypting MP4 file...")
                        self.run_command(f"mp4decrypt --key {video_decryption_key} {video_file}_encrypted.mp4 {decrypted_mp4}")

                        print("Decrypting M4A file...")
                        self.run_command(f"mp4decrypt --key {audio_decryption_key} {video_file}_encrypted.m4a {decrypted_m4a}")

                        # Step 4: Merge video and audio
                        output_file = f"{video_file}.mp4"
                        print("Merging decrypted video and audio...")
                        self.run_command(f"ffmpeg -i {decrypted_mp4} -i {decrypted_m4a} -c:v copy -c:a copy {output_file}")
                    else:
                        command = f'yt-dlp -o "{video_file}.mp4" "{manifesturl}"'
                        self.run_command(command)

                    print(f"Process completed. Output file: {f"{video_file}.mp4"}")
                    shutil.move(f"{video_file}.mp4",video_folder)
                    tries = 0
                except Exception as e:
                    error = f"{date_time_str}-Error Downloading DRM Video :{str(e)},{url_results.json()}"
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(error + '\n')
                    print(error)
                    time.sleep(1)
                    tries -=1

        if os.path.exists(internal_folder):
            shutil.rmtree(internal_folder)

        if not os.path.exists(shortcut_path):
            self.create_shortcut(os.path.join(video_folder, f"{vidname}.mp4"), shortcut_path)


   
    def download_and_create_shortcut(self, video_folder,vidname, shortcut_path, m3u8_url):
        # Ensure the video_folder and parent_folder exist
        try:
            if not os.path.exists(video_folder):
                os.makedirs(video_folder)
            internal_folder = os.path.join(video_folder,vidname)
            if not os.path.exists(internal_folder):
                os.makedirs(internal_folder)
            else:
                loop = True
                times = 0
                while loop:
                    if times == 20:
                        shutil.rmtree(internal_folder)
                        os.makedirs(internal_folder)
                        loop = False
                    print("waiting for video...",internal_folder)
                    time.sleep(3)
                    if not os.path.exists(internal_folder):
                        loop = False
                    times +=1
        except Exception as e :
            error = f"{date_time_str}-Error at Creating Download video Folder :{str(e)} at {video_folder}"
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(error + '\n')
            print(error)
            
            
        # Set the full path to the video file
        video_file = os.path.join(internal_folder, f"{vidname}.mp4")

        if not os.path.exists(os.path.join(video_folder, f"{vidname}.mp4")):
            # FFmpeg command to download and convert the video with target resolution
            try:
                ydl_opts = {
                'format': 'best',
                'outtmpl':video_file,
                'http_headers':self.headers,
                'verbose': True, 
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([m3u8_url])
                shutil.move(video_file,video_folder)
            except Exception as e:
                error = f"{date_time_str}-Error at Download video:{str(e)} at {video_folder}"
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(error + '\n')
                print(error)


        if os.path.exists(internal_folder):
            shutil.rmtree(internal_folder)
        # Create a shortcut in the parent folder with the format pathname=(vidname).mp4
        
        if not os.path.exists(shortcut_path):
            self.create_shortcut(os.path.join(video_folder, f"{vidname}.mp4"), shortcut_path)

        # After downloading the video and creating the shortcut, generate the batch file
        

    def create_shortcut(self, target, shortcut_path):
        try:
            shortcut_path = os.path.abspath(shortcut_path)
            if os.path.exists(shortcut_path):
                return
            target = os.path.abspath(target)
            linkname = os.path.basename(shortcut_path)
            temp_shortcut_name = os.path.join(os.path.dirname(target),linkname)
            relative_target = os.path.relpath(target, start=os.path.dirname(shortcut_path))
            
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortcut(temp_shortcut_name)
            
            # Set the full absolute path for TargetPath
            shortcut.TargetPath = target  # The full absolute path to the target file
            shortcut.WorkingDirectory = os.path.dirname(target)  # The directory of the target file
            shortcut.RelativePath = relative_target  # Set the relative path for better path handling

            shortcut.save()
            shutil.move(temp_shortcut_name,os.path.dirname(shortcut_path))
        except Exception as e:
                error = f"{date_time_str}-Failed to create shortcut file: {str(e)} file paths from {temp_shortcut_name} to {target}"
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(error + '\n')
                print(error)
                return

        

  
class CourseApp(QWidget):
    def __init__(self):
        super().__init__()
        self.selectallcheck = True
        self.log_file = 'logs.txt'
        self.token = ''
        self.tries = 5
        self.sheetappurl = 'https://script.google.com/macros/s/yoursheetcode/exec' # sheet url for token update
        self.detailsurl = 'https://script.google.com/macros/s/yoursheetcode/exec' # sheet url to place current courses details
        self.session = create_session()  # Using a session with retry mechanism
        self.get_token()
        self.headers = {
            'x-access-token': self.token,
            'accept': 'application/json, text/plain, */*',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'en-US,en;q=0.9',
            'api-version': '51',
            'origin': 'https://classplusapp.com',
            'referer': 'https://classplusapp.com/',
            'region': 'IN',
            'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
        }
        self.threads = {}
        self.executor = ThreadPoolExecutor(max_workers=1)  # Thread pool for parallel execution
        
        self.setWindowTitle("Course Data")
        self.setGeometry(100, 100, 600, 400)

        self.layout = QVBoxLayout()

        self.fetch_button = QPushButton("Fetch Courses")
        self.fetch_button.clicked.connect(self.fetch_courses)
        self.layout.addWidget(self.fetch_button)

        self.buttonlayout = QHBoxLayout()
        self.selectallcheckbox = QCheckBox("Select All")
        self.selectallcheckbox.stateChanged.connect(self.selectall)
        self.buttonlayout.addWidget(self.selectallcheckbox)
        self.update_button = QPushButton("Update Selected Courses")
        self.update_button.setMinimumWidth(450)
        self.update_button.clicked.connect(self.start_exec)
        self.buttonlayout.addWidget(self.update_button)
        self.layout.addLayout(self.buttonlayout)
        self.update_button.setVisible(False)
        self.selectallcheckbox.setVisible(False)

        self.mainscrollareaframe = QWidget()
        self.mainscrollareaLayout = QVBoxLayout(self.mainscrollareaframe)
        self.mainscrollarea = QScrollArea()
        self.mainscrollarea.setWidget(self.mainscrollareaframe)
        self.mainscrollarea.setWidgetResizable(True)
        self.layout.addWidget(self.mainscrollarea)
        self.setLayout(self.layout)

    def get_token(self):
        try:
            response = self.session.get(self.sheetappurl, timeout=5)
            data = response.json()
            self.token = data['Token']
        except Exception as e:
            error = f"{date_time_str}-Error loading token from sheet: {str(e)}"
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(error + '\n')
            print(error)
            QMessageBox.critical(self, "Error", "Failed to load data from the Google Sheet.")

    def update_token(self):
        data = {'Token': self.token}
        response = requests.post(self.sheetappurl, json=data)
        if response.status_code == 200:
            print("Token updated successfully.")
        else:
            error = f"{date_time_str}-Failed to update token. Status code: {response.status_code}"
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(error + '\n')
            print(error)

    def extract_token(self):
        os.system("taskkill /f /im chrome.exe")
        chrome_profile_path = r"C:\\Users\\gpsir\\AppData\\Local\\Google\\Chrome\\User Data"
        profile_directory = "Profile 10"

        chrome_options = Options()
        chrome_options.add_argument(f"user-data-dir={chrome_profile_path}")
        chrome_options.add_argument(f"--profile-directory={profile_directory}")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Suppress "Chrome is being controlled by automated test software"
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        caps = DesiredCapabilities.CHROME.copy()
        caps['goog:loggingPrefs'] = {'performance': 'ALL'}
        chrome_options.capabilities.update(caps)

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

        try:
            driver.get("https://classplusapp.com/diy/courses/course-list")
            time.sleep(5)

            logs = driver.get_log('performance')
            self.token = None

            for entry in logs:
                log = entry['message']
                if 'Network.requestWillBeSent' in log and 'orgDetails' in log:
                    log_json = json.loads(log)['message']['params']['request']['headers']
                    if 'x-access-token' in log_json:
                        self.token = log_json['x-access-token']
                        self.update_token()
                        self.headers = {
                            'x-access-token': self.token,
                            'accept': 'application/json, text/plain, */*',
                            'accept-encoding': 'gzip, deflate, br, zstd',
                            'accept-language': 'en-US,en;q=0.9',
                            'api-version': '51',
                            'origin': 'https://classplusapp.com',
                            'referer': 'https://classplusapp.com/',
                            'region': 'IN',
                            'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
                            'sec-ch-ua-mobile': '?0',
                            'sec-ch-ua-platform': '"Windows"',
                            'sec-fetch-dest': 'empty',
                            'sec-fetch-mode': 'cors',
                            'sec-fetch-site': 'same-site',
                            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
                        }
                        break

            if self.token is None:
                print("x-access-token not found")
                driver.quit()
                exit()
        finally:
            driver.quit()

    def remove_temp_files(self, folder_path):
        folder_path = os.path.abspath(folder_path)
        # Traverse through all directories and files in the given folder
        for root, dirs, files in os.walk(folder_path, topdown=False):
            # Remove .temp files in the current directory
            for file_name in files:
                if file_name.endswith('.temp'):
                    file_path = os.path.join(root, file_name)
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        error = f"{date_time_str}-Error deleting {file_path}: {str(e)}"
                        with open(self.log_file, 'a', encoding='utf-8') as f:
                            f.write(error + '\n')
                        print(error)
            
            # Remove subdirectories
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    shutil.rmtree(dir_path)
                except Exception as e:
                    error = f"{date_time_str}-Error deleting {dir_path}: {str(e)}"
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(error + '\n')
                    print(error)

    def fetch_courses(self):
        self.remove_temp_files('Downloads')
        self.CourseIds = []
        self.TotalFile = []
        self.TotalVideo = []
        self.LastUpdate = []
        try:
            response = requests.get(self.detailsurl)
            data = response.json()
            for i in range(len(data["CourseId"])):
                CourseId = data["CourseId"][i]
                TotalFiles = data["TotalFiles"][i]
                TotalVideos = data["TotalVideos"][i]
                LastUpdated = data["LastUpdated"][i]
                if CourseId:
                     self.CourseIds.append(int(CourseId))
                     self.TotalFile.append(int(TotalFiles))
                     self.TotalVideo.append(int(TotalVideos))
                     self.LastUpdate.append(LastUpdated)
            

            url = "https://api.classplusapp.com/v2/courses?offset=0&limit=10"
            response = self.session.get(url, headers=self.headers, timeout=10)
            response_data = response.json()
            if response_data['status'] != 'success':
                self.extract_token()
                self.tries -= 1
                self.fetch_courses()

            total_count = response_data['data']['totalCount']
            courses = response_data['data']['courses']

            future_remaining = self.executor.submit(self.fetch_remaining_courses, total_count-10)
            remaining_courses = future_remaining.result()
            courses.extend(remaining_courses)

            if not courses:
                error = "Failed to fetch all courses after retries."
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(error + '\n')
                raise Exception("Failed to fetch all courses after retries.")
            
            self.update_button.setVisible(True)
            self.selectallcheckbox.setVisible(True)
            self.futures = []
            self.elements = {}
            self.toupdatelist = []

            for course in courses:
                files = int(course["resources"]["files"])
                videos = int(course["resources"]["videos"])
                course_name = sanitize_directory_name(course['name']) + '_(' + str(course['id']) + ')'
                course_layout = QHBoxLayout()
                course_layout.setAlignment(Qt.AlignLeft)
                course_checkbox = QCheckBox()
                course_checkbox.stateChanged.connect(lambda state, i=course['id'] : self.toupdate(state,i))
                course_layout.addWidget(course_checkbox)
                if int(course['id']) in self.CourseIds:
                    index = self.CourseIds.index(int(course['id']))
                    file = self.TotalFile[index]
                    video = self.TotalVideo[index]
                    date = self.LastUpdate[index]
                    if file != files or video != videos :
                        course_checkbox.setChecked(True)

                else:
                    course_checkbox.setChecked(True)
                course_lable = QLabel(course_name[:250])
                course_layout.addWidget(course_lable)
                self.mainscrollareaLayout.addLayout(course_layout)
                self.elements[course['id']] = [course_layout,files,videos]

                if not os.path.exists('App Backup'):
                    os.makedirs('App Backup')
                    
                course_dir = f'App Backup/{course_name}'
                
                if not os.listdir('App Backup'):
                    os.makedirs(course_dir)
                else:
                    with os.scandir('App Backup') as entries:
                        for entry in entries:
                            # Check if it's a directory and contains course id
                            if entry.is_dir() and str(course['id']) in entry.name:
                                if not os.path.exists(course_dir):
                                    os.rename(entry.path, course_dir)
                            else:
                                if not os.path.exists(course_dir):
                                    os.makedirs(course_dir)
                self.futures.append((self.fetch_folder_contents, course['id'], 0, course_dir))

                
                if not course['id'] in self.CourseIds:
                    self.CourseIds.append(course['id'])
                    self.TotalFile.append(0)
                    self.TotalVideo.append(0)
                    self.LastUpdate.append(str(dt.today()))
            updated_data = {
                "CourseId" : self.CourseIds,
                "TotalFiles" : self.TotalFile,
                "TotalVideos" : self.TotalVideo,
                "LastUpdated" : self.LastUpdate
            }
            response = requests.post(self.detailsurl, json=updated_data)
            if response.status_code == 200:
                print("Data saved successfully.")
            else:
                print(f"Failed to save data. Status code: {response.status_code}")
        except Exception as e:
            error = f"{date_time_str}-An error occurred: {str(e)}"
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(error + '\n')
            print(error)
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
    
    def start_exec(self):
        for future in self.futures:
            if future[1] in self.toupdatelist :
                self.executor.submit(future[0],future[1],future[2],future[3])

    
    def toupdate(self, state, courseid):
        if state == 2:
            if not( courseid in self.toupdatelist ) :
                self.toupdatelist.append(courseid)
        else:
            self.toupdatelist.remove(courseid)
    
    def selectall(self):
        for value in self.elements.values():
            course_layout = value[0]
            checkbox = course_layout.itemAt(0).widget()
            checkbox.setChecked(self.selectallcheck)
        self.selectallcheck = not self.selectallcheck

    def fetch_remaining_courses(self, total_count):
        courses = []
        i = 0 if total_count%10 == 0 else 1
        times = int(total_count/10) + i
        for time in range(times):
            offset = 10+ 10*time
            url = f"https://api.classplusapp.com/v2/courses?offset={offset}&limit=10"
            response = self.session.get(url, headers=self.headers, timeout=10)
            response_data = response.json()
            if response_data['status'] != 'success':
                raise Exception("Failed to fetch remaining courses")
            courses.extend(response_data['data']['courses'])

        return courses

    # Track overall progress
    def fetch_folder_contents(self, course_id, folder_id, parent_dir):
        thread = QThread()
        self.elements[course_id].append(thread)
        worker = DownloadWorker(course_id, folder_id, parent_dir,self.headers)
        worker.moveToThread(thread)
        worker.progress.connect(self.update_progress)
        worker.status.connect(self.update_status)
        worker.finished.connect(self.download_complete)
        thread.started.connect(worker.fetch_folder_contents(course_id, folder_id, parent_dir))
        thread.start()

        self.threads[course_id] = (thread, worker)

    def update_status(self,courseid, progress):
        progresslable = QLabel(progress)
        self.elements[courseid][0].addWidget(progresslable)
    
    def update_progress(self,courseid,progress,total):
        widget_item = self.elements[courseid][0].itemAt(self.elements[courseid][0].count()-1)
        if widget_item is not None:
            widget_item.widget().setText(f"{progress}/{total}")

    def download_complete(self,courseid):
        widget_item = self.elements[courseid][0].itemAt(self.elements[courseid][0].count()-1)
        if widget_item is not None:
            widget = widget_item.widget()
            widget.deleteLater()
            self.elements[courseid][0].removeWidget(widget)
        if self.elements[courseid][0].count() == 2:
            index = self.CourseIds.index(courseid)
            self.TotalFile[index] = self.elements[courseid][1]
            self.TotalVideo[index] = self.elements[courseid][2]
            self.LastUpdate[index] = str(dt.today())
            updated_data = {
                "CourseId" : self.CourseIds,
                "TotalFiles" : self.TotalFile,
                "TotalVideos" : self.TotalVideo,
                "LastUpdated" : self.LastUpdate
            }
            response = requests.post(self.detailsurl, json=updated_data)
            if response.status_code == 200:
                print("Data saved successfully.")
            else:
                print(f"Failed to save data. Status code: {response.status_code}")
            ticklable = QLabel('✅')
            self.elements[courseid][0].addWidget(ticklable)
            thread = self.elements[courseid][3]
            thread.quit()
            thread.wait()
    
if __name__ == "__main__":
    app = QApplication([])

    window = CourseApp()
    window.show()

    app.exec()
