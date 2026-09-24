import os
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
    
    system_prompt = (
        "You are an expert documentary scriptwriter for Dark History and Unsolved Mysteries. "
        "Create an engaging, deep dark history narrative in Hindi/Hinglish. "
        "Break the story into dynamic sequential scenes according to the flow and tension of the story. "
        "For EACH scene, strictly specify:\n"
        "1. 'text': Narration line for voiceover.\n"
        "2. 'duration': Recommended time in seconds for this visual scene based on the text speed and tension (between 2 to 8 seconds).\n"
        "3. 'image_prompt': Highly descriptive image prompt for the scene. "
        "Always append 'cinematic lighting, dark atmospheric historical scene, ultra detailed, 8k' to image prompts.\n"
        "Return ONLY a raw valid JSON list of objects with keys 'text', 'duration', and 'image_prompt'."
    )
    
    models_to_try = ['gemini-3.6-flash']
    
    for model_name in models_to_try:
        try:
            print(f"Generating dynamic storyline with {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=system_prompt,
            )
            if response and response.text:
                cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
                return json.loads(cleaned_text)
        except Exception as e:
            print(f"Model {model_name} failed: {e}")
            
    raise Exception("Failed to generate content from Gemini.")

def download_images(scenes):
    os.makedirs("images", exist_ok=True)
    image_files = []
    
    print("Downloading AI images based on dynamic script...")
    for idx, scene in enumerate(scenes):
        prompt = scene['image_prompt']
        encoded_prompt = requests.utils.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1280&height=720&nologo=true&seed={idx+100}"
        
        file_path = f"images/scene_{idx+1:03d}.jpg"
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
            
        time.sleep(1)
            
    return image_files

async def generate_audio(scenes, output_file="voiceover.mp3"):
    full_text = " ".join([s['text'] for s in scenes])
    
    voice = "hi-IN-MadhurNeural"
    communicate = edge_tts.Communicate(full_text, voice, rate="-4%", pitch="-2Hz")
    await communicate.save(output_file)
    print("Voiceover generated successfully.")

def render_video(scenes, audio_file="voiceover.mp3", output_file="final_video.mp4"):
    print("Rendering video with DYNAMIC scene durations...")
    
    concat_file = "files.txt"
    with open(concat_file, "w") as f:
        for idx, scene in enumerate(scenes):
            img_path = f"images/scene_{idx+1:03d}.jpg"
            if os.path.exists(img_path):
                duration = scene.get('duration', 4)
                f.write(f"file '{img_path}'\n")
                f.write(f"duration {duration}\n")
        
        if scenes:
            f.write(f"file 'images/scene_{len(scenes):03d}.jpg'\n")

    command = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-i", audio_file,
        "-vf", "crop=in_w:in_h-40:0:0,scale=1280:720",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        output_file
    ]
    
    try:
        subprocess.run(command, check=True)
        print(f"Final Dynamic Video rendered successfully: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e}")
        raise Exception("Video rendering failed.")

async def main():
    print("Starting Advanced Dynamic Video Pipeline...")
    try:
        scenes = await generate_script_and_prompts()
        print(f"\n--- Generated {len(scenes)} Dynamic Scenes ---")
        
        download_images(scenes)
        await generate_audio(scenes)
        render_video(scenes)
        
        print("\nSUCCESS! Dynamic video ready for Youtube!")
    except Exception as err:
        print(f"Pipeline Failed: {err}")
        exit(1)

if __name__ == "__main__":
    asyncio.main(main()) if hasattr(asyncio, 'main') else asyncio.run(main())
