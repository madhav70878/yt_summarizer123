from fastapi import FastAPI, Query
from transformers import pipeline
from urllib.parse import urlparse, parse_qs
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import yt_dlp
import json

app = FastAPI()

# Extract video ID from URL
def extract_video_id(youtube_url: str):
    parsed_url = urlparse(youtube_url)
    if parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    elif parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        return parse_qs(parsed_url.query).get('v', [None])[0]
    return None

# Get transcript using yt-dlp
def get_transcript(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitlesformat': 'json3',
        'quiet': True,
    }
    

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            subtitles = info.get('subtitles') or info.get('automatic_captions')
            if not subtitles:
                return "Error: No subtitles found."

            # Prefer English
            if 'en' in subtitles:
                sub_url = subtitles['en'][0]['url']
            else:
                # fallback: use first available
                sub_url = list(subtitles.values())[0][0]['url']

            # Now download the subtitle file
            import requests
            response = requests.get(sub_url)
            response.raise_for_status()
            data = response.json()

            # Combine transcript texts
            transcript = " ".join([event['segs'][0]['utf8'] for event in data['events'] if 'segs' in event])
            return transcript
    except Exception as e:
        return f"Error fetching transcript: {str(e)}"

# Summarize transcript
def summarize_text(text):
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    chunks = [text[i:i + 1024] for i in range(0, len(text), 1024)]
    summary = ""
    for chunk in chunks:
        result = summarizer(chunk, max_length=150, min_length=40, do_sample=False)
        summary += result[0]['summary_text'] + " "
    return summary.strip()

# FastAPI endpoint
@app.get("/summarize")
def summarize_youtube_video(url: str = Query(..., description="YouTube video URL")):
    video_id = extract_video_id(url)
    if not video_id:
        return {"error": "Invalid YouTube URL."}
    
    transcript = get_transcript(video_id)
    if transcript.startswith("Error"):
        return {"error": transcript}
    
    summary = summarize_text(transcript)
    return {"summary": summary}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def get_index():
    return FileResponse("static/index.html")
