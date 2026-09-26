import os
import json
import time
import random
import asyncio
import requests
import subprocess
import edge_tts
from google import genai

# API Clients
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

# Comprehensive space keywords pool for variety
BACKUP_KEYWORDS = [
    "black hole animation", "galaxy spinning 4k", "supernova explosion",
    "wormhole space-time", "neutron star collision", "solar flare space",
    "cosmic nebula motion", "deep space stars", "event horizon black hole",
    "milky way core vertical", "space void dark", "astronomy cosmic dust",
    "hyperspace warp speed", "quasar light emission", "interstellar space travel"
]

# Track used video IDs to prevent repetition
used_video_ids = set()

def generate_cosmology_storyboard(topic):
    """Generates script using multiple backup Gemini models, cycling A-Z multiple times if needed."""
    system_prompt = """
    You are an expert video producer for US Facebook Reels.
    Create a 60-second vertical (9:16) script about Cosmology & Space Mysteries.
    Target Audience: USA. Language: English. Tone: Atmospheric, cinematic, deep, mysterious.
    
    CRITICAL RULE: Each scene MUST have a unique, highly specific visual search keyword for stock videos.
    Example keywords: "black hole accretion disk", "space warp grid", "galaxy collision animation", "cosmic ray explosion".
    
    Return STRICTLY a JSON object with this structure:
    {
      "project_name": "Cosmology_Reels",
      "topic": "string",
      "scenes": [
        {
          "scene_id": 1,
          "duration_seconds": 5,
          "narration_text": "Engaging hook line in English...",
          "search_keyword": "black hole accretion disk"
        }
      ]
    }
    """
    user_prompt = f"Generate a high-retention space documentary storyboard about: {topic}"
    
    # Backup models list in priority order
    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]
    
    total_cycles = 10  # ৪টি মডেল x ১০ সাইকেল = মোট ৪০ বার ট্রাই করবে
    
    for cycle in range(1, total_cycles + 1):
        print(f"\n🔄 --- Starting Model Cycle {cycle}/{total_cycles} ---")
        for model_name in models_to_try:
            try:
                print(f"  Attempting with model: {model_name}...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=f"{system_prompt}\n\n{user_prompt}",
                    config={"response_mime_type": "application/json"}
                )
                print(f"✅ Success with model: {model_name} (Cycle {cycle})")
                return json.loads(response.text)
            except Exception as e:
                print(f"  ⚠️ Failed with {model_name}: {e}")
                print("  Waiting 5 seconds before trying next model...")
                time.sleep(5)
                
    raise Exception("❌ All Gemini models failed across all full cycles. Quota might be completely exhausted.")

async def generate_voiceover(text, output_file):
    """Generates voiceover using Edge TTS."""
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(output_file)

def fetch_unique_pexels_video(keyword, output_file):
    """Downloads unique HD vertical space video clip from Pexels API."""
    global used_video_ids
    headers = {"Authorization": PEXELS_API_KEY}
    
    # Try the scene keyword first, then fallback to random backup keywords
    search_terms = [keyword] + random.sample(BACKUP_KEYWORDS, len(BACKUP_KEYWORDS))
    
    for term in search_terms:
        # Randomize page number to get different clips each run
        page = random.randint(1, 3)
        url = f"https://api.pexels.com/videos/search?query={term}&orientation=portrait&per_page=15&page={page}"
        
        try:
            res = requests.get(url, headers=headers, timeout=15)
            data = res.json()
            videos = data.get("videos", [])
            
            for video in videos:
                v_id = video.get("id")
                # Ensure this clip hasn't been used in current reel
                if v_id not in used_video_ids:
                    video_files = video.get("video_files", [])
                    # Find highest quality vertical file
                    hd_file = next((f for f in video_files if f.get("height", 0) >= 1280), video_files[0])
                    video_url = hd_file.get("link")
                    
                    print(f"  Downloading UNIQUE Pexels clip (ID: {v_id}) for '{term}'...")
                    v_data = requests.get(video_url, timeout=30).content
                    with open(output_file, "wb") as f:
                        f.write(v_data)
                    
                    used_video_ids.add(v_id)
                    return True
        except Exception as e:
            print(f"  Pexels fetch attempt failed for '{term}': {e}")
            
    return False

def build_scene_assets(storyboard):
    """Builds audio and downloads unique stock video clips for each scene."""
    os.makedirs("output/videos", exist_ok=True)
    os.makedirs("output/audio", exist_ok=True)
    
    processed_scenes = []
    
    for scene in storyboard.get("scenes", []):
        scene_id = scene["scene_id"]
        keyword = scene.get("search_keyword", "deep space galaxy")
        narration = scene["narration_text"]
        
        print(f"\n--- [Processing Scene {scene_id}] ---")
        
        # 1. Voiceover
        audio_path = f"output/audio/scene_{scene_id}.mp3"
        asyncio.run(generate_voiceover(narration, audio_path))
        
        # 2. Unique Video Clip
        video_path = f"output/videos/scene_{scene_id}.mp4"
        success = fetch_unique_pexels_video(keyword, video_path)
        
        if success:
            processed_scenes.append((scene_id, video_path, audio_path))
        
    return processed_scenes

def stitch_final_reel(processed_scenes):
    """Stitches unique video clips and audio into a final Reel using FFmpeg."""
    print("\n🎬 Rendering final Reel with FFmpeg...")
    scene_outputs = []
    
    for scene_id, video_path, audio_path in processed_scenes:
        merged_scene_path = f"output/videos/merged_scene_{scene_id}.mp4"
        
        # Trim/loop video precisely to match voiceover length
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            merged_scene_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        scene_outputs.append(merged_scene_path)
        
    # Concat all unique merged scene clips
    concat_list_path = "output/concat_list.txt"
    with open(concat_list_path, "w") as f:
        for path in scene_outputs:
            f.write(f"file '{os.path.abspath(path)}'\n")
            
    final_output_path = "output/final_cosmology_reel.mp4"
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        final_output_path
    ]
    subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"🎉 FINAL UNIQUE REEL CREATED: {final_output_path}")

def main():
    print("🚀 Initiating Autopilot Cosmology Reel Production Engine...")
    current_topic = "What happens if two supermassive black holes collide?"
    
    storyboard = generate_cosmology_storyboard(current_topic)
    os.makedirs("output", exist_ok=True)
    with open("output/storyboard.json", "w") as f:
        json.dump(storyboard, f, indent=2)
        
    processed_scenes = build_scene_assets(storyboard)
    if processed_scenes:
        stitch_final_reel(processed_scenes)
    
    print("\n✅ Process Finished Successfully!")

if __name__ == "__main__":
    main()
