import time
import threading
import mss
import cv2
import numpy as np
import keyboard
import os
import sounddevice as sd
import soundfile as sf
import subprocess
import imageio_ffmpeg
from pynput.mouse import Controller
import platform

mouse = Controller()

def get_mouse_pos():
    return mouse.position

recording = True
fps = 30.0  # Increased to 30 FPS for smooth motion

def select_region():
    print("\n[*] Screen capture for area selection...")
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        img = np.array(sct.grab(monitor))
        frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        # Resize to fit on screen for selection
        height, width = frame.shape[:2]
        scale = min(1200 / width, 800 / height)
        if scale < 1.0:
            resized_frame = cv2.resize(frame, (int(width * scale), int(height * scale)))
        else:
            resized_frame = frame
            scale = 1.0
        
        print("[*] A window will pop up.")
        print("[*] DRAW a rectangle over the area you want to record, then press ENTER or SPACE.")
        
        window_name = "Select Area (Draw rectangle then press SPACE or ENTER)"
        cv2.imshow(window_name, resized_frame)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
        
        bbox = cv2.selectROI(window_name, resized_frame, fromCenter=False, showCrosshair=True)
        cv2.destroyAllWindows()
        
        if bbox == (0, 0, 0, 0):
            print("[!] No area selected. Recording FULL SCREEN.")
            return monitor
        
        x, y, w, h = bbox
        return {
            "top": monitor["top"] + int(y / scale), 
            "left": monitor["left"] + int(x / scale), 
            "width": int(w / scale), 
            "height": int(h / scale)
        }

def record_screen(monitor):
    global recording
    width, height = monitor['width'], monitor['height']
    
    # Ensure dimensions are even numbers (required by many h264 decoders)
    width = width if width % 2 == 0 else width - 1
    height = height if height % 2 == 0 else height - 1
    
    # Use imageio_ffmpeg directly for perfect libx264 encoding in real-time
    writer = imageio_ffmpeg.write_frames(
        'temp_video.mp4', 
        (width, height), 
        fps=fps, 
        codec='libx264',
        pix_fmt_in='bgra',      # Direct BGRA input skips expensive color conversions
        pix_fmt_out='yuv420p',  # CRITICAL for standard video player compatibility
        macro_block_size=2,     # Allows any even-numbered resolution
        output_params=['-preset', 'ultrafast', '-crf', '18']
    )
    writer.send(None) # Initialize generator
    
    # Custom arrow cursor shape
    cursor_pts = np.array([
        [0, 0], [0, 20], [5, 15], [9, 24], 
        [12, 23], [8, 14], [15, 14]
    ], np.int32)
    
    frame_duration = 1.0 / fps
    next_frame_time = time.perf_counter() + frame_duration
    
    with mss.mss() as sct:
        try:
            while recording:
                img = np.array(sct.grab(monitor))
                
                # Draw cursor using ultra-fast ctypes directly on BGRA
                mx, my = get_mouse_pos()
                cx = int(mx - monitor["left"])
                cy = int(my - monitor["top"])
                
                if 0 <= cx < monitor["width"] and 0 <= cy < monitor["height"]:
                    cv2.circle(img, (cx, cy), 15, (0, 255, 255, 255), -1)
                    pts = cursor_pts + [cx, cy]
                    cv2.fillPoly(img, [pts], (255, 255, 255, 255))
                    cv2.polylines(img, [pts], True, (0, 0, 0, 255), 1)

                # CRITICAL: Crop frame to exactly match the even width/height declared to ffmpeg
                frame_bgra = np.ascontiguousarray(img[:height, :width, :])
                
                # High-precision busy-wait loop to guarantee flawlessly smooth frame pacing
                now = time.perf_counter()
                sleep_time = next_frame_time - now
                if sleep_time > 0:
                    if sleep_time > 0.002:
                        time.sleep(sleep_time - 0.002)
                    while time.perf_counter() < next_frame_time:
                        pass
                
                # Write frame
                writer.send(frame_bgra)
                next_frame_time += frame_duration
                
                # Frame Duplication: If capturing took too long (GPU busy during scroll), duplicate the frame
                # This guarantees constant 30 FPS stream and fixes "blinking" or jumping during scrolls
                while time.perf_counter() > next_frame_time:
                    writer.send(frame_bgra)
                    next_frame_time += frame_duration
                
        except Exception as e:
            print(f"\n[!] Video recording error: {e}")
            
    writer.close()

def record_audio(fs=44100):
    global recording
    print("[*] Starting microphone recording...")
    audio_data = []
    
    def callback(indata, frames, time_info, status):
        audio_data.append(indata.copy())
        
    # Increased blocksize to 4096 to prevent buffer underruns (fixes audio cracking/popping)
    with sd.InputStream(samplerate=fs, channels=1, callback=callback, blocksize=4096):
        while recording:
            time.sleep(0.1)
            
    print("[*] Saving audio...")
    if len(audio_data) > 0:
        audio_concat = np.concatenate(audio_data, axis=0)
        sf.write('temp_audio.wav', audio_concat, fs)

def merge_video_audio():
    print("\n[*] Saving video instantly, please wait...")
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # Use copy to instantly multiplex without re-encoding, avoiding long freezes
    cmd = [
        ffmpeg_exe, "-y",
        "-i", "temp_video.mp4",
        "-i", "temp_audio.wav",
        "-c:v", "copy",
        "-c:a", "aac",
        "demo_recording.mp4"
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists('temp_video.mp4'): os.remove('temp_video.mp4')
    if os.path.exists('temp_audio.wav'): os.remove('temp_audio.wav')
    print("\n[+] ✅ Final video saved instantly as: demo_recording.mp4 !")

def main():
    global recording
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Force Windows to use 1ms high-resolution timers to eliminate time.sleep jitter
    if platform.system() == 'Windows':
        import ctypes
        ctypes.windll.winmm.timeBeginPeriod(1)
    
    print("======================================================")
    print("   UNLIMITED SCREEN & AUDIO RECORDER")
    print("======================================================")
    
    # 1. Area selection
    monitor = select_region()
    
    print("\n======================================================")
    print(" INSTRUCTIONS :")
    print(" 1. The selected area and your microphone are currently recording.")
    print(" 2. The recording is unlimited. It will not stop automatically.")
    print(" 3. To STOP and save the recording, press the 'F12' key.")
    print("======================================================\n")
    
    t_video = threading.Thread(target=record_screen, args=(monitor,))
    t_audio = threading.Thread(target=record_audio)
    
    t_video.start()
    t_audio.start()
    
    try:
        while recording:
            # Replaced 'q' with 'F12' to prevent accidental termination while typing in the browser
            if keyboard.is_pressed('F12'):
                print("\n[*] F12 pressed. Stopping recording...")
                recording = False
                break
                
            time.sleep(0.05)
    except KeyboardInterrupt:
        recording = False
        
    t_video.join()
    t_audio.join()
    
    # 4. Merge Audio and Video
    merge_video_audio()

if __name__ == '__main__':
    main()
