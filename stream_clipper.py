#!/usr/bin/env python3
"""Video Clipper - Interface graphique pour extraire et concaténer des segments vidéo."""

import os
import sys
import tempfile
import streamlit as st

# S'assurer que le dossier du projet est dans le path pour importer video_clipper
sys.path.insert(0, os.path.dirname(__file__))

from video_clipper import (
    parse_timestamp,
    format_timestamp,
    get_video_duration,
    extract_and_concat,
)

SEGMENT_COLORS = [
    "#1f77b4",  # bleu
    "#ff7f0e",  # orange
    "#2ca02c",  # vert
    "#d62728",  # rouge
    "#9467bd",  # violet
    "#8c564b",  # marron
    "#e377c2",  # rose
    "#7f7f7f",  # gris
    "#17becf",  # cyan
    "#bcbd22",  # olive
]


def file_system_selector(root_path: str = ".", extensions: list = ['mp4', 'mov', 'avi']):
    """
    rajout avec Euria - 18 09 2026
    >>> Peux m'écrire pour streamlit une fonction qui permet de lister et selectionner le contenu d'un dossier (en commençant pas '.'), en tilisant os.listdir() par exemple,  et qui permet aussi de changer de dossier.
    >>> C'est bien ce que je veux, peux tu réécrire avec un filtre sur les extensions de fichiers, et un liste d'extensions possibles comme argument de la fonction
    + qq modifs
    Un widget personnalisé pour naviguer dans le système de fichiers local avec filtrage par extension.
    
    Args:
        root_path (str): Le chemin de départ (défaut: dossier du script).
        extensions (list): Liste des extensions acceptées (ex: [".csv", ".txt", ".pdf"]). 
                           Si None, tous les fichiers sont affichés.
    
    Returns:
        str | None: Le chemin complet du fichier sélectionné, ou None si aucun fichier n'est choisi.
    """
    # Normalisation des extensions (minuscules, avec point)
    allowed_exts = None
    if extensions:
        allowed_exts = [ext.lower() if ext.startswith('.') else f".{ext.lower()}" for ext in extensions]

    # Initialisation du chemin actuel dans la session si inexistant
    if "current_dir" not in st.session_state:
        st.session_state.current_dir = os.path.abspath(root_path)
    
    # Affichage du chemin actuel
    st.text_input("Dossier actuel", value=st.session_state.current_dir, disabled=True)
    
    # Liste des éléments du dossier
    try:
        items = os.listdir(st.session_state.current_dir)
    except PermissionError:
        st.error("Permission refusée pour accéder à ce dossier.")
        return None
    except FileNotFoundError:
        st.error("Le dossier n'existe plus.")
        # Reset au dossier racine en cas d'erreur
        st.session_state.current_dir = os.path.abspath(root_path)
        st.rerun()
        return None

    # Séparation dossiers et fichiers
    folders = []
    files = []
    
    for item in items:
        full_path = os.path.join(st.session_state.current_dir, item)
        if os.path.isdir(full_path):
            if item[0] != '.':
                folders.append(item)
        elif os.path.isfile(full_path):
            # Filtrage par extension si la liste est fournie
            if allowed_exts:
                _, ext = os.path.splitext(item)
                if ext.lower() in allowed_exts:
                    files.append(item)
            else:
                files.append(item)
    
    # Tri alphabétique
    folders.sort(key=str.lower)
    files.sort(key=str.lower)

    st.markdown("### sélectionne un fichier vidéo")
    st.markdown(f"*extensions: {' , '.join(extensions)}*")
    
    # Bouton pour remonter au dossier parent
    parent_dir = os.path.dirname(st.session_state.current_dir)
    if st.button("📁 .. (Dossier parent)", use_container_width=True, key="btn_parent"):
        st.session_state.current_dir = parent_dir
        st.rerun()

    # Affichage des dossiers
    for folder in folders:
        if st.button(f"📂 {folder}", key=f"dir_{folder}", use_container_width=True):
            st.session_state.current_dir = os.path.join(st.session_state.current_dir, folder)
            st.rerun()

    # Affichage des fichiers filtrés
    selected_file = None
    
    if not files and allowed_exts:
        st.info(f"Aucun fichier avec les extensions {allowed_exts} dans ce dossier.")
    
    for file in files:
        if st.button(f"📄 {file}", key=f"file_{file}", use_container_width=True):
            selected_file = os.path.join(st.session_state.current_dir, file)
    
    if selected_file:
        st.success(f"Fichier sélectionné : {selected_file}")
        return selected_file
    
    return None

