import subprocess
# from pytube import YouTube
    
def downloadFromYT(url, format_code = '270'):
    command = ['yt-dlp', '-F', url]
    try:
        output = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print(output.stdout.decode())
    except subprocess.CalledProcessError as e:
        print("Error listing formats:", e.stderr.decode())
        return None
    
    command = [
        'yt-dlp',
        '-f', format_code,
        '--merge-output-format', 'mp4',
        '-o', 'video_downloaded',
        url
    ]

    try:
        subprocess.run(command, check=True)
        print(f"Downloaded video in format {format_code}.")
    except subprocess.CalledProcessError as e:
        print(f"Error downloading the video in format {format_code}:", e.stderr.decode())
