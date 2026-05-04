import os
import sys
import asyncio
import edge_tts
import subprocess
import shutil
import tempfile
import imageio_ffmpeg
import re
from datetime import timedelta

# Configuration
INPUT_VIDEO = "demo_recording_fr_refined.mp4"
OUTPUT_VIDEO_FINAL = "demo_recording_fr_final.mp4"
TTS_VOICE = "fr-FR-RemyMultilingualNeural"
TTS_PITCH = "-10Hz"
SPEED_FACTOR = 1.0 # The source is already at 1.15x speed

REFINED_SEGMENTS = {
    1: "Bonjour à tous et bienvenue. Aujourd'hui, nous allons découvrir ensemble une solution de gestion scolaire innovante.",
    2: "Nous allons explorer Ed Solution, un logiciel de gestion scolaire complet, spécialement conçu pour répondre aux besoins spécifiques des établissements d'enseignement primaire et secondaire, avec une interface moderne.",
    3: "Il s'agit d'un système robuste qui centralise absolument toutes les opérations administratives, pédagogiques et financières de votre école.",
    4: "Nous allons maintenant vous démontrer concrètement comment cet outil fonctionne au quotidien pour simplifier la vie de votre administration.",
    5: "Pour commencer, nous voici dans l'interface d'administration principale. C'est ici, sur cette page de connexion sécurisée, que l'administrateur peut s'identifier pour accéder au système.",
    6: "Il vous suffit de saisir vos identifiants personnels pour déverrouiller l'accès complet à l'ensemble des modules du logiciel.",
    7: "Si vous disposez d'un accès administrateur, vous pouvez vous connecter depuis n'importe quel poste de travail, que ce soit sur une application Windows ou directement via votre navigateur web.",
    8: "L'administrateur principal, qui est généralement la personne ayant acquis la licence du logiciel, possède les droits pour configurer le système et déléguer des accès spécifiques aux autres membres.",
    9: "Il est très simple d'embaucher et d'enregistrer de nouveaux membres du personnel administratif au sein du logiciel pour vous aider dans la gestion quotidienne et le suivi de l'ensemble du système scolaire.",
    10: "Cette fonctionnalité permet de répartir efficacement les tâches, les responsabilités et les flux de travail entre les différents utilisateurs du logiciel, garantissant ainsi une organisation fluide.",
    11: "Faisons un test pratique : essayons de nous connecter immédiatement en utilisant un compte avec des privilèges d'administrateur pour voir l'étendue des fonctionnalités disponibles.",
    12: "Une fois la connexion établie, nous sommes automatiquement redirigés vers le tableau de bord principal de l'administration, qui regroupe toutes les informations essentielles de votre établissement.",
    13: "Notez bien que ce tableau de bord est exclusivement réservé à l'administrateur et aux profils spécifiquement autorisés pour garantir la sécurité des données.",
    14: "Les autres membres du personnel, comme les enseignants ou les comptables, auront des accès restreints et personnalisés en fonction de leurs rôles et responsabilités respectifs.",
    15: "C'est seulement en leur fournissant les identifiants et les permissions appropriés qu'ils pourront accéder aux sections et aux outils qui concernent directement leur travail quotidien.",
    16: "Au sein de ce tableau de bord, vous trouverez une statistique récapitulative complète des données et des informations relatives à chaque étudiant et à la vie de l'école.",
    17: "Comme vous pouvez le voir ici, nous avons un aperçu direct du nombre total d'élèves inscrits dans l'école, ainsi que de l'effectif complet du personnel enseignant et administratif.",
    18: "On y retrouve également le nombre total de classes ouvertes et le nombre d'utilisateurs actuellement actifs sur le système, ce qui permet un suivi précis de l'activité en temps réel.",
    19: "En tant qu'administrateur, je peux facilement gérer les droits et les accès pour que chaque collaborateur puisse travailler sereinement sur les modules qui lui sont dédiés dans le système.",
    20: "Chaque utilisateur est ainsi limité aux fonctionnalités strictement nécessaires à sa mission, ce qui simplifie l'interface et renforce la sécurité des informations sensibles de l'établissement.",
    21: "Vous avez également une vue d'ensemble sur les revenus totaux de l'école. Ce module permet de suivre la santé financière, en analysant les dépenses et les revenus sur une période d'un an.",
    22: "Le système permet aussi de visualiser les performances académiques pour chaque niveau, vous permettant d'identifier rapidement quelles classes sont les plus performantes et lesquelles nécessitent un suivi.",
    23: "Le suivi de l'assiduité est également intégré. En vous basant sur le nombre total d'élèves, vous pouvez monitorer précisément le taux de présence quotidien et global au sein de votre école.",
    24: "On peut aussi analyser la répartition du personnel par rôle ou par genre. Comme vous pouvez le constater, le logiciel offre une vision très détaillée et multi-dimensionnelle de votre organisation humaine.",
    25: "La section des alertes est cruciale pour la communication. Si vous envoyez des messages groupés aux élèves, au personnel ou aux parents, vous pouvez tout gérer ici, y compris le calendrier des événements scolaires.",
    26: "Un module d'annonce complet est disponible pour diffuser les nouvelles. Notez qu'il est très facile de changer la langue du logiciel ; passons par exemple l'interface en français pour la suite de la démo.",
    27: "C'est une manipulation simple et rapide qui se fait en quelques clics seulement dans les paramètres de réglage de votre profil utilisateur.",
    28: "Maintenant que nous avons basculé en français, explorons la section dédiée aux étudiants. C'est ici que vous pouvez modifier, manipuler les dossiers, ajouter de nouveaux élèves et gérer toutes leurs informations académiques.",
    29: "Vous pouvez gérer les résultats, imprimer les cartes d'identité scolaires et consulter chaque profil en détail. La plateforme offre une flexibilité totale pour promouvoir les élèves d'un niveau à l'autre ou même supprimer des dossiers si nécessaire. Tout est conçu pour être géré de manière intuitive, vous permettant de gagner un temps précieux sur les tâches administratives répétitives liées aux élèves.",
    30: "Accédons ensuite aux sections académiques où vous pouvez organiser la vie scolaire : ajouter de nouvelles classes, définir les matières enseignées et créer des emplois du temps personnalisés pour chaque groupe. Vous avez également la possibilité de prendre les présences de manière numérique, garantissant ainsi un suivi rigoureux et une centralisation parfaite de toutes les activités pédagogiques de votre établissement.",
    31: "Le suivi financier est tout aussi performant. Vous pouvez surveiller les finances de l'école, gérer les dépenses courantes et suivre les revenus totaux de manière transparente. Le logiciel vous permet de garder un œil constant sur la trésorerie grâce à des outils de reporting intégrés, vous aidant ainsi à maintenir une gestion budgétaire saine et équilibrée pour votre institution au fil des mois et des années.",
    32: "La gestion du personnel est un autre point fort. Vous pouvez monitorer les enseignants et le staff, imprimer leurs cartes d'identification et éditer leurs données personnelles. Le module permet aussi de prendre les présences du personnel et de suivre toutes leurs transactions financières, incluant les paiements de salaires, la génération de reçus officiels et bien d'autres options administratives essentielles.",
    33: "Vous avez la possibilité d'ajouter de nouveaux utilisateurs dans le système en toute simplicité. De plus, la gestion des congés est intégrée : si un membre du personnel a besoin de s'absenter pour des raisons personnelles ou de santé, il peut formuler sa demande directement via le logiciel, permettant ainsi une validation structurée et un suivi clair des absences au sein de votre équipe.",
    34: "Le calendrier intégré est un outil de planification puissant. Vous pouvez y créer des événements, concevoir des rappels et ajouter des dates clés pour l'école. Chaque événement créé peut être automatiquement annoncé par e-mail ou par SMS aux personnes concernées, assurant ainsi une communication fluide. C'est aussi ici que vous pouvez gérer la création de reçus et d'autres documents officiels.",
    35: "Gérez absolument toutes les données de votre établissement, des élèves au personnel, avec une simplicité déconcertante. Vous pouvez également effectuer des annonces officielles qui seront visibles par tous les utilisateurs autorisés du système.",
    36: "Pour les écoles équipées, nous proposons une gestion de bibliothèque complète. Vous pouvez répertorier tous les livres, suivre les emprunts en cours, savoir qui a emprunté quel ouvrage et gérer les retours. C'est un excellent moyen de maintenir votre inventaire à jour et de favoriser l'accès à la lecture pour tous vos étudiants et votre personnel enseignant de manière organisée.",
    37: "Le logiciel inclut également un module de centre de santé scolaire. C'est ici que vous pouvez créer et suivre les dossiers médicaux des élèves. Si un étudiant ne se sent pas bien, vous pouvez enregistrer les soins prodigués et maintenir un historique de santé pour chaque enfant, garantissant ainsi une prise en charge sécurisée et un suivi attentif au sein de l'infirmerie de votre établissement.",
    38: "Les services de transport ne sont pas oubliés. Vous pouvez configurer les moyens de transport pour les élèves qui en ont besoin, gérer les trajets et suivre les abonnements. C'est une fonctionnalité très appréciée pour assurer la sécurité et la logistique des déplacements des étudiants, que ce soit pour les trajets quotidiens ou pour des sorties scolaires spécifiques organisées par l'école.",
    39: "En plus de ces nombreuses fonctions, Ed Solution supporte des technologies modernes comme le scanner d'empreintes digitales pour la prise de présence. Cela garantit une fiabilité totale et une rapidité d'exécution lors de l'arrivée des élèves ou du personnel le matin, éliminant ainsi les erreurs de saisie manuelle et les oublis potentiels.",
    40: "L'impression des cartes d'identité est un jeu d'enfant, et le moteur de recherche puissant vous permet de retrouver n'importe quel dossier ou information instantanément. Comme vous pouvez le voir ici, je recherche une information précise et le système me donne le résultat immédiatement, ce qui est extrêmement pratique lors des pics d'activité administrative.",
    41: "La recherche est rapide. Regardez comment je trouve les informations en un instant.",
    42: "Enfin, l'interface est totalement personnalisable pour votre confort. Vous pouvez passer très facilement du mode clair au mode sombre, selon ce que vous préférez pour votre environnement de travail quotidien.",
    43: "Pour ceux d'entre nous qui ont une sensibilité oculaire, il est préférable d'utiliser le mode sombre comme celui-ci. Cela réduit considérablement la fatigue visuelle car la lumière de l'écran ne vient pas agresser vos yeux, surtout lors des longues sessions de travail administratif.",
    44: "Comme vous avez pu le constater, Ed Solution possède énormément de fonctionnalités pour transformer votre école. Merci beaucoup de votre attention et passez une excellente journée."
}

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
    
    matches = re.findall(r"(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\n|\n$|$)", content, re.DOTALL)
    for m in matches:
        def to_sec(t):
            h, mi, s = t.replace(',', '.').split(':')
            return float(h)*3600 + float(mi)*60 + float(s)
        segments.append({
            'index': int(m[0]),
            'start': to_sec(m[1]),
            'end': to_sec(m[2]),
            'text': m[3].strip()
        })
    return segments

