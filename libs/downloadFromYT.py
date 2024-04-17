import subprocess
from datetime import datetime
# from pytube import YouTube

def downloadFromYT(url, format_code='270'):
    command = ['yt-dlp', '-F', url]
    try:
        output = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print(output.stdout.decode())
    except subprocess.CalledProcessError as e:
        print("Error listing formats:", e.stderr.decode())
        return None
    
    # Generate a dynamic filename based on the current date and time
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"video_downloaded_{timestamp}.mp4"
    
    command = [
        'yt-dlp',
        '-f', format_code,
        '--merge-output-format', 'mp4',
        '-o', filename,
        url
    ]

    try:
        subprocess.run(command, check=True)
        print(f"Downloaded video as {filename} in format {format_code}.")
    except subprocess.CalledProcessError as e:
        print(f"Error downloading the video in format {format_code}:", e.stderr.decode())
