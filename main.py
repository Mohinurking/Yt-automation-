import os
import json
import time
import asyncio
import requests
import subprocess
import edge_tts
from google import genai

# Clients
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

def generate_cosmology_storyboard(topic):
    """Generates structured script and visual search keywords."""
    system_prompt = """
    You are an expert video producer for US Facebook Reels.
    Create a 60-second vertical (9:16) script about Cosmology & Space Mysteries.
    Target Audience: USA. Language: English. Tone: Atmospheric, cinematic, deep, mysterious.
    
    CRITICAL RULE: The first scene (0-3 seconds) MUST be an extremely engaging hook.
    DO NOT include any human psychology, dark human nature, or unrelated subjects.
    
    Return STRICTLY a JSON object with this structure:
    {
      "project_name": "Cosmology_Reels",
      "topic": "string",
      "scenes": [
        {
          "scene_id": 1,
          "duration_seconds": 5,
          "narration_text": "Engaging hook line in English...",
          "search_keyword": "black hole space animation"
        }
      ]
    }
    """
    user_prompt = f"Generate a high-retention space documentary storyboard about: {topic}"
    
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Requesting script from Gemini (Attempt {attempt})...")
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=f"{system_prompt}\n\n{user_prompt}",
                config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Error getting script: {e}")
            time.sleep(5)
    raise Exception("Failed to get storyboard script.")

async def generate_voiceover(text, output_file):
    """Generates voiceover using Edge TTS."""
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(output_file)

def fetch_pexels_video(keyword, output_file):
    """Downloads HD vertical space video clip from Pexels API."""
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={keyword}&orientation=portrait&per_page=5"
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        data = res.json()
        videos = data.get("videos", [])
        
        if videos:
            # Pick first vertical HD video
            video_files = videos[0].get("video_files", [])
            hd_file = next((f for f in video_files if f.get("height", 0) >= 1280), video_files[0])
            video_url = hd_file.get("link")
            
            print(f"  Downloading Pexels video clip for '{keyword}'...")
            v_data = requests.get(video_url, timeout=30).content
            with open(output_file, "wb") as f:
                f.write(v_data)
            return True
    except Exception as e:
        print(f"  Pexels download error for keyword '{keyword}': {e}")
    return False

def build_scene_assets(storyboard):
    """Builds audio and downloads stock video clips."""
    os.makedirs("output/videos", exist_ok=True)
    os.makedirs("output/audio", exist_ok=True)
    
    processed_scenes = []
    
    for scene in storyboard.get("scenes", []):
        scene_id = scene["scene_id"]
        keyword = scene.get("search_keyword", "space galaxy")
        narration = scene["narration_text"]
        
        print(f"\n--- [Processing Scene {scene_id}] ---")
        
        # 1. Voiceover
        audio_path = f"output/audio/scene_{scene_id}.mp3"
        asyncio.run(generate_voiceover(narration, audio_path))
        
        # 2. Video Clip
        video_path = f"output/videos/scene_{scene_id}.mp4"
        success = fetch_pexels_video(keyword, video_path)
        
        # Fallback keyword if specific search fails
        if not success:
            fetch_pexels_video("deep space galaxy", video_path)
            
        processed_scenes.append((scene_id, video_path, audio_path))
        
    return processed_scenes

def stitch_final_reel(processed_scenes):
    """Stitches clips and audio into a final vertical video using FFmpeg."""
    print("\n🎬 Rendering final Reel with FFmpeg...")
    scene_outputs = []
    
    for scene_id, video_path, audio_path in processed_scenes:
        merged_scene_path = f"output/videos/merged_scene_{scene_id}.mp4"
        
        # Trim video to match audio length
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
        
    # Concat all merged scenes
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
    print(f"🎉 FINAL REEL CREATED: {final_output_path}")

def main():
    print("🚀 Initiating Autopilot Cosmology Reel Production Engine...")
    current_topic = "What happens if two supermassive black holes collide?"
    
    storyboard = generate_cosmology_storyboard(current_topic)
    os.makedirs("output", exist_ok=True)
    with open("output/storyboard.json", "w") as f:
        json.dump(storyboard, f, indent=2)
        
    processed_scenes = build_scene_assets(storyboard)
    stitch_final_reel(processed_scenes)
    
    print("\n✅ Process Finished Successfully!")

if __name__ == "__main__":
    main()
