import os
import sys
import whisper
import asyncio
import edge_tts
import subprocess
import shutil
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
from deep_translator import GoogleTranslator
from datetime import timedelta
import tempfile
import imageio_ffmpeg

# Setup ffmpeg for Whisper and other tools
def setup_ffmpeg():
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = os.path.dirname(ffmpeg_exe)
    # Whisper expects 'ffmpeg' command. Create a shim if needed.
    temp_bin_dir = tempfile.mkdtemp()
    shutil.copy(ffmpeg_exe, os.path.join(temp_bin_dir, "ffmpeg.exe"))
    shutil.copy(ffmpeg_exe, os.path.join(temp_bin_dir, "ffprobe.exe")) # Also ffprobe
    os.environ["PATH"] = temp_bin_dir + os.pathsep + os.environ["PATH"]
    print(f"Ffmpeg setup in {temp_bin_dir}")
    return temp_bin_dir

# Configuration
INPUT_VIDEO = "demo_recording.mp4"
OUTPUT_VIDEO_BASE = "demo_recording_fr_temp.mp4"
OUTPUT_VIDEO_FINAL = "demo_recording_fr.mp4"
WHISPER_MODEL = "base"
TTS_VOICE = "fr-FR-HenriNeural"
TTS_PITCH = "-20Hz"

def format_timedelta(td: timedelta):
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def create_srt(segments, srt_path):
    print(f"Creating SRT at {srt_path}...")
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments):
            start = format_timedelta(timedelta(seconds=seg['start']))
            end = format_timedelta(timedelta(seconds=seg['end']))
            f.write(f"{i+1}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{seg['text']}\n\n")

async def generate_tts(text, output_path):
    communicate = edge_tts.Communicate(text, TTS_VOICE, pitch=TTS_PITCH)
    await communicate.save(output_path)

async def main():
    if not os.path.exists(INPUT_VIDEO):
        print(f"Error: {INPUT_VIDEO} not found.")
        return

    setup_ffmpeg()

    print("--- Phase 1: Transcription ---")
    # Using 'base' model for faster processing
    model = whisper.load_model(WHISPER_MODEL)
    print(f"Transcribing {INPUT_VIDEO}...")
    result = model.transcribe(INPUT_VIDEO)
    segments = result['segments']
    print(f"Transcribed {len(segments)} segments.")

    print("--- Phase 2: Translation ---")
    translator = GoogleTranslator(source='en', target='fr')
    for seg in segments:
        seg['text_en'] = seg['text'].strip()
        if not seg['text_en']:
            seg['text'] = ""
            continue
        seg['text'] = translator.translate(seg['text_en'])
        print(f"[{seg['start']:.2f}s] {seg['text_en']} -> {seg['text']}")

    create_srt(segments, "subtitles_fr.srt")

    print("--- Phase 3: TTS & Synchronization ---")
    tmp_dir = tempfile.mkdtemp()
    audio_clips = []
    
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    for i, seg in enumerate(segments):
        if not seg['text']: continue
        
        target_dur = seg['end'] - seg['start']
        if target_dur <= 0.1: continue # Skip tiny segments
        
        tts_path = os.path.join(tmp_dir, f"seg_{i}.mp3")
        await generate_tts(seg['text'], tts_path)
        
        clip = AudioFileClip(tts_path)
        actual_dur = clip.duration
        
        # Calculate speed factor to match target duration
        speed_factor = actual_dur / target_dur
        
        # atempo filter limit is 0.5 to 2.0. We'll clip it to be safe.
        safe_speed = max(0.5, min(2.0, speed_factor))
        
        if abs(safe_speed - 1.0) > 0.05:
            adjusted_path = os.path.join(tmp_dir, f"seg_{i}_adj.mp3")
            subprocess.run([
                ffmpeg_exe, "-i", tts_path, 
                "-filter:a", f"atempo={safe_speed}", 
                "-y", adjusted_path
            ], capture_output=True)
            if os.path.exists(adjusted_path):
                clip = AudioFileClip(adjusted_path)
        
        # Set start time relative to video
        clip = clip.with_start(seg['start'])
        audio_clips.append(clip)

    print("--- Phase 4: Assembly ---")
    video = VideoFileClip(INPUT_VIDEO)
    final_audio = CompositeAudioClip(audio_clips)
    
    # Overlay audio on a silent version of the video
    final_video = video.with_audio(final_audio)
    
    # Limit duration to original video
    final_video = final_video.with_duration(video.duration)
    
    print(f"Writing intermediate video to {OUTPUT_VIDEO_BASE}...")
    final_video.write_videofile(OUTPUT_VIDEO_BASE, codec="libx264", audio_codec="aac", fps=video.fps)
    
    print("--- Phase 5: Adding Subtitles ---")
    # Add subtitles as a soft track
    subprocess.run([
        ffmpeg_exe, "-i", OUTPUT_VIDEO_BASE, "-i", "subtitles_fr.srt",
        "-c", "copy", "-c:s", "mov_text", "-y", OUTPUT_VIDEO_FINAL
    ])
    
    # Cleanup temp file
    if os.path.exists(OUTPUT_VIDEO_BASE):
        os.remove(OUTPUT_VIDEO_BASE)
        
    print(f"\nSUCCESS!")
    print(f"Original: {INPUT_VIDEO}")
    print(f"French Version: {OUTPUT_VIDEO_FINAL}")
    print(f"Subtitles: subtitles_fr.srt")

if __name__ == "__main__":
    asyncio.run(main())
