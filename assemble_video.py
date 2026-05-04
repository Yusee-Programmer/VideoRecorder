import os
import sys
import asyncio
import edge_tts
import subprocess
import shutil
import tempfile
import imageio_ffmpeg
import re

# Configuration
INPUT_VIDEO = "demo_recording.mp4"
OUTPUT_VIDEO_FINAL = "demo_recording_fr.mp4"
TTS_VOICE = "fr-FR-HenriNeural"
TTS_PITCH = "-20Hz"
SRT_PATH = "subtitles_fr.srt"

def setup_ffmpeg():
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    temp_bin_dir = tempfile.mkdtemp()
    shutil.copy(ffmpeg_exe, os.path.join(temp_bin_dir, "ffmpeg.exe"))
    os.environ["PATH"] = temp_bin_dir + os.pathsep + os.environ["PATH"]
    return temp_bin_dir, os.path.join(temp_bin_dir, "ffmpeg.exe")

def parse_srt(path):
    segments = []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Simple SRT parser
    matches = re.findall(r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\n$|$)", content, re.DOTALL)
    for m in matches:
        def to_sec(t):
            h, m, s = t.replace(',', '.').split(':')
            return float(h)*3600 + float(m)*60 + float(s)
        segments.append({
            'start': to_sec(m[1]),
            'end': to_sec(m[2]),
            'text': m[3].strip()
        })
    return segments

async def generate_tts(text, output_path):
    communicate = edge_tts.Communicate(text, TTS_VOICE, pitch=TTS_PITCH)
    await communicate.save(output_path)

def get_duration(file_path, ffmpeg_exe):
    # Use ffmpeg to get duration from stderr
    cmd = [ffmpeg_exe, "-i", file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if match:
        h, m, s = match.groups()
        return float(h)*3600 + float(m)*60 + float(s)
    return 0.0

async def main():
    _, ffmpeg_exe = setup_ffmpeg()
    segments = parse_srt(SRT_PATH)
    print(f"Parsed {len(segments)} segments from SRT.")

    tmp_dir = "tts_segments"
    if not os.path.exists(tmp_dir): os.makedirs(tmp_dir)
    
    audio_inputs = []
    filter_complex = ""
    
    print("--- Generating TTS and calculating synchronization ---")
    for i, seg in enumerate(segments):
        if not seg['text']: continue
        
        tts_path = os.path.join(tmp_dir, f"seg_{i}.mp3")
        if not os.path.exists(tts_path):
            await generate_tts(seg['text'], tts_path)
        
        target_dur = seg['end'] - seg['start']
        actual_dur = get_duration(tts_path, ffmpeg_exe)
        
        speed = actual_dur / target_dur
        safe_speed = max(0.5, min(2.0, speed))
        
        adj_path = os.path.join(tmp_dir, f"seg_{i}_adj.mp3")
        subprocess.run([
            ffmpeg_exe, "-i", tts_path, "-filter:a", f"atempo={safe_speed}", "-y", adj_path
        ], capture_output=True)
        
        # We'll use adelay for positioning
        delay_ms = int(seg['start'] * 1000)
        # Note: adelay filter takes delay for each channel. 
        # For stereo: adelay=1000|1000. For mono: adelay=1000.
        # We'll use adelay={delay}|{delay} to be safe.
        audio_inputs.append(adj_path)
        filter_complex += f"[{i+1}:a]adelay={delay_ms}|{delay_ms}[a{i}];"

    # Combine all delayed segments
    inputs_str = "".join([f"[a{i}]" for i in range(len(audio_inputs))])
    filter_complex += f"{inputs_str}amix=inputs={len(audio_inputs)}:dropout_transition=0:normalize=0[outa]"

    print("--- Final Assembly with FFmpeg ---")
    # Command: ffmpeg -i video -i seg1 -i seg2 ... -filter_complex ... -map 0:v -map [outa] ...
    cmd = [ffmpeg_exe, "-i", INPUT_VIDEO]
    for path in audio_inputs:
        cmd.extend(["-i", path])
    
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[outa]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-y", "temp_fr_no_sub.mp4"
    ])
    
    print("Running ffmpeg assembly...")
    subprocess.run(cmd)

    print("--- Adding Subtitles ---")
    subprocess.run([
        ffmpeg_exe, "-i", "temp_fr_no_sub.mp4", "-i", SRT_PATH,
        "-c", "copy", "-c:s", "mov_text", "-y", OUTPUT_VIDEO_FINAL
    ])
    
    if os.path.exists("temp_fr_no_sub.mp4"):
        os.remove("temp_fr_no_sub.mp4")

    print(f"SUCCESS! {OUTPUT_VIDEO_FINAL} created.")

if __name__ == "__main__":
    asyncio.run(main())