def file_selector(folder_path='.', label='Choisis un fichier', help=None):
    """
    from https://discuss.streamlit.io/t/file-browser-to-select-a-folder-or-a-file/49325
    hum, ça marche pas, on ne peut pas changer le folder_path ..."""
    filenames = os.listdir(folder_path)
    selected_filename = st.selectbox(label, filenames, help=help)
    return os.path.join(folder_path, selected_filename)


def init_state():
    """Initialiser les variables d'état de la session."""
    st.session_state.setdefault("video_path", None)
    st.session_state.setdefault("video_duration", None)
    st.session_state.setdefault("video_name", "")
    st.session_state.setdefault("segments", [])
    st.session_state.setdefault("output_file", None)
    st.session_state.setdefault("processing", False)
    st.session_state.setdefault("result", None)
    st.session_state.setdefault("error", None)


def render_timeline(total_duration, segments):
    """Afficher une barre de timeline visuelle montrant les segments sélectionnés."""
    if not segments or total_duration <= 0:
        return

    with st.container(border=True):
        st.caption(":material/analytics: Timeline")
        track_html_parts = [
            '<div style="position:relative;height:28px;background:#e0e0e0;border-radius:6px;overflow:hidden;">'
        ]
        for i, (start, end) in enumerate(segments):
            left_pct = (start / total_duration) * 100
            width_pct = ((end - start) / total_duration) * 100
            color = SEGMENT_COLORS[i % len(SEGMENT_COLORS)]
            title = f"Segment {i+1}: {format_timestamp(start)} - {format_timestamp(end)}"
            track_html_parts.append(
                f'<div style="position:absolute;left:{left_pct}%;width:{width_pct}%;height:100%;background:{color};border-radius:6px;opacity:0.85;" title="{title}"></div>'
            )
        track_html_parts.append("</div>")
        st.markdown("".join(track_html_parts), unsafe_allow_html=True)

        # Légende
        cols = st.columns(len(segments) + 1)
        for i, (start, end) in enumerate(segments):
            color = SEGMENT_COLORS[i % len(SEGMENT_COLORS)]
            with cols[i]:
                label = f"{i+1}. {format_timestamp(start)} - {format_timestamp(end)}"
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:4px;"><span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:{color};"></span><span style="font-size:0.8em">{label}</span></div>',
                    unsafe_allow_html=True,
                )
        with cols[-1]:
            st.markdown(
                f'<span style="font-size:0.8em;color:#666;">Total : {format_timestamp(total_duration)}</span>',
                unsafe_allow_html=True,
            )


def remove_segment(idx):
    """Supprimer un segment."""
    st.session_state.segments.pop(idx)
    st.rerun()


def process_segments():
    """Lancer le traitement et mettre à jour l'état de la session."""
    if not st.session_state.video_path or not os.path.exists(st.session_state.video_path):
        st.session_state.error = "Tâche d'abord fournir un chemin de fichier vidéo valide."
        st.rerun()
        return

    if not st.session_state.segments:
        st.session_state.error = "Il faut au moins un segment."
        st.rerun()
        return

    st.session_state.processing = True
    st.session_state.error = None
    st.session_state.result = None
    st.rerun()


def run_processing(progress_bar, status_container):
    """Exécuter le traitement ffmpeg avec retour sur la progression."""
    input_file = st.session_state.video_path
    output_file = st.session_state.output_file or f"{st.session_state.video_name}_clipped.mp4"

    with status_container:
        progress_bar.progress(0.2, text="Extraction des segments...")
        try:
            extract_and_concat(input_file, st.session_state.segments, output_file, verbose=False)
            progress_bar.progress(1.0, text="Terminé !")
            st.session_state.result = output_file
            st.session_state.processing = False
            st.rerun()
        except RuntimeError as e:
            st.session_state.error = str(e)
            st.session_state.processing = False
            st.rerun()


