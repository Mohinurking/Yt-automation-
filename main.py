import os
import json
import time
import random
import asyncio
import requests
import subprocess
import edge_tts
from google import genai
import openai

# Retrieve API keys securely from Environment Variables / Github Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

# Initialize Clients
client_gemini = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

client_openrouter = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
) if OPENROUTER_API_KEY else None

# Backup keywords pool for stock videos
BACKUP_KEYWORDS = [
    "deep space 4k", "black hole accretion", "spinning galaxy vertical", 
    "supernova explosion motion", "wormhole tunnel space", "neutron star cosmic", 
    "solar flare universe", "nebulas cinematic space", "event horizon dark", 
    "milky way vertical cosmos", "astronomy space exploration", "interstellar void"
]

used_video_ids = set()

def extract_json_from_text(text):
    """Cleans markdown formatting from response."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def generate_cosmology_storyboard(topic):
    """Generates storyboard with robust model fallbacks."""
    system_prompt = """
    You are an expert video producer for US Facebook Reels.
    Create a 60-second vertical (9:16) script about Cosmology & Space Mysteries.
    Target Audience: USA. Language: English. Tone: Atmospheric, cinematic, deep, mysterious.
    
    CRITICAL RULE: Each scene MUST have a unique, highly specific visual search keyword for stock videos.
    
    Return STRICTLY a JSON object with this structure (no extra markdown):
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
    
    # Updated Active Gemini & OpenRouter Models Pool
    models_to_try = [
        {"provider": "gemini", "model": "gemini-2.5-flash"},
        {"provider": "gemini", "model": "gemini-1.5-flash"},
        {"provider": "openrouter", "model": "google/gemma-2-9b-it:free"},
        {"provider": "openrouter", "model": "meta-llama/llama-3.1-8b-instruct:free"}
    ]
    
    total_cycles = 3
    
    for cycle in range(1, total_cycles + 1):
        print(f"\n--- Starting Model Cycle {cycle}/{total_cycles} ---")
        for model_info in models_to_try:
            provider = model_info["provider"]
            model_name = model_info["model"]
            
            try:
                print(f"  Attempting with {provider.upper()} model: {model_name}...")
                
                if provider == "gemini" and client_gemini:
                    response = client_gemini.models.generate_content(
                        model=model_name,
                        contents=f"{system_prompt}\n\n{user_prompt}",
                        config={"response_mime_type": "application/json"}
                    )
                    script_text = response.text
                
                elif provider == "openrouter" and client_openrouter:
                    response = client_openrouter.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ]
                    )
                    script_text = response.choices[0].message.content
                else:
                    continue
                
                clean_text = extract_json_from_text(script_text)
                storyboard = json.loads(clean_text)
                
                print(f"Success with {provider.upper()} model: {model_name} (Cycle {cycle})")
                return storyboard
                
            except Exception as e:
                print(f"  Failed with {model_name}: {e}")
                time.sleep(3)
                
    raise Exception("All AI models failed to generate content.")

async def generate_voiceover(text, output_file):
    """Generates voiceover using Edge TTS."""
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(output_file)

def fetch_unique_pexels_video(keyword, output_file):
    """Downloads guaranteed unique HD vertical space video clip from Pexels API."""
    global used_video_ids
    
    if not PEXELS_API_KEY:
        print("⚠️ Warning: PEXELS_API_KEY is missing!")
        return False

    headers = {"Authorization": PEXELS_API_KEY}
    search_terms = [keyword] + random.sample(BACKUP_KEYWORDS, len(BACKUP_KEYWORDS))
    
    for term in search_terms:
        page = random.randint(1, 8)
        url = f"[https://api.pexels.com/videos/search?query=](https://api.pexels.com/videos/search?query=){term}&orientation=portrait&per_page=15&page={page}"
        
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                videos = data.get("videos", [])
                
                random.shuffle(videos)
                
                for video in videos:
                    v_id = video.get("id")
                    if v_id not in used_video_ids:
                        video_files = video.get("video_files", [])
                        if not video_files:
                            continue
                            
                        hd_file = next((f for f in video_files if f.get("height", 0) >= 1280), video_files[0])
                        video_url = hd_file.get("link")
                        
                        print(f"  Downloading UNIQUE Pexels clip (ID: {v_id}) for query '{term}'...")
                        v_data = requests.get(video_url, timeout=30).content
                        with open(output_file, "wb") as f:
                            f.write(v_data)
                        
                        used_video_ids.add(v_id)
                        return True
        except Exception as e:
            print(f"  Fetch attempt failed for '{term}': {e}")
            
    print(f"❌ Could not find a unique video for '{keyword}', retrying default...")
    return False

def build_scene_assets(storyboard):
    """Builds audio and downloads unique stock video clips."""
    os.makedirs("output/videos", exist_ok=True)
    os.makedirs("output/audio", exist_ok=True)
    processed_scenes = []
    
    for scene in storyboard.get("scenes", []):
        scene_id = scene["scene_id"]
        keyword = scene.get("search_keyword", "deep space galaxy")
        narration = scene["narration_text"]
        
        print(f"\n--- [Processing Scene {scene_id}] ---")
        audio_path = f"output/audio/scene_{scene_id}.mp3"
        asyncio.run(generate_voiceover(narration, audio_path))
        
        video_path = f"output/videos/scene_{scene_id}.mp4"
        success = fetch_unique_pexels_video(keyword, video_path)
        
        if success:
            processed_scenes.append((scene_id, video_path, audio_path))
        else:
            print(f"Skipping scene {scene_id} due to video fetch issue.")
        
    return processed_scenes

def stitch_final_reel(processed_scenes):
    """Stitches unique video clips and audio into a final Reel using FFmpeg."""
    print("\nRendering final Reel with FFmpeg...")
    scene_outputs = []
    
    for scene_id, video_path, audio_path in processed_scenes:
        merged_scene_path = f"output/videos/merged_scene_{scene_id}.mp4"
        
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            merged_scene_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        scene_outputs.append(merged_scene_path)
        
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
    print(f"FINAL UNIQUE REEL CREATED: {final_output_path}")

def main():
    print("Initiating Autopilot Cosmology Reel Production Engine...")
    current_topic = "What happens if two supermassive black holes collide?"
    
    storyboard = generate_cosmology_storyboard(current_topic)
    os.makedirs("output", exist_ok=True)
    with open("output/storyboard.json", "w") as f:
        json.dump(storyboard, f, indent=2)
        
    processed_scenes = build_scene_assets(storyboard)
    if processed_scenes:
        stitch_final_reel(processed_scenes)
    else:
        print("❌ No scenes processed successfully. Video render skipped.")

    print("\nProcess Finished Successfully!")

if __name__ == "__main__":
    main()
