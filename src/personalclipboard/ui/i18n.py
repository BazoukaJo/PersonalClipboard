"""HUD strings. Speech recognition stays multilingual via Whisper auto-detect."""

from __future__ import annotations

LANGS = (
    ("en", "English"),
    ("fr", "Français"),
    ("es", "Español"),
)
LANG_CODES = tuple(code for code, _name in LANGS)


def ui_lang(lang: str) -> str:
    return lang if lang in LANG_CODES else "en"


_EN = {
    "mic": "Mic",
    "copy": "Copy",
    "history": "Clips",
    "clips": "Clips",
    "records": "Records",
    "hide": "Hide",
    "app_title": "Clipboard",
    "voice": "Voice",
    "hearing": "Hearing",
    "type": "Type",
    "meeting": "Recording",
    "record": "Record",
    "record_meeting": "Meeting",
    "record_playback": "Playback",
    "stop_save": "Stop",
    "settings": "Settings",
    "language": "Language",
    "opacity": "Opacity",
    "opacity_tip": "How solid the overlay is. 100% is fully opaque.",
    "whisper": "Whisper",
    "corrector": "Corrector",
    "vad": "Idle mic when quiet",
    "predict": "Suggest while typing",
    "empty": "Ready to paste",
    "type_hint": "Type, Tab to accept, then Enter or a period.",
    "meet_hint": "Finished phrases appear here after correction.",
    "meet_tip": (
        "Meeting: transcribe your microphone and what you hear "
        "(speakers or headphones). Saves a markdown file on the desktop. "
        "Does not copy to the clipboard."
    ),
    "playback_tip": (
        "Playback: transcribe only what you hear — YouTube, a video, or another app. "
        "Uses speakers or headphones, not the microphone. "
        "Saves a markdown file on the desktop. Does not capture the picture."
    ),
    "record_menu_tip": (
        "Choose Meeting (mic + speakers) or Playback (speakers only, for YouTube and videos)."
    ),
    "mic_tip": "Master privacy switch. Off stops the microphone and the wake probe.",
    "history_tip": "Clipboard history. Open a clip to copy it again.",
    "clips_tip": "Clipboard history. Open a clip to copy it again.",
    "records_tip": "Saved meeting and playback transcripts on the desktop.",
    "records_empty": "No meeting or playback records yet. Use Record to save one.",
    "records_empty_preview": "No phrases saved in this file.",
    "records_open_tip": "Open the full transcript.",
    "history_empty": "No clipboard history yet.",
    "history_copy_tip": "Copy this text to the clipboard.",
    "close": "Close",
    "close_tip": "Close this window.",
    "back": "Back",
    "back_tip": "Return to the list of records.",
    "open_file": "Open file",
    "open_file_tip": "Open this markdown file in your default app.",
    "kind_meeting": "Meeting",
    "kind_playback": "Playback",
    "copy_tip": "Copy the last finished sentence to the clipboard again.",
    "copy_meet_tip": "Recording is saving to a desktop file, not the clipboard.",
    "hide_tip": "Hide this overlay. Click the tray icon to show it again.",
    "vad_tip": "After a short silence, stop the microphone and Whisper. Speech wakes them.",
    "predict_tip": "Grey ghost text in Type while the field is focused. Tab inserts it.",
    "clear": "Clear",
    "clear_tip": "Clear the Type field.",
    "retry_tip": "Try another wording of this sentence.",
    "settings_tip": "Language, opacity, Whisper model, corrector, idle-mic, and type-ahead.",
    "language_tip": "Language of this overlay. Speech recognition still auto-detects.",
    "whisper_tip": "Faster-Whisper model on this PC. Changing it reloads CUDA weights.",
    "corrector_tip": "Local Ollama model that corrects finished sentences.",
    "voice_tip": (
        "Spoken dictation. Separate from Type. Finish with a period to fix "
        "grammar and copy. Always kept readable for a person."
    ),
    "voice_role": "Dictation",
    "voice_phrase_tip": "Last spoken sentence. Copy puts it on the clipboard again.",
    "hearing_tip": "What Whisper hears right now. This is a partial, not the saved sentence.",
    "type_tip": (
        "Typed text, separate from Voice. Enter or a period corrects and copies. "
        "The icons next to Type choose human or AI correction. Tab accepts the grey suggestion."
    ),
    "type_phrase_tip": "Last typed sentence after correction. Copy puts it on the clipboard again.",
    "correct_human_tip": (
        "Human: fix grammar and punctuation. Keep your wording and tone. For people."
    ),
    "correct_ai_tip": (
        "AI: fully reformulate as a prompt for another model. Does not answer the request."
    ),
    "phrase_tip": "Last finished sentence. Copy puts it on the clipboard again.",
    "status_tip": "Capture state. Green is live, grey is idle, red is off.",
    "brand_tip": "Drag to move this overlay.",
    "status_off": "Mic off",
    "status_loading": "Loading",
    "status_listening": "Listening",
    "status_uncertain": "Other voice",
    "status_locked": "Your voice",
    "status_recording": "Recording",
    "status_error": "Error",
    "status_quiet": "Quiet",
    "flash_copied": "Copied",
    "flash_saved": "Saved",
    "flash_correcting": "Correcting",
    "flash_empty": "Empty",
    "flash_loading": "Loading",
    "flash_error": "Error",
    "live": "Live",
}

