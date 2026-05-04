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
OUTPUT_VIDEO_FINAL = "demo_recording_fr_natural.mp4"
TTS_VOICE = "fr-FR-RemyMultilingualNeural"
TTS_PITCH = "-10Hz"
TTS_RATE = "-5%" # Slightly slower for better clarity

# Detailed Script (French)
# Timestamps are in seconds
SCRIPT = [
    (0, 45, "Bonjour et bienvenue dans cette présentation complète d'EduManage, votre partenaire pour une gestion scolaire simplifiée et efficace. Nous commençons ici par l'initialisation de notre système de démonstration pour vous montrer la puissance de l'outil dès son lancement."),
    (45, 120, "Nous arrivons maintenant sur le tableau de bord principal. C'est le cœur de votre établissement. Comme vous pouvez le constater, l'interface est épurée et moderne. Vous avez immédiatement accès aux chiffres clés : le nombre total d'élèves inscrits, l'effectif complet de votre personnel, et bien sûr, un suivi financier en temps réel avec le revenu total affiché en haut à droite."),
    (120, 240, "Les graphiques en bas de page vous permettent de visualiser la santé financière de l'école, en comparant les revenus et les dépenses. À côté, le graphique de performance vous donne une vision claire du niveau académique par classe. C'est un outil indispensable pour les directeurs d'école qui souhaitent prendre des décisions basées sur des données précises."),
    (240, 360, "Explorons maintenant le répertoire des élèves. La gestion des inscriptions n'a jamais été aussi simple. Vous disposez d'une liste exhaustive où vous pouvez filtrer les étudiants par nom ou par classe. Pour chaque élève, vous avez des actions rapides : consulter son profil complet, générer un bulletin académique, ou modifier ses informations personnelles en un clin d'œil."),
    (360, 480, "La fluidité de la plateforme est l'un de ses points forts. Que vous passiez du module de scolarité au calendrier académique, tout se fait instantanément. Le calendrier vous permet de noter les dates d'examens, les réunions de parents ou les périodes de vacances. C'est une vue partagée qui assure que tout le monde, de l'administration aux enseignants, reste sur la même longueur d'onde."),
    (480, 540, "En descendant dans le menu, nous trouvons les services de frais et les annonces. Le module d'annonces est particulièrement utile pour communiquer des informations importantes à toute la communauté scolaire de manière officielle et structurée."),
    (540, 600, "Passons à une fonctionnalité essentielle : les rapports. EduManage vous permet de générer des rapports détaillés sur presque tous les aspects de votre école. Vous avez besoin d'un résumé des inscriptions, d'une liste de présence pour une classe spécifique, ou d'un rapport financier annuel ? Tout est là, prêt à être consulté ou exporté."),
    (600, 660, "L'exportation de données est extrêmement flexible. Vous pouvez télécharger vos listes d'étudiants, vos registres de paiements ou vos fiches de paie directement en format Excel ou CSV. Cela facilite grandement la comptabilité et le partage d'informations avec des intervenants externes."),
    (660, 720, "Comme vous pouvez le voir, l'interface s'adapte également à vos préférences de travail. Le mode sombre, que nous activons ici, offre une alternative élégante et reposante pour les yeux lors d'une utilisation prolongée. C'est ce souci du détail qui fait d'EduManage un logiciel premium."),
    (720, 800, "En résumé, EduManage n'est pas seulement un outil de gestion, c'est une véritable extension de votre équipe administrative. Il automatise les tâches répétitives, sécurise vos données et vous permet de vous concentrer sur ce qui compte vraiment : la réussite de vos élèves."),
    (800, 840, "Nous espérons que cette démonstration vous a donné un bon aperçu des capacités de notre solution. N'hésitez pas à nous contacter pour une présentation personnalisée ou pour toute question. Merci de nous avoir suivis et à bientôt sur EduManage !")
]

def setup_ffmpeg():
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    temp_bin_dir = tempfile.mkdtemp()
    shutil.copy(ffmpeg_exe, os.path.join(temp_bin_dir, "ffmpeg.exe"))
    os.environ["PATH"] = temp_bin_dir + os.pathsep + os.environ["PATH"]
    return temp_bin_dir, os.path.join(temp_bin_dir, "ffmpeg.exe")

async def generate_tts(text, output_path):
    communicate = edge_tts.Communicate(text, TTS_VOICE, pitch=TTS_PITCH, rate=TTS_RATE)
    await communicate.save(output_path)

def get_duration(file_path, ffmpeg_exe):
    cmd = [ffmpeg_exe, "-i", file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if match:
        h, m, s = match.groups()
        return float(h)*3600 + float(m)*60 + float(s)
    return 0.0

def format_srt_time(seconds):
    td = list(re.findall(r"(\d+):(\d+):(\d+\.\d+)", str(os.popen(f"echo {seconds}").read())) or [("00","00","0.0")])[0]
    # Simple formatting
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02}:{m:02}:{int(s):02},{int((s-int(s))*1000):03}"

async def main():
    _, ffmpeg_exe = setup_ffmpeg()
    
    tmp_dir = "tts_natural"
    if not os.path.exists(tmp_dir): os.makedirs(tmp_dir)
    
    audio_inputs = []
    filter_complex = ""
    srt_content = ""

    print("--- Generating Natural TTS segments ---")
    for i, (start, end, text) in enumerate(SCRIPT):
        tts_path = os.path.join(tmp_dir, f"nat_{i}.mp3")
        await generate_tts(text, tts_path)
        
        target_dur = end - start
        actual_dur = get_duration(tts_path, ffmpeg_exe)
        
        speed = actual_dur / target_dur
        # To make it sound human, we want to keep speed close to 1.0.
        # If the text is way too long, it will sound fast. 
        # But for these segments, I've balanced them.
        safe_speed = max(0.6, min(1.8, speed))
        
        adj_path = os.path.join(tmp_dir, f"nat_{i}_adj.mp3")
        subprocess.run([
            ffmpeg_exe, "-i", tts_path, "-filter:a", f"atempo={safe_speed}", "-y", adj_path
        ], capture_output=True)
        
        audio_inputs.append(adj_path)
        delay_ms = int(start * 1000)
        filter_complex += f"[{i+1}:a]adelay={delay_ms}|{delay_ms}[a{i}];"
        
        # SRT Entry
        srt_content += f"{i+1}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{text}\n\n"

    # Save SRT
    with open("subtitles_fr_natural.srt", "w", encoding="utf-8") as f:
        f.write(srt_content)

    inputs_str = "".join([f"[a{i}]" for i in range(len(audio_inputs))])
    filter_complex += f"{inputs_str}amix=inputs={len(audio_inputs)}:dropout_transition=0:normalize=0[outa]"

    print("--- Final Assembly ---")
    cmd = [ffmpeg_exe, "-i", INPUT_VIDEO]
    for path in audio_inputs:
        cmd.extend(["-i", path])
    
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[outa]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-y", "temp_natural.mp4"
    ])
    
    subprocess.run(cmd)

    # Add subtitles
    subprocess.run([
        ffmpeg_exe, "-i", "temp_natural.mp4", "-i", "subtitles_fr_natural.srt",
        "-c", "copy", "-c:s", "mov_text", "-y", OUTPUT_VIDEO_FINAL
    ])
    
    if os.path.exists("temp_natural.mp4"):
        os.remove("temp_natural.mp4")

    print(f"SUCCESS! Created {OUTPUT_VIDEO_FINAL}")

if __name__ == "__main__":
    asyncio.run(main())
