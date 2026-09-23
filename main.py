import os
import asyncio
import google.generativeai as genai
import edge_tts

# 1. Setup Gemini API
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

async def generate_script():
    prompt = "Write an engaging, exciting 40-second Hindi recap script for an action manhwa/anime short video. Use natural conversational Hindi in Latin/Hinglish script."
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    return response.text

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
        script = await generate_script()
        print("Generated Script:\n", script)
        await generate_audio(script)
    else:
        print("API Key not found!")

if __name__ == "__main__":
    asyncio.run(main())
