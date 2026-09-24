import os
import re
import json
import asyncio
import requests
import subprocess
import time
from google import genai
import edge_tts

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

async def generate_script_and_prompts():
    if not GEMINI_KEY:
        raise Exception("GEMINI_API_KEY environment variable is not set.")
    
    client = genai.Client(api_key=GEMINI_KEY.strip())
    
    # Prompt updated for Dark History & Mysteries within Anime/Manhwa lore
    system_prompt = (
        "You are a scriptwriter for Dark History and Unsolved Mysteries, specifically focusing on Anime, Manga, and Manhwa lore. "
        "Write a catchy, fast-paced 40-second script in Hindi/Hinglish about a dark, mysterious event or anti-hero lore from a popular manga/manhwa universe. "
        "Break the story into exactly 4 sequential scenes. "
        "For each scene, provide:\n"
        "1. 'text': The narration text for voiceover.\n"
        "2. 'image_prompt': A detailed image prompt describing the scene. "
        "Always append 'clean sharp dark manhwa art style, cinematic lighting, ultra detailed, masterpiece, 8k' to the end of every image prompt.\n"
        "Return ONLY a raw valid JSON list of objects with keys 'text' and 'image_prompt'."
    )
    
    # Reverted back to the working flash model
    models_to_try = ['gemini-3.6-flash']
    
    for model_name in models_to_try:
        try:
            print(f"Generating dark manhwa lore with model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=system_prompt,
            )
            if response and response.text:
                cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
                return json.loads(cleaned_text)
        except Exception as e:
            print(f"Model {model_name} failed: {e}")
            
    raise Exception("Failed to generate content from Gemini models.")

def download_images(scenes):
    os.makedirs("images", exist_ok=True)
    image_files = []
    
    print("Downloading automated AI images from Pollinations.ai...")
    for idx, scene in enumerate(scenes):
        prompt = scene['image_prompt']
        encoded_prompt = requests.utils.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1280&height=720&nologo=true&seed=42"
        
        file_path = f"images/scene_{idx+1:02d}.jpg"
        try:
            res = requests.get(url, timeout=30)
            if res.status_code == 200:
                with open(file_path, "wb") as f:
                    f.write(res.content)
                print(f"Downloaded: {file_path}")
                image_files.append(file_path)
            else:
                print(f"Failed image download for scene {idx+1}")
        except Exception as e:
            print(f"Error fetching image for scene {idx+1}: {e}")
            
        # 2-second delay to prevent Pollinations.ai rate limiting
        time.sleep(2)
            
    return image_files

async def generate_audio(full_text, output_file="voiceover.mp3"):
    voice = "hi-IN-MadhurNeural"
    communicate = edge_tts.Communicate(full_text, voice)
    await communicate.save(output_file)
    print("Voiceover generated successfully.")

def render_video(audio_file="voiceover.mp3", output_file="final_video.mp4"):
    print("Starting video assembly via FFmpeg...")
    
    command = [
        "ffmpeg", "-y",
        "-framerate", "1/5",
        "-pattern_type", "glob", "-i", "images/*.jpg",
        "-i", audio_file,
        "-c:v", "libx264",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        output_file
    ]
    
    try:
        subprocess.run(command, check=True)
        print(f"Final Video rendered successfully: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e}")
        raise Exception("Video rendering failed.")

async def main():
    print("Starting Automated Dark Manhwa Mystery Pipeline...")
    try:
        scenes = await generate_script_and_prompts()
        full_narration = " ".join([s['text'] for s in scenes])
        print("\n--- Generated Script ---\n", full_narration)
        
        download_images(scenes)
        await generate_audio(full_narration)
        render_video()
        
        print("\nSUCCESS! Full automation completed. Video ready!")
    except Exception as err:
        print(f"Pipeline Failed: {err}")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
