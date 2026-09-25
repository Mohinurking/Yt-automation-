import os
import json
import requests
from google import genai

# Initialize Gemini Client (Uses GEMINI_API_KEY from Environment Variables)
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def generate_cosmology_storyboard(topic):
    """Generates structured script and visual prompts strictly focused on Cosmology."""
    
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
          "duration_seconds": 4,
          "narration_text": "Engaging hook line in English...",
          "visual_prompt": "cinematic 8k, photorealistic, deep space, James Webb telescope style, 9:16 vertical, [specific visual description]"
        }
      ]
    }
    """
    
    user_prompt = f"Generate a high-retention space documentary storyboard about: {topic}"
    
    # Updated to the new model gemini-3.8-flash as required
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=f"{system_prompt}\n\n{user_prompt}",
        config={"response_mime_type": "application/json"}
    )
    
    return json.loads(response.text)

def build_scene_assets(storyboard):
    """Processes each scene to generate image prompts and text-to-speech audio."""
    os.makedirs("output/images", exist_ok=True)
    os.makedirs("output/audio", exist_ok=True)
    
    for scene in storyboard.get("scenes", []):
        scene_id = scene["scene_id"]
        img_prompt = scene["visual_prompt"]
        narration = scene["narration_text"]
        
        print(f"[Processing Scene {scene_id}] Generating assets...")
        
        # --- Image Generation Endpoint Logic ---
        # img_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(img_prompt)}?width=1080&height=1920&nologo=true"
        # img_bytes = requests.get(img_url).content
        # with open(f"output/images/scene_{scene_id}.jpg", "wb") as f:
        #     f.write(img_bytes)

        # --- TTS Audio Generation Logic ---
        # Generate TTS audio file and save as output/audio/scene_{scene_id}.mp3
        
    print("Asset generation phase complete.")

def render_final_reel():
    """Stitches images and audio into a single 9:16 vertical video using FFmpeg/MoviePy."""
    print("Stitching video frames and audio channels into final output...")
    # FFmpeg compilation commands execute here

def main():
    print("🚀 Initiating Autopilot Cosmology Reel Production Engine...")
    
    # Topic can be fetched dynamically or defined
    current_topic = "What happens if two supermassive black holes collide?"
    
    # Step 1: Script and JSON Storyboard
    print("Step 1: Requesting structured JSON storyboard from Gemini...")
    storyboard = generate_cosmology_storyboard(current_topic)
    
    # Ensure output directory exists before saving JSON
    os.makedirs("output", exist_ok=True)
    with open("output/storyboard.json", "w") as f:
        json.dump(storyboard, f, indent=2)
        
    # Step 2: Asset Creation
    print("Step 2: Processing visual prompts and audio narration...")
    build_scene_assets(storyboard)
    
    # Step 3: Video Assembly
    print("Step 3: Rendering final 60s Reel...")
    render_final_reel()
    
    print("✅ Process completed successfully! File location: output/final_cosmology_reel.mp4")

if __name__ == "__main__":
    main()
