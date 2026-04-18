# ✂️ ClipForge

An AI-powered video clip generator. Paste any YouTube, TikTok, or Instagram URL and get viral-ready short clips — powered by Gemini 1.5 Pro.

## How it works

1. **Download** — `yt-dlp` pulls the video from any supported URL
2. **Analyze** — Gemini 1.5 Pro watches the video and identifies the best segments with virality scores
3. **Cut** — `moviepy` slices the video at the exact timestamps Gemini identified
4. **Download** — You get the clips directly from the Streamlit UI

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

You also need `ffmpeg` installed on your system:
- **Windows**: Download from https://ffmpeg.org/download.html and add to PATH
- **Mac**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

### 2. Get a Gemini API key

Go to [aistudio.google.com](https://aistudio.google.com) and create a free API key.

### 3. Run the app

```bash
streamlit run app.py
```

Enter your Gemini API key in the UI (or add it to a `.env` file).

## Project structure

```
clipper/
├── app.py              # Streamlit UI
├── downloader.py       # yt-dlp video download
├── analyzer.py         # Gemini clip detection + scoring
├── cutter.py           # moviepy video cutting
├── requirements.txt
└── .env.example
```

## Supported platforms

Any platform supported by `yt-dlp`:
- YouTube
- TikTok
- Instagram Reels
- Twitter/X
- Facebook
- Vimeo
- And 1000+ more