async def generate_tts(text, output_path):
    communicate = edge_tts.Communicate(text, TTS_VOICE, pitch=TTS_PITCH)
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
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02}:{m:02}:{int(s):02},{int((s-int(s))*1000):03}"

async def main():
    _, ffmpeg_exe = setup_ffmpeg()
    orig_segments = parse_srt("subtitles_fr_refined.srt")
    
    tmp_dir = "tts_refined"
    if not os.path.exists(tmp_dir): os.makedirs(tmp_dir)
    
    audio_inputs = []
    filter_complex = ""
    srt_content = ""

    print(f"--- Processing {len(orig_segments)} segments at {SPEED_FACTOR}x speed ---")
    
    for seg in orig_segments:
        idx = seg['index']
        refined_text = REFINED_SEGMENTS.get(idx, seg['text'])
        
        # Adjust timing for speed-up
        start_adj = seg['start'] / SPEED_FACTOR
        end_adj = seg['end'] / SPEED_FACTOR
        target_dur = end_adj - start_adj
        
        tts_path = os.path.join(tmp_dir, f"ref_{idx}.mp3")
        await generate_tts(refined_text, tts_path)
        
        actual_dur = get_duration(tts_path, ffmpeg_exe)
        
        # Calculate needed atempo to fit target_dur
        # speed = current_dur / target_dur
        speed = actual_dur / target_dur
        safe_speed = max(0.5, min(2.0, speed))
        
        adj_path = os.path.join(tmp_dir, f"ref_{idx}_adj.mp3")
        subprocess.run([
            ffmpeg_exe, "-i", tts_path, "-filter:a", f"atempo={safe_speed}", "-y", adj_path
        ], capture_output=True, check=True)
        
        audio_inputs.append(adj_path)
        delay_ms = int(start_adj * 1000)
        filter_complex += f"[{len(audio_inputs)}:a]adelay={delay_ms}|{delay_ms}[a{idx}];"
        
        srt_content += f"{idx}\n{format_srt_time(start_adj)} --> {format_srt_time(end_adj)}\n{refined_text}\n\n"

    with open("subtitles_fr_refined.srt", "w", encoding="utf-8") as f:
        f.write(srt_content)

    print(f"--- Final Assembly (including video speed-up) ---")
    print(f"Filter complex length: {len(filter_complex)}")
    inputs_str = "".join([f"[a{seg['index']}]" for seg in orig_segments])
    # Video filter: setpts=PTS/factor
    # Audio filter: amix...
    filter_complex += f"[0:v]setpts=PTS/{SPEED_FACTOR}[v];"
    filter_complex += f"{inputs_str}amix=inputs={len(orig_segments)}:dropout_transition=0:normalize=0[outa]"
    
    with open("filter_complex.txt", "w") as f:
        f.write(filter_complex)
    print("Created filter_complex.txt")

    cmd = [ffmpeg_exe, "-i", INPUT_VIDEO]
    for path in audio_inputs:
        cmd.extend(["-i", path])
    
    cmd.extend([
        "-filter_complex_script", "filter_complex.txt",
        "-map", "[v]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-y", "temp_refined_no_sub.mp4"
    ])
    
    subprocess.run(cmd, check=True)

    print("--- Adding Subtitles ---")
    subprocess.run([
        ffmpeg_exe, "-i", "temp_refined_no_sub.mp4", "-i", "subtitles_fr_refined.srt",
        "-c", "copy", "-c:s", "mov_text", "-y", OUTPUT_VIDEO_FINAL
    ], check=True)
    
    # Cleanup
    for f in ["temp_refined_no_sub.mp4"]:
        if os.path.exists(f): os.remove(f)

    print(f"SUCCESS! Created {OUTPUT_VIDEO_FINAL}")

if __name__ == "__main__":
    asyncio.run(main())
