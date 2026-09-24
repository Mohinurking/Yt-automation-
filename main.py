import os
import re
import json
import time
import shutil
import asyncio
import logging
import subprocess
from pathlib import Path

import requests
import edge_tts
from google import genai


# ============================================================
# CONFIG
# ============================================================

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

OUTPUT_DIR = Path("output")
IMAGES_DIR = OUTPUT_DIR / "images"
AUDIO_DIR = OUTPUT_DIR / "audio"
CLIPS_DIR = OUTPUT_DIR / "clips"

FINAL_VIDEO = OUTPUT_DIR / "final_video.mp4"
SCRIPT_FILE = OUTPUT_DIR / "project.json"

WIDTH = 1280
HEIGHT = 720
FPS = 30

IMAGE_RETRIES = 3
IMAGE_WAIT = 2

VOICE = "hi-IN-MadhurNeural"
VOICE_RATE = "-4%"
VOICE_PITCH = "-2Hz"

# Try models in this order.
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

IMAGE_BASE_URL = "https://image.pollinations.ai/prompt/"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

log = logging.getLogger("AI-VIDEO")


# ============================================================
# HELPERS
# ============================================================

def check_environment():
    if not GEMINI_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Check your GitHub repository secrets."
        )

    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "FFmpeg was not found. Install FFmpeg and add it to PATH."
        )

    if shutil.which("ffprobe") is None:
        raise RuntimeError(
            "ffprobe was not found. Install FFmpeg properly and add it to PATH."
        )


def create_directories():
    for folder in [OUTPUT_DIR, IMAGES_DIR, AUDIO_DIR, CLIPS_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def run_command(command):
    log.debug("Running: %s", " ".join(map(str, command)))

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed:\n{' '.join(map(str, command))}\n\n"
            f"{result.stderr[-4000:]}"
        )

    return result


def clean_json(text):
    text = text.strip()

    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end != -1:
        text = text[start:end + 1]

    return text.strip()


# ============================================================
# GEMINI
# ============================================================

def build_prompt(topic):
    return f"""
You are an expert documentary filmmaker and dark-history storyteller.

Create a cinematic Hindi/Hinglish documentary about:

TOPIC:
{topic}

The video must feel serious, mysterious, cinematic and engaging.

IMPORTANT:
- Do NOT invent historical facts.
- Clearly distinguish known facts from uncertainty.
- Do not create fake quotes.
- Keep narration natural for Hindi voiceover.
- Start with a strong hook.
- Build tension progressively.
- Avoid unnecessary filler.
- Every scene must visually support its narration.
- Scenes should normally be 3–8 seconds long.
- Use detailed cinematic visual prompts.
- Maintain visual continuity between scenes.
- If a person appears repeatedly, describe their consistent appearance.
- If the story is historical, use historically appropriate clothing,
  architecture, weapons, environment and technology.
- Do not use modern objects in historical scenes unless historically correct.

Return ONLY valid JSON.

Format:

[
  {{
    "text": "Hindi/Hinglish narration",
    "image_prompt": "Detailed visual generation prompt",
    "mood": "dark / mysterious / tense / emotional / etc"
  }}
]

Do not include markdown.
Do not include explanations outside JSON.
"""


def generate_scenes(topic):
    client = genai.Client(api_key=GEMINI_KEY)

    prompt = build_prompt(topic)

    for model in GEMINI_MODELS:
        try:
            log.info("Generating documentary with %s...", model)

            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                },
            )

            if not response or not response.text:
                continue

            raw = clean_json(response.text)
            scenes = json.loads(raw)

            if not isinstance(scenes, list) or not scenes:
                raise ValueError("Gemini returned an empty scene list.")

            validated = []

            for i, scene in enumerate(scenes, start=1):
                text = str(scene.get("text", "")).strip()
                image_prompt = str(scene.get("image_prompt", "")).strip()
                mood = str(scene.get("mood", "cinematic")).strip()

                if not text:
                    continue

                if not image_prompt:
                    image_prompt = (
                        "Cinematic documentary scene, "
                        "dark atmospheric historical environment, "
                        "realistic details"
                    )

                image_prompt += (
                    ", cinematic lighting, dark atmospheric documentary scene, "
                    "ultra detailed, realistic, 8k, "
                    "dramatic composition, volumetric lighting, "
                    "historically appropriate details"
                )

                validated.append({
                    "scene": i,
                    "text": text,
                    "image_prompt": image_prompt,
                    "mood": mood,
                })

            if not validated:
                raise ValueError("No valid scenes generated.")

            log.info("Generated %d scenes.", len(validated))

            return validated

        except Exception as e:
            log.warning("%s failed: %s", model, e)

    raise RuntimeError("All Gemini models failed.")


