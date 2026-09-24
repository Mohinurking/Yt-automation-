import os
import asyncio
from google import genai
import edge_tts

# 1. Setup Gemini API with modern google-genai SDK
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

async def generate_script():
    if not GEMINI_KEY:
        raise Exception("GEMINI_API_KEY environment variable is not set.")
    
    client = genai.Client(api_key=GEMINI_KEY.strip())
    
    prompt = "Write an engaging, exciting 40-second Hindi recap script for a popular action manhwa. Keep it in Hindi script or Hinglish, fast-paced and catchy."
    
    # Updated model list as recommended by Google API response
    models_to_try = [
        'gemini-2.0-flash',
        'gemini-2.5-flash',
        'gemini-1.5-flash'
    ]
    
    for model_name in models_to_try:
        try:
            print(f"Trying model: {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            if response and response.text:
                print(f"Successfully generated script using {model_name}!")
                return response.text
        except Exception as e:
            print(f"Model {model_name} failed: {e}")
            
    raise Exception("All attempted Gemini models failed to generate content.")

async def generate_audio(text):
    # Hindi Neural Voice from Microsoft Edge TTS
    voice = "hi-IN-MadhurNeural"
    output_file = "voiceover.mp3"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)
    print("Voiceover generated successfully.")

async def main():
    print("Starting YouTube Automation Pipeline...")
    try:
        script = await generate_script()
        print("\n--- Generated Script ---\n", script)
        await generate_audio(script)
        print("Pipeline Step Completed Successfully!")
    except Exception as err:
        print(f"Pipeline Error: {err}")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