_FR = {
    **_EN,
    "mic": "Micro",
    "copy": "Copier",
    "history": "Historique",
    "hide": "Masquer",
    "app_title": "Presse-papiers",
    "voice": "Voix",
    "hearing": "Écoute",
    "type": "Saisie",
    "meeting": "Réunion",
    "record": "Enregistrer",
    "stop_save": "Arrêter",
    "settings": "Réglages",
    "language": "Langue",
    "opacity": "Opacité",
    "opacity_tip": "Opacité de la fenêtre. 100 % = opaque.",
    "whisper": "Whisper",
    "corrector": "Correcteur",
    "vad": "Couper le micro au silence",
    "predict": "Suggérer pendant la saisie",
    "empty": "Prêt à coller",
    "type_hint": "Saisissez, Tab pour accepter, puis Entrée ou un point.",
    "meet_hint": "La transcription apparaît ici.",
    "meet_tip": (
        "Transcrit la pièce (micro et son des haut-parleurs ou du casque) "
        "et enregistre des notes sur le bureau. Pas de presse-papiers."
    ),
    "mic_tip": "Désactivé arrête le microphone.",
    "history_tip": "Affiche l’historique. Copiez n’importe quelle entrée.",
    "history_empty": "Aucun historique pour le moment.",
    "history_copy_tip": "Copie ce texte dans le presse-papiers.",
    "close": "Fermer",
    "copy_tip": "Recopie la dernière phrase terminée",
    "copy_meet_tip": "La parole va dans les notes, pas le presse-papiers.",
    "hide_tip": "Masque la fenêtre. Cliquez l’icône de la barre pour l’afficher.",
    "vad_tip": "Après un silence, arrête le micro et Whisper. La parole les relance.",
    "predict_tip": "Texte fantôme dans Saisie tant que le champ est actif. Tab l’insère.",
    "clear": "Effacer",
    "clear_tip": "Efface le champ Saisie.",
    "retry_tip": "Propose une autre formulation de cette phrase.",
    "status_off": "Micro off",
    "status_loading": "Chargement",
    "status_listening": "Écoute",
    "status_uncertain": "Autre voix",
    "status_locked": "Votre voix",
    "status_recording": "Enregistrement",
    "status_error": "Erreur",
    "status_quiet": "Silence",
    "flash_copied": "Copié",
    "flash_saved": "Enregistré",
    "flash_correcting": "Correction",
    "flash_empty": "Vide",
    "flash_loading": "Chargement",
    "flash_error": "Erreur",
    "live": "Direct",
    "clips": "Extraits",
    "records": "Notes",
    "record_meeting": "Réunion",
    "record_playback": "Lecture",
    "stop_save": "Arrêter",
    "meet_hint": "Les phrases corrigées apparaissent ici.",
    "meet_tip": (
        "Réunion : transcrit le micro et ce que vous entendez "
        "(haut-parleurs ou casque). Fichier markdown sur le bureau. "
        "Pas de presse-papiers."
    ),
    "playback_tip": (
        "Lecture : transcrit seulement ce que vous entendez — YouTube, une vidéo, "
        "une autre appli. Pas le micro, pas l’image. Fichier sur le bureau."
    ),
    "record_menu_tip": "Réunion (micro + haut-parleurs) ou Lecture (haut-parleurs seulement).",
    "clips_tip": "Historique du presse-papiers. Ouvrez un extrait pour le recopier.",
    "records_tip": "Transcriptions réunion et lecture enregistrées sur le bureau.",
    "records_empty": "Aucune note pour l’instant. Utilisez Enregistrer.",
    "records_empty_preview": "Aucune phrase dans ce fichier.",
    "records_open_tip": "Ouvrir la transcription complète.",
    "close_tip": "Fermer cette fenêtre.",
    "back": "Retour",
    "back_tip": "Retour à la liste des notes.",
    "open_file": "Ouvrir le fichier",
    "open_file_tip": "Ouvre ce fichier markdown dans l’appli par défaut.",
    "kind_meeting": "Réunion",
    "kind_playback": "Lecture",
    "settings_tip": "Langue, opacité, Whisper, correcteur, micro au silence, suggestions.",
    "language_tip": "Langue de l’interface. La reconnaissance reste automatique.",
    "whisper_tip": "Modèle Faster-Whisper sur ce PC. Le changer recharge le GPU.",
    "corrector_tip": "Modèle Ollama local qui corrige les phrases terminées.",
    "voice_tip": (
        "Dictée parlée, distincte de la saisie. Terminez par un point pour "
        "corriger et copier. Toujours lisible pour une personne."
    ),
    "voice_role": "Dictée",
    "voice_phrase_tip": "Dernière phrase dictée. Copier la remet dans le presse-papiers.",
    "hearing_tip": "Ce que Whisper entend maintenant. Hypothèse partielle, pas la phrase sauvée.",
    "type_tip": (
        "Texte saisi, distinct de la voix. Entrée ou un point corrige et copie. "
        "Les icônes à côté de Saisie choisissent la correction humaine ou IA. "
        "Tab accepte la suggestion."
    ),
    "type_phrase_tip": "Dernière phrase saisie après correction. Copier la remet dans le presse-papiers.",
    "correct_human_tip": (
        "Humain : corrige grammaire et ponctuation. Garde vos mots et votre ton. Pour les gens."
    ),
    "correct_ai_tip": (
        "IA : reformule entièrement en consigne pour un autre modèle. Ne répond pas à la demande."
    ),
    "phrase_tip": "Dernière phrase terminée. Copier la remet dans le presse-papiers.",
    "status_tip": "État de la capture. Vert = actif, gris = pause, rouge = off.",
    "brand_tip": "Glissez pour déplacer la fenêtre.",
    "copy_meet_tip": "L’enregistrement va dans un fichier, pas le presse-papiers.",
}