# ============================================================
# IMAGE GENERATION
# ============================================================

def generate_image_url(prompt, seed):
    encoded = requests.utils.quote(prompt)

    return (
        f"{IMAGE_BASE_URL}{encoded}"
        f"?width={WIDTH}"
        f"&height={HEIGHT}"
        f"&nologo=true"
        f"&seed={seed}"
    )


def download_image(prompt, output_path, seed):
    headers = {
        "User-Agent": "AI-Video-Pipeline/1.0"
    }

    for attempt in range(1, IMAGE_RETRIES + 1):

        try:
            log.info(
                "Image %s | attempt %d/%d",
                output_path.name,
                attempt,
                IMAGE_RETRIES,
            )

            url = generate_image_url(prompt, seed)

            response = requests.get(
                url,
                headers=headers,
                timeout=60,
            )

            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            if "image" not in content_type.lower():
                raise RuntimeError(
                    f"Unexpected response type: {content_type}"
                )

            with open(output_path, "wb") as f:
                f.write(response.content)

            if output_path.stat().st_size < 10_000:
                raise RuntimeError("Downloaded image appears invalid.")

            return True

        except Exception as e:
            log.warning(
                "Image failed: %s",
                e,
            )

            if attempt < IMAGE_RETRIES:
                time.sleep(IMAGE_WAIT * attempt)

    return False


def download_all_images(scenes):
    log.info("Generating/downloading scene images...")

    successful = 0

    for index, scene in enumerate(scenes, start=1):

        output = IMAGES_DIR / f"scene_{index:03d}.jpg"

        success = download_image(
            scene["image_prompt"],
            output,
            seed=1000 + index,
        )

        if success:
            successful += 1
        else:
            log.error("Scene %d image failed.", index)

    if successful == 0:
        raise RuntimeError("No images were generated.")

    return successful


# ============================================================
# TTS
# ============================================================

async def generate_scene_audio(text, output_path):
    communicate = edge_tts.Communicate(
        text,
        VOICE,
        rate=VOICE_RATE,
        pitch=VOICE_PITCH,
    )

    await communicate.save(str(output_path))


def get_media_duration(path):
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]

    result = run_command(command)

    return float(result.stdout.strip())


async def generate_all_audio(scenes):
    log.info("Generating scene-by-scene voiceover...")

    valid_scenes = []

    for index, scene in enumerate(scenes, start=1):

        audio_path = AUDIO_DIR / f"scene_{index:03d}.mp3"

        try:
            await generate_scene_audio(
                scene["text"],
                audio_path,
            )

            duration = get_media_duration(audio_path)

            if duration <= 0:
                raise RuntimeError("Invalid audio duration.")

            scene["audio_file"] = str(audio_path)
            scene["duration"] = round(duration, 3)

            valid_scenes.append(scene)

            log.info(
                "Scene %d voice: %.2fs",
                index,
                duration,
            )

        except Exception as e:
            log.error(
                "TTS failed for scene %d: %s",
                index,
                e,
            )

    if not valid_scenes:
        raise RuntimeError("No audio scenes generated.")

    return valid_scenes


# ============================================================
# CINEMATIC SCENE VIDEO
# ============================================================

def render_scene(scene, index):
    image_path = IMAGES_DIR / f"scene_{index:03d}.jpg"
    audio_path = Path(scene["audio_file"])

    output_path = CLIPS_DIR / f"clip_{index:03d}.mp4"

    if not image_path.exists():
        raise RuntimeError(
            f"Missing image for scene {index}"
        )

    duration = float(scene["duration"])

    video_filter = (
        "scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080,"
        "zoompan="
        "z='min(zoom+0.00035,1.08)':"
        "x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':"
        "d=1:"
        f"s={WIDTH}x{HEIGHT}:"
        f"fps={FPS},"
        "format=yuv420p"
    )

    command = [
        "ffmpeg",
        "-y",

        "-loop", "1",
        "-i", str(image_path),

        "-i", str(audio_path),

        "-vf", video_filter,

        "-t", f"{duration:.3f}",

        "-r", str(FPS),

        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "19",

        "-c:a", "aac",
        "-b:a", "192k",

        "-ar", "48000",

        "-pix_fmt", "yuv420p",

        "-shortest",

        str(output_path),
    ]

    run_command(command)

    return output_path


