import os
import time
import uuid
import base64
import json
import logging
from typing import Optional
from pathlib import Path
import asyncio

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Enforced output directory for all media assets (configurable via environment)
_MEDIA_WORKSPACE_ENV = os.environ.get("DEERFLOW_MEDIA_WORKSPACE")
if _MEDIA_WORKSPACE_ENV:
    MEDIA_WORKSPACE = Path(_MEDIA_WORKSPACE_ENV)
else:
    # Default: relative to project root
    MEDIA_WORKSPACE = Path(__file__).parent.parent.parent.parent / "workspace" / "media"
# Ensure the directory exists
MEDIA_WORKSPACE.mkdir(parents=True, exist_ok=True)

# Helper for API key
def _get_api_key() -> str:
    key = os.environ.get("MINIMAX_API_KEY")
    if not key:
        raise ValueError("MINIMAX_API_KEY environment variable is not set. Cannot use MiniMax tools.")
    return key

def _get_base_url() -> str:
    # Use config base_url endpoint or fallback to minimaxi.com (Mainland routing)
    return "https://api.minimaxi.com/v1"

@tool
async def generate_image_minimax(prompt: str, model: str = "image-01", aspect_ratio: str = "16:9") -> str:
    """
    Generate an image based on a text prompt using MiniMax API.
    Args:
        prompt: Detailed description of the image to generate. Max 1500 chars.
        model: The model to use, default is "image-01".
        aspect_ratio: Aspect ratio of the image. Standard options: "1:1", "16:9", "4:3", "9:16".
    Returns:
        The absolute file path of the generated image on the local disk.
    """
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "response_format": "base64"
    }
    
    endpoint = f"{_get_base_url()}/image_generation"
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # The base64 output is usually in data["data"]["image_base64"][0]
            if "data" in data and "image_base64" in data["data"] and len(data["data"]["image_base64"]) > 0:
                img_b64 = data["data"]["image_base64"][0]
                img_bytes = base64.b64decode(img_b64)
                
                filename = f"image_{uuid.uuid4().hex[:8]}.png"
                output_path = MEDIA_WORKSPACE / filename
                output_path.write_bytes(img_bytes)
                return f"Image successfully generated and saved to: {output_path.absolute()}"
            else:
                return f"Failed to generate image. Unexpected API response structure: {data}"
        except Exception as e:
            logger.exception("Image generation failed")
            return f"Error during image generation: {str(e)}"

@tool
async def generate_audio_minimax(text: str, model: str = "speech-01-turbo", voice_id: str = "male-qn-qingse") -> str:
    """
    Generate speech/audio from text using MiniMax API.
    Args:
        text: The text to synthesize into speech.
        model: The speech model, default "speech-01-turbo" or "speech-01".
        voice_id: The specific voice timbre to use. Options include:
                  "male-qn-qingse", "female-shaonv", "female-yujie", "male-播音".
    Returns:
        The absolute file path of the generated audio (.mp3) on the local disk.
    """
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": voice_id
        },
        "audio_sample_rate": 32000,
        "format": "mp3"
    }
    
    endpoint = f"{_get_base_url()}/t2a_v2"
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # For t2a_v2 hex encoded format inside `data['data']['audio']`
            if "data" in data and "audio" in data["data"]:
                audio_hex = data["data"]["audio"]
                audio_bytes = bytes.fromhex(audio_hex)
                
                filename = f"audio_{uuid.uuid4().hex[:8]}.mp3"
                output_path = MEDIA_WORKSPACE / filename
                output_path.write_bytes(audio_bytes)
                return f"Audio successfully generated and saved to: {output_path.absolute()}"
            else:
                return f"Failed to generate audio. Unexpected API response structure: {data}"
                
        except Exception as e:
            logger.exception("Audio generation failed")
            return f"Error during audio generation: {str(e)}"

