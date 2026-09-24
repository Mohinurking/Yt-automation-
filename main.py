import os
import asyncio
import google.generativeai as genai
import edge_tts

# 1. Setup Gemini API
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY.strip())

async def generate_script():
    prompt = "Write an engaging, exciting 40-second Hindi recap script for a popular action manhwa. Keep it in Hindi script or Hinglish, fast-paced and catchy."
    
    # Try updated Gemini models with a fallback list
    models_to_try = [
        'gemini-2.5-flash',
        'gemini-1.5-flash-latest',
        'gemini-2.0-flash',
        'gemini-1.5-pro'
    ]
    
    for model_name in models_to_try:
        try:
            print(f"Trying model: {model_name}...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
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
    if GEMINI_KEY:
        try:
            script = await generate_script()
            print("\n--- Generated Script ---\n", script)
            await generate_audio(script)
            print("Pipeline Step Completed Successfully!")
        except Exception as err:
            print(f"Pipeline Error: {err}")
            exit(1)
    else:
        print("API Key not found!")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