def render_all_scenes(scenes):
    log.info("Rendering cinematic scene clips...")

    clips = []

    for index, scene in enumerate(scenes, start=1):

        try:
            clip = render_scene(scene, index)

            clips.append(clip)

            log.info(
                "Rendered scene %d/%d",
                index,
                len(scenes),
            )

        except Exception as e:
            log.error(
                "Scene %d rendering failed: %s",
                index,
                e,
            )

    if not clips:
        raise RuntimeError("No video clips were rendered.")

    return clips


# ============================================================
# CONCATENATE
# ============================================================

def create_concat_file(clips):
    concat_file = OUTPUT_DIR / "concat.txt"

    with open(concat_file, "w", encoding="utf-8") as f:

        for clip in clips:
            absolute_path = clip.resolve()
            path_string = str(absolute_path).replace("'", "'\\''")
            f.write(f"file '{path_string}'\n")

    return concat_file


def concatenate_clips(clips):
    concat_file = create_concat_file(clips)

    log.info("Combining all scenes...")

    command = [
        "ffmpeg",
        "-y",

        "-f", "concat",
        "-safe", "0",

        "-i", str(concat_file),

        "-c", "copy",

        str(FINAL_VIDEO),
    ]

    try:
        run_command(command)

    except Exception:
        log.warning(
            "Stream-copy concat failed. Trying safe re-encode..."
        )

        command = [
            "ffmpeg",
            "-y",

            "-f", "concat",
            "-safe", "0",

            "-i", str(concat_file),

            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "19",

            "-c:a", "aac",
            "-b:a", "192k",

            "-pix_fmt", "yuv420p",

            str(FINAL_VIDEO),
        ]

        run_command(command)

    return FINAL_VIDEO


# ============================================================
# PROJECT FILE
# ============================================================

def save_project(topic, scenes):
    project = {
        "topic": topic,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "voice": VOICE,
        "resolution": f"{WIDTH}x{HEIGHT}",
        "fps": FPS,
        "scenes": scenes,
    }

    with open(
        SCRIPT_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            project,
            f,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# MAIN PIPELINE
# ============================================================

async def main():

    print()
    print("=" * 60)
    print("        AI DOCUMENTARY VIDEO GENERATOR")
    print("=" * 60)
    print()

    check_environment()
    create_directories()

    # Default topic for automated cron runs if input isn't interactive
    topic = "The Mysterious Disappearance of the Roanoke Colony"
    
    try:
        if os.isatty(0):
            user_input = input("Enter documentary topic:\n> ").strip()
            if user_input:
                topic = user_input
    except Exception:
        pass

    log.info("Using documentary topic: %s", topic)

    start_time = time.time()

    scenes = generate_scenes(topic)
    image_count = download_all_images(scenes)

    log.info(
        "Successfully generated %d/%d images.",
        image_count,
        len(scenes),
    )

    scenes = await generate_all_audio(scenes)
    save_project(topic, scenes)

    clips = render_all_scenes(scenes)
    final_video = concatenate_clips(clips)
    final_duration = get_media_duration(final_video)

    elapsed = time.time() - start_time

    print()
    print("=" * 60)
    print("                 SUCCESS")
    print("=" * 60)
    print()
    print(f"Topic       : {topic}")
    print(f"Scenes      : {len(scenes)}")
    print(f"Duration    : {final_duration:.2f} seconds")
    print(f"Resolution  : {WIDTH}x{HEIGHT}")
    print(f"FPS         : {FPS}")
    print(f"Video       : {FINAL_VIDEO}")
    print(f"Project JSON: {SCRIPT_FILE}")
    print(f"Time taken  : {elapsed / 60:.2f} minutes")
    print()
    print("Your documentary video is ready.")
    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print("\nProcess cancelled by user.")

    except Exception as e:
        log.exception("PIPELINE FAILED")
        print()
        print("ERROR:", e)
        exit(1)