@tool
async def generate_video_minimax(prompt: str, model: str = "video-01") -> str:
    """
    Generate a short video from text using MiniMax Video API (Hailuo). Asynchronous task.
    Args:
        prompt: Detailed description of the video to create.
        model: Model ID, default "video-01".
    Returns:
        The status and local file path if successful. This function blocks until video is ready.
    """
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json"
    }
    create_payload = {
        "model": model,
        "prompt": prompt
    }
    
    create_endpoint = f"{_get_base_url()}/video_generation"
    query_endpoint = f"{_get_base_url()}/query/video_generation"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # 1. Create Task
            create_resp = await client.post(create_endpoint, json=create_payload, headers=headers)
            create_resp.raise_for_status()
            create_data = create_resp.json()
            
            task_id = create_data.get("task_id")
            if not task_id:
                return f"Failed to submit video generation task. Response: {create_data}"
                
            # 2. Poll Status
            max_attempts = 60 # 60 * 5s = 300s (5 minutes)
            for attempt in range(max_attempts):
                await asyncio.sleep(5)
                poll_resp = await client.get(f"{query_endpoint}?task_id={task_id}", headers=headers)
                poll_resp.raise_for_status()
                poll_data = poll_resp.json()
                
                status = poll_data.get("status", "")
                if status == "Success":
                    file_id = poll_data.get("file_id")
                    if not file_id:
                        return f"Video succeeded but missing file_id: {poll_data}"
                    
                    # 3. Download the video using MiniMax files API
                    files_endpoint = f"{_get_base_url()}/files/retrieve?file_id={file_id}"
                    file_resp = await client.get(files_endpoint, headers=headers)
                    file_resp.raise_for_status()
                    
                    filename = f"video_{uuid.uuid4().hex[:8]}.mp4"
                    output_path = MEDIA_WORKSPACE / filename
                    output_path.write_bytes(file_resp.content)
                    return f"Video successfully generated and saved to: {output_path.absolute()}"
                    
                elif status == "Fail":
                    return f"Video generation failed remotely. Response: {poll_data}"
                
                # If Processing/Queueing, continue looping
                
            return f"Video generation task {task_id} timed out after {max_attempts * 5} seconds."
            
        except Exception as e:
            logger.exception("Video generation failed")
            return f"Error during video generation: {str(e)}"

@tool
async def generate_music_minimax(prompt: str, lyrics: str = "", is_instrumental: bool = False, model: str = "music-2.6") -> str:
    """
    Generate music using MiniMax Music Generation API.
    Args:
        prompt: Describes the genre, mood, instruments, and style.
        lyrics: The song lyrics. Use tags like [Verse], [Chorus] to structure. Leave empty if is_instrumental=True.
        is_instrumental: Set to True to generate a backing track without vocals.
        model: Model ID, default "music-2.6".
    Returns:
        The absolute file path of the generated music (.mp3 or .pcm) on the local disk.
    """
    headers = {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "is_instrumental": is_instrumental,
        "output_format": "url"  # URL format is reliable for large music files
    }
    if not is_instrumental and lyrics:
        payload["lyrics"] = lyrics

    endpoint = f"{_get_base_url()}/music_generation"

    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # The API returns 'data': {'audio_url': '...'} or we might need to parse.
            if "data" in data and "audio" in data["data"]:
                # Hex format fallback
                audio_hex = data["data"]["audio"]
                audio_bytes = bytes.fromhex(audio_hex)
                filename = f"music_{uuid.uuid4().hex[:8]}.mp3"
                output_path = MEDIA_WORKSPACE / filename
                output_path.write_bytes(audio_bytes)
                return f"Music safely generated and saved to: {output_path.absolute()}"
            elif "data" in data and "audio_url" in data["data"]:
                audio_url = data["data"]["audio_url"]
                dl_resp = await client.get(audio_url)
                dl_resp.raise_for_status()
                filename = f"music_{uuid.uuid4().hex[:8]}.mp3"
                output_path = MEDIA_WORKSPACE / filename
                output_path.write_bytes(dl_resp.content)
                return f"Music successfully generated and saved to: {output_path.absolute()}"
            elif "audio" in data:
                 url = data["audio"]
                 dl_resp = await client.get(url)
                 dl_resp.raise_for_status()
                 filename = f"music_{uuid.uuid4().hex[:8]}.mp3"
                 output_path = MEDIA_WORKSPACE / filename
                 output_path.write_bytes(dl_resp.content)
                 return f"Music successfully generated and saved to: {output_path.absolute()}"

            return f"Failed to parse music generation. Response: {data}"
                
        except Exception as e:
            logger.exception("Music generation failed")
            return f"Error during music generation: {str(e)}"

__all__ = ["generate_image_minimax", "generate_audio_minimax", "generate_video_minimax", "generate_music_minimax"]
