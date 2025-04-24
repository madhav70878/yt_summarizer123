from fastapi import FastAPI, Query
from transformers import pipeline
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
app = FastAPI()

# Extract video ID from URL
def extract_video_id(youtube_url: str):
    parsed_url = urlparse(youtube_url)
    if parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    elif parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        return parse_qs(parsed_url.query).get('v', [None])[0]
    return None

# Get transcript
def get_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([entry['text'] for entry in transcript])
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