def main():
    st.set_page_config(
        page_title="Video Clipper",
        page_icon=":material/analytics:",
        layout="wide",
    )

    init_state()

    st.title("Video Clipper")
    st.caption("Extraire et concaténer des segments vidéo avec ffmpeg")

    # --- Barre latérale : fichier, sortie, traitement ---
    with st.sidebar:
        st.header(":material/video_library: Source")

        # file_path = st.text_input(
        #     "Chemin du fichier vidéo",
        #     placeholder="/chemin/vers/ma_video.mp4",
        #     help="Copiez/Collez ici le chemin complet d'un fichier vidéo local. Aucune limite de taille.",
        # )

        file_path = file_system_selector()

        if file_path and os.path.isfile(file_path):
            st.session_state.video_name = os.path.splitext(os.path.basename(file_path))[0]
            st.session_state.video_path = file_path

            # Réinitialiser la durée pour forcer le rechargement
            if st.session_state.video_duration is not None:
                st.session_state.video_duration = None
        elif file_path:
            st.error(f"Fichier introuvable : {file_path}")

        if st.session_state.video_path and os.path.exists(st.session_state.video_path):
            st.success(f":material/check_circle: {st.session_state.video_name}")
            if st.session_state.video_duration is not None:
                st.caption(f"Durée : {format_timestamp(st.session_state.video_duration)}")

            default_output = f"{st.session_state.video_name}_clipped.mp4"
            st.session_state.output_file = st.text_input(
                "Fichier de sortie",
                value=st.session_state.output_file or default_output,
                key="output_file_input",
            )
        else:
            st.info(":material/info: Sélectionne le chemin d'un fichier vidéo pour commencer")

        st.divider()

        process_disabled = (
            not st.session_state.video_path
            or not os.path.exists(st.session_state.video_path)
            or not st.session_state.segments
            or st.session_state.processing
        )
        process_btn = st.button(
            ":material/rocket_launch: Traiter",
            type="primary",
            disabled=process_disabled,
            use_container_width=True,
        )

        if process_btn and not process_disabled:
            process_segments()

        st.divider()
        st.caption("Video Clipper v1.0")

    # --- Zone principale ---
    if not st.session_state.video_path or not os.path.exists(st.session_state.video_path):
        st.info("Choisis un fichier vidéo dans la barre latérale pour commencer.")
        return

    if st.session_state.video_duration is None:
        with st.spinner("Chargement des informations vidéo..."):
            try:
                st.session_state.video_duration = get_video_duration(st.session_state.video_path)
            except RuntimeError as e:
                st.session_state.error = str(e)
                return

    # Informations vidéo
    with st.container():
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.subheader(":material/video_library: " + st.session_state.video_name)
        with col2:
            st.metric("Durée", format_timestamp(st.session_state.video_duration))
        with col3:
            st.metric("Segments", len(st.session_state.segments))

    st.divider()

    # --- Gestion des segments ---
    st.subheader(":material/playlist_add: Segments")

    with st.form("add_segment_form", border=False):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            new_start = st.text_input(
                "Heure de début",
                placeholder="ex. 00:30 ou 00:01:30",
                help="Format MM:SS ou HH:MM:SS",
            )
        with col2:
            new_end = st.text_input(
                "Heure de fin",
                placeholder="ex. 01:45 ou 00:02:45",
                help="Format MM:SS ou HH:MM:SS",
            )
        with col3:
            add_btn = st.form_submit_button(":material/add_circle: Ajouter", use_container_width=True)

        if add_btn:
            if not new_start or not new_end:
                st.error("Il faut saisir les deux dates (début et fin).")
            else:
                try:
                    start = parse_timestamp(new_start)
                    end = parse_timestamp(new_end)
                    if start < 0 or end < 0:
                        st.error("Les heures ne peuvent pas être négatives.")
                    elif start >= st.session_state.video_duration:
                        st.error(f"L'heure de début dépasse la durée vidéo ({format_timestamp(st.session_state.video_duration)}).")
                    elif end > st.session_state.video_duration:
                        st.error(f"L'heure de fin dépasse la durée vidéo ({format_timestamp(st.session_state.video_duration)}).")
                    elif start >= end:
                        st.error("L'heure de début doit être inférieure à l'heure de fin.")
                    else:
                        st.session_state.segments.append((start, end))
                        st.session_state.segments.sort(key=lambda x: x[0])
                        # Vérifier les chevauchements
                        for i in range(len(st.session_state.segments) - 1):
                            if st.session_state.segments[i][1] > st.session_state.segments[i + 1][0]:
                                st.warning(f"Les segments {i+1} et {i+2} se chevauchent.")
                except ValueError as e:
                    st.error(str(e))

    # --- Liste des segments ---
    if st.session_state.segments:
        render_timeline(st.session_state.video_duration, st.session_state.segments)

        st.markdown("")
        with st.container(border=True):
            st.markdown("**Segments sélectionnés**")
            for idx, (start, end) in enumerate(st.session_state.segments):
                col1, col2, col3 = st.columns([3, 3, 0.5])
                with col1:
                    st.text_input(
                        "Début",
                        value=format_timestamp(start),
                        key=f"seg_start_{idx}",
                        label_visibility="collapsed",
                    )
                with col2:
                    st.text_input(
                        "Fin",
                        value=format_timestamp(end),
                        key=f"seg_end_{idx}",
                        label_visibility="collapsed",
                    )
                with col3:
                    st.button(
                        ":material/delete:",
                        key=f"seg_remove_{idx}",
                        on_click=remove_segment,
                        args=(idx,),
                        use_container_width=True,
                    )

        # --- Aperçu des segments ---
        preview_exp = st.expander(":material/visibility: Aperçu des segments", expanded=False)
        with preview_exp:
            total_selected = sum(end - start for start, end in st.session_state.segments)
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.metric("Nombre de segments", len(st.session_state.segments))
            with col_info2:
                st.metric("Durée totale sélectionnée", format_timestamp(total_selected))

            st.markdown("")
            st.markdown("**Détail par segment :**")
            for idx, (start, end) in enumerate(st.session_state.segments):
                duration = end - start
                color = SEGMENT_COLORS[idx % len(SEGMENT_COLORS)]
                with st.container():
                    col_label, col_bar = st.columns([1, 10])
                    with col_label:
                        st.markdown(
                            f'<div style="display:inline-flex;align-items:center;gap:6px;"><span style="display:inline-block;width:14px;height:14px;border-radius:4px;background:{color};"></span><strong>Segment {idx+1}</strong></div>',
                            unsafe_allow_html=True,
                        )
                    with col_bar:
                        bar_width = max(5, (duration / st.session_state.video_duration) * 100)
                        st.markdown(
                            f'<div style="display:flex;align-items:center;gap:8px;"><div style="flex:1;height:18px;background:#e0e0e0;border-radius:4px;overflow:hidden;"><div style="width:{bar_width}%;height:100%;background:{color};border-radius:4px;"></div></div><span style="font-size:0.85em;white-space:nowrap;">{format_timestamp(start)} → {format_timestamp(end)} ({duration:.1f}s)</span></div>',
                            unsafe_allow_html=True,
                        )

            # Aperçu vidéo par segment
            st.markdown("")
            st.markdown("**Aperçu vidéo :**")
            for idx, (start, end) in enumerate(st.session_state.segments):
                color = SEGMENT_COLORS[idx % len(SEGMENT_COLORS)]
                with st.container():
                    st.markdown(
                        f'<div style="display:inline-flex;align-items:center;gap:6px;"><span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:{color};"></span><strong>Segment {idx+1} : {format_timestamp(start)} → {format_timestamp(end)}</strong></div>',
                        unsafe_allow_html=True,
                    )
                    st.video(
                        st.session_state.video_path,
                        start_time=int(start),
                        end_time=int(end),
                        autoplay=False,
                    )

            # Résumé compact
            st.markdown("")
            with st.container(border=True):
                st.caption("Résumé")
                for idx, (start, end) in enumerate(st.session_state.segments):
                    duration = end - start
                    st.write(f"- Segment {idx+1}: **{format_timestamp(start)}** → **{format_timestamp(end)}** ({duration:.1f} secondes)")
                st.write(f"- **Total : {len(st.session_state.segments)} segment(s), {format_timestamp(total_selected)}**")

    else:
        st.info(":material/add_circle: Ajoute ton premier segment avec le formulaire ci-dessus.")

    # --- Statut du traitement ---
    if st.session_state.processing:
        progress_bar = st.progress(0, text="Traitement en cours...")
        status_container = st.empty()
        run_processing(progress_bar, status_container)

    if st.session_state.error:
        st.error(f":material/error: {st.session_state.error}")

    if st.session_state.result:
        st.success(f":material/check_circle: Sortie enregistrée dans `{st.session_state.result}`")
        if os.path.exists(st.session_state.result):
            file_size = os.path.getsize(st.session_state.result)
            if file_size > 1024 * 1024:
                st.caption(f"Taille du fichier : {file_size / (1024*1024):.1f} Mo")
            else:
                st.caption(f"Taille du fichier : {file_size / 1024:.1f} Ko")
            with open(st.session_state.result, "rb") as f:
                st.download_button(
                    label=":material/download: Télécharger la sortie",
                    data=f,
                    file_name=os.path.basename(st.session_state.result),
                    mime="video/mp4",
                    use_container_width=True,
                )


if __name__ == "__main__":
    main()