_ES = {
    **_EN,
    "mic": "Mic",
    "copy": "Copiar",
    "history": "Historial",
    "hide": "Ocultar",
    "app_title": "Portapapeles",
    "voice": "Voz",
    "hearing": "Oyendo",
    "type": "Escribir",
    "meeting": "Reunión",
    "record": "Grabar",
    "stop_save": "Parar y guardar",
    "settings": "Ajustes",
    "language": "Idioma",
    "opacity": "Opacidad",
    "opacity_tip": "Qué tan sólida es la ventana. 100% es opaca.",
    "corrector": "Corrector",
    "vad": "Apagar el micrófono en silencio",
    "predict": "Sugerir al escribir",
    "empty": "Listo para pegar",
    "type_hint": "Escriba, Tab para aceptar, luego Enter o un punto.",
    "meet_hint": "La transcripción aparece aquí.",
    "meet_tip": (
        "Transcribe la sala (micrófono y audio de altavoces o auriculares) "
        "y guarda notas en el escritorio. No usa el portapapeles."
    ),
    "mic_tip": "Desactivado detiene el micrófono.",
    "history_tip": "Muestra el historial. Copie cualquier entrada.",
    "history_empty": "Aún no hay historial.",
    "history_copy_tip": "Copia este texto al portapapeles.",
    "close": "Cerrar",
    "copy_tip": "Copia de nuevo la última frase",
    "copy_meet_tip": "El habla va a las notas, no al portapapeles.",
    "hide_tip": "Oculta la ventana. Clic en la bandeja para mostrarla.",
    "vad_tip": "Tras un silencio, para el micrófono y Whisper. El habla los despierta.",
    "predict_tip": "Texto fantasma en Escribir con el campo activo. Tab lo inserta.",
    "clear": "Borrar",
    "clear_tip": "Borra el campo Escribir.",
    "retry_tip": "Prueba otra redacción de esta frase.",
    "status_off": "Mic off",
    "status_loading": "Cargando",
    "status_listening": "Escuchando",
    "status_uncertain": "Otra voz",
    "status_locked": "Tu voz",
    "status_recording": "Grabando",
    "status_error": "Error",
    "status_quiet": "Silencio",
    "flash_copied": "Copiado",
    "flash_saved": "Guardado",
    "flash_correcting": "Corrigiendo",
    "flash_empty": "Vacío",
    "flash_loading": "Cargando",
    "flash_error": "Error",
    "live": "En vivo",
    "clips": "Clips",
    "records": "Notas",
    "record_meeting": "Reunión",
    "record_playback": "Reproducción",
    "stop_save": "Parar",
    "meet_hint": "Las frases corregidas aparecen aquí.",
    "meet_tip": (
        "Reunión: transcribe el micrófono y lo que oye "
        "(altavoces o auriculares). Archivo markdown en el escritorio. "
        "No usa el portapapeles."
    ),
    "playback_tip": (
        "Reproducción: transcribe solo lo que oye — YouTube, un vídeo u otra app. "
        "Sin micrófono y sin imagen. Archivo en el escritorio."
    ),
    "record_menu_tip": "Reunión (mic + altavoces) o Reproducción (solo altavoces).",
    "clips_tip": "Historial del portapapeles. Abra un clip para copiarlo de nuevo.",
    "records_tip": "Transcripciones de reunión y reproducción en el escritorio.",
    "records_empty": "Aún no hay notas. Use Grabar para guardar una.",
    "records_empty_preview": "No hay frases en este archivo.",
    "records_open_tip": "Abrir la transcripción completa.",
    "close_tip": "Cerrar esta ventana.",
    "back": "Atrás",
    "back_tip": "Volver a la lista de notas.",
    "open_file": "Abrir archivo",
    "open_file_tip": "Abre este markdown con la aplicación predeterminada.",
    "kind_meeting": "Reunión",
    "kind_playback": "Reproducción",
    "settings_tip": "Idioma, opacidad, Whisper, corrector, micrófono en silencio y sugerencias.",
    "language_tip": "Idioma de la interfaz. El reconocimiento sigue siendo automático.",
    "whisper_tip": "Modelo Faster-Whisper en este PC. Cambiarlo recarga CUDA.",
    "corrector_tip": "Modelo Ollama local que corrige las frases terminadas.",
    "voice_tip": (
        "Dictado hablado, aparte de Escribir. Termine con un punto para "
        "corregir y copiar. Siempre legible para una persona."
    ),
    "voice_role": "Dictado",
    "voice_phrase_tip": "Última frase dictada. Copiar la vuelve a poner en el portapapeles.",
    "hearing_tip": "Lo que Whisper oye ahora. Es una hipótesis, no la frase guardada.",
    "type_tip": (
        "Texto escrito, aparte de Voz. Enter o un punto corrige y copia. "
        "Los iconos junto a Escribir eligen corrección humana o IA. "
        "Tab acepta la sugerencia."
    ),
    "type_phrase_tip": "Última frase escrita tras la corrección. Copiar la vuelve a poner en el portapapeles.",
    "correct_human_tip": (
        "Humano: corrige gramática y puntuación. Conserva tus palabras y tu tono. Para personas."
    ),
    "correct_ai_tip": (
        "IA: reformula por completo como indicación para otro modelo. No responde a la petición."
    ),
    "phrase_tip": "Última frase terminada. Copiar la vuelve a poner en el portapapeles.",
    "status_tip": "Estado de captura. Verde = activo, gris = inactivo, rojo = off.",
    "brand_tip": "Arrastre para mover esta ventana.",
    "copy_meet_tip": "La grabación va a un archivo, no al portapapeles.",
}

STRINGS = {"en": _EN, "fr": _FR, "es": _ES}


def t(lang: str, key: str) -> str:
    table = STRINGS.get(lang) or _EN
    return table.get(key) or _EN.get(key) or key


def flash_key(label: str) -> str:
    mapping = {
        "Copied": "flash_copied",
        "Saved": "flash_saved",
        "Correcting": "flash_correcting",
        "Empty": "flash_empty",
        "Loading": "flash_loading",
        "Error": "flash_error",
    }
    return mapping.get(label, "")
