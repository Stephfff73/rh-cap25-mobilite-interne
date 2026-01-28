import streamlit as st
import pandas as pd
from datetime import datetime
import time
from google.oauth2 import service_account
import gspread
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="CAP25 - Pilotage Mobilité", 
    layout="wide", 
    page_icon="🏢",
    initial_sidebar_state="expanded"
)

# --- CONFIGURATION GOOGLE SHEETS ---
@st.cache_resource
def get_gsheet_connection():
    try:
        # 1. On récupère les secrets sous forme de dictionnaire Python pur
        creds_dict = st.secrets["gcp_service_account"].to_dict()
        
        # 2. On s'assure que les \n sont bien gérés si la clé est sur une seule ligne
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Erreur de configuration des credentials : {str(e)}")
        return None

@st.cache_data(ttl=60)
def load_data_from_gsheet(_client, sheet_url):
    """
    Charge les données depuis Google Sheets.
    Onglets : CAP 2025 (collaborateurs) et Postes (référentiel)
    """
    try:
        spreadsheet = _client.open_by_url(sheet_url)
    except Exception as e:
        st.error(f"Impossible d'ouvrir le Google Sheet : {str(e)}")
        return pd.DataFrame(), pd.DataFrame()
    
    # Charger l'onglet "CAP 2025" (collaborateurs)
    try:
        cap_sheet = spreadsheet.worksheet("CAP 2025")
        # Les données commencent à la ligne 3 (ligne 1 = titre, ligne 2 = headers)
        all_values = cap_sheet.get_all_values()
        headers = all_values[1]  # Ligne 2 = headers
        data = all_values[2:]     # À partir de la ligne 3
        
        collaborateurs_df = pd.DataFrame(data, columns=headers)
        
        # Nettoyer les colonnes vides potentielles
        collaborateurs_df = collaborateurs_df.loc[:, ~collaborateurs_df.columns.str.contains('^Unnamed')]
        
    except gspread.WorksheetNotFound:
        st.error("⚠️ L'onglet 'CAP 2025' n'a pas été trouvé.")
        collaborateurs_df = pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur lors du chargement de 'CAP 2025' : {str(e)}")
        collaborateurs_df = pd.DataFrame()
    
    # Charger l'onglet "Postes" (référentiel)
    try:
        postes_sheet = spreadsheet.worksheet("Postes")
        postes_data = postes_sheet.get_all_records()
        postes_df = pd.DataFrame(postes_data)
        
    except gspread.WorksheetNotFound:
        st.error("⚠️ L'onglet 'Postes' n'a pas été trouvé.")
        postes_df = pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur lors du chargement de 'Postes' : {str(e)}")
        postes_df = pd.DataFrame()
    
    return collaborateurs_df, postes_df

def create_entretien_sheet_if_not_exists(_client, sheet_url):
    """
    Crée l'onglet "Entretien RH" s'il n'existe pas déjà.
    """
    try:
        spreadsheet = _client.open_by_url(sheet_url)
        
        # Vérifier si l'onglet existe
        try:
            spreadsheet.worksheet("Entretien RH")
            return True  # L'onglet existe déjà
        except gspread.WorksheetNotFound:
            # Créer l'onglet avec les headers
            worksheet = spreadsheet.add_worksheet(title="Entretien RH", rows="1000", cols="50")
            
            # Headers de l'onglet Entretien RH
            headers = [
                "Matricule", "Nom", "Prénom", "Date_Entretien", "Referente_RH",
                # Vœu 1
                "Voeu_1", "V1_Motivations", "V1_Vision_Enjeux", "V1_Premieres_Actions",
                "V1_Competence_1_Nom", "V1_Competence_1_Niveau", "V1_Competence_1_Justification",
                "V1_Competence_2_Nom", "V1_Competence_2_Niveau", "V1_Competence_2_Justification",
                "V1_Competence_3_Nom", "V1_Competence_3_Niveau", "V1_Competence_3_Justification",
                "V1_Experience_Niveau", "V1_Experience_Justification",
                "V1_Besoin_Accompagnement", "V1_Type_Accompagnement",
                # Vœu 2
                "Voeu_2", "V2_Motivations", "V2_Vision_Enjeux", "V2_Premieres_Actions",
                "V2_Competence_1_Nom", "V2_Competence_1_Niveau", "V2_Competence_1_Justification",
                "V2_Competence_2_Nom", "V2_Competence_2_Niveau", "V2_Competence_2_Justification",
                "V2_Competence_3_Nom", "V2_Competence_3_Niveau", "V2_Competence_3_Justification",
                "V2_Experience_Niveau", "V2_Experience_Justification",
                "V2_Besoin_Accompagnement", "V2_Type_Accompagnement",
                # Vœu 3
                "Voeu_3", "V3_Motivations", "V3_Vision_Enjeux", "V3_Premieres_Actions",
                "V3_Competence_1_Nom", "V3_Competence_1_Niveau", "V3_Competence_1_Justification",
                "V3_Competence_2_Nom", "V3_Competence_2_Niveau", "V3_Competence_2_Justification",
                "V3_Competence_3_Nom", "V3_Competence_3_Niveau", "V3_Competence_3_Justification",
                "V3_Experience_Niveau", "V3_Experience_Justification",
                "V3_Besoin_Accompagnement", "V3_Type_Accompagnement",
                # Avis RH
                "Attentes_Manager", "Avis_RH_Synthese"
            ]
            
            worksheet.update('A1:AX1', [headers])
            return True
            
    except Exception as e:
        st.error(f"Erreur lors de la création de l'onglet 'Entretien RH' : {str(e)}")
        return False

def save_entretien_to_gsheet(_client, sheet_url, entretien_data):
    """
    Sauvegarde un entretien RH dans l'onglet "Entretien RH".
    """
    try:
        spreadsheet = _client.open_by_url(sheet_url)
        worksheet = spreadsheet.worksheet("Entretien RH")
        
        # Chercher si l'entretien existe déjà (basé sur Matricule)
        all_records = worksheet.get_all_records()
        existing_row = None
        
        for idx, record in enumerate(all_records):
            if str(record.get("Matricule", "")) == str(entretien_data["Matricule"]):
                existing_row = idx + 2  # +2 car ligne 1 = header, index commence à 0
                break
        
        # Préparer les données dans l'ordre des colonnes
        row_data = [
            entretien_data.get("Matricule", ""),
            entretien_data.get("Nom", ""),
            entretien_data.get("Prénom", ""),
            entretien_data.get("Date_Entretien", ""),
            entretien_data.get("Referente_RH", ""),
            # Vœu 1
            entretien_data.get("Voeu_1", ""),
            entretien_data.get("V1_Motivations", ""),
            entretien_data.get("V1_Vision_Enjeux", ""),
            entretien_data.get("V1_Premieres_Actions", ""),
            entretien_data.get("V1_Competence_1_Nom", ""),
            entretien_data.get("V1_Competence_1_Niveau", ""),
            entretien_data.get("V1_Competence_1_Justification", ""),
            entretien_data.get("V1_Competence_2_Nom", ""),
            entretien_data.get("V1_Competence_2_Niveau", ""),
            entretien_data.get("V1_Competence_2_Justification", ""),
            entretien_data.get("V1_Competence_3_Nom", ""),
            entretien_data.get("V1_Competence_3_Niveau", ""),
            entretien_data.get("V1_Competence_3_Justification", ""),
            entretien_data.get("V1_Experience_Niveau", ""),
            entretien_data.get("V1_Experience_Justification", ""),
            entretien_data.get("V1_Besoin_Accompagnement", ""),
            entretien_data.get("V1_Type_Accompagnement", ""),
            # Vœu 2
            entretien_data.get("Voeu_2", ""),
            entretien_data.get("V2_Motivations", ""),
            entretien_data.get("V2_Vision_Enjeux", ""),
            entretien_data.get("V2_Premieres_Actions", ""),
            entretien_data.get("V2_Competence_1_Nom", ""),
            entretien_data.get("V2_Competence_1_Niveau", ""),
            entretien_data.get("V2_Competence_1_Justification", ""),
            entretien_data.get("V2_Competence_2_Nom", ""),
            entretien_data.get("V2_Competence_2_Niveau", ""),
            entretien_data.get("V2_Competence_2_Justification", ""),
            entretien_data.get("V2_Competence_3_Nom", ""),
            entretien_data.get("V2_Competence_3_Niveau", ""),
            entretien_data.get("V2_Competence_3_Justification", ""),
            entretien_data.get("V2_Experience_Niveau", ""),
            entretien_data.get("V2_Experience_Justification", ""),
            entretien_data.get("V2_Besoin_Accompagnement", ""),
            entretien_data.get("V2_Type_Accompagnement", ""),
            # Vœu 3
            entretien_data.get("Voeu_3", ""),
            entretien_data.get("V3_Motivations", ""),
            entretien_data.get("V3_Vision_Enjeux", ""),
            entretien_data.get("V3_Premieres_Actions", ""),
            entretien_data.get("V3_Competence_1_Nom", ""),
            entretien_data.get("V3_Competence_1_Niveau", ""),
            entretien_data.get("V3_Competence_1_Justification", ""),
            entretien_data.get("V3_Competence_2_Nom", ""),
            entretien_data.get("V3_Competence_2_Niveau", ""),
            entretien_data.get("V3_Competence_2_Justification", ""),
            entretien_data.get("V3_Competence_3_Nom", ""),
            entretien_data.get("V3_Competence_3_Niveau", ""),
            entretien_data.get("V3_Competence_3_Justification", ""),
            entretien_data.get("V3_Experience_Niveau", ""),
            entretien_data.get("V3_Experience_Justification", ""),
            entretien_data.get("V3_Besoin_Accompagnement", ""),
            entretien_data.get("V3_Type_Accompagnement", ""),
            # Avis RH
            entretien_data.get("Attentes_Manager", ""),
            entretien_data.get("Avis_RH_Synthese", "")
        ]
        
        if existing_row:
            # Mettre à jour la ligne existante
            worksheet.update(f'A{existing_row}:AX{existing_row}', [row_data])
        else:
            # Ajouter une nouvelle ligne
            worksheet.append_row(row_data)
        
        return True
        
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde : {str(e)}")
        return False

# --- URL DU GOOGLE SHEET ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1BXez24VFNhb470PrCjwNIFx6GdJFqLnVh8nFf3gGGvw/edit?usp=sharing"

# --- INITIALISATION ---
try:
    gsheet_client = get_gsheet_connection()
    if gsheet_client:
        st.sidebar.success("✅ Connexion Google Sheets établie")
        # Créer l'onglet Entretien RH si nécessaire
        create_entretien_sheet_if_not_exists(gsheet_client, SHEET_URL)
    else:
        st.sidebar.error("❌ Erreur de connexion")
        st.stop()
except Exception as e:
    st.sidebar.error(f"❌ Erreur : {str(e)}")
    st.stop()

# --- CHARGEMENT DES DONNÉES ---
with st.spinner("Chargement des données..."):
    collaborateurs_df, postes_df = load_data_from_gsheet(gsheet_client, SHEET_URL)

if collaborateurs_df.empty or postes_df.empty:
    st.error("Impossible de charger les données. Vérifiez la structure du Google Sheet.")
    st.stop()

# --- SIDEBAR : NAVIGATION ---
st.sidebar.title("🏢 CAP25 - Mobilité Interne")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigation",
    ["📊 Tableau de Bord", "👥 Liste Collaborateurs", "📝 Entretien RH", "🎯 Analyse par Poste", "🌳 Référentiel Postes"],
    label_visibility="collapsed"
)

# Bouton de rafraîchissement
st.sidebar.divider()
if st.sidebar.button("🔄 Rafraîchir les données", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()
st.sidebar.caption(f"Dernière mise à jour : {datetime.now().strftime('%H:%M:%S')}")

# ========================================
# PAGE 1 : TABLEAU DE BORD
# ========================================

if page == "📊 Tableau de Bord":
    st.title("📊 Tableau de Bord - Vue d'ensemble")
    
    # Métriques principales
    col1, col2, col3, col4 = st.columns(4)
    
    nb_collaborateurs = len(collaborateurs_df)
    nb_postes_ouverts = len(postes_df[postes_df["Mobilité interne"].str.lower() == "oui"])
    nb_entretiens_planifies = len(collaborateurs_df[collaborateurs_df["Rencontre RH / Positionnement"].str.lower() == "oui"])
    nb_priorite_1 = len(collaborateurs_df[collaborateurs_df["Priorité"] == "Priorité 1"])
    
    col1.metric("👥 Collaborateurs", nb_collaborateurs)
    col2.metric("📍 Postes ouverts", nb_postes_ouverts)
    col3.metric("📅 Entretiens planifiés", nb_entretiens_planifies)
    col4.metric("⭐ Priorité 1", nb_priorite_1)
    
    st.divider()
    
    # Graphiques
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("🔥 Top 10 des postes les plus demandés")
        
        # Concaténer tous les vœux
        all_voeux = pd.concat([
            collaborateurs_df["Vœux 1"],
            collaborateurs_df["Vœux 2"],
            collaborateurs_df["Voeux 3"]
        ])
        all_voeux = all_voeux[all_voeux.notna() & (all_voeux != "") & (all_voeux != "Positionnement manquant")]
        
        if len(all_voeux) > 0:
            top_postes = all_voeux.value_counts().head(10)
            st.bar_chart(top_postes, color="#FF4B4B")
        else:
            st.info("Aucun vœu enregistré pour le moment")
    
    with col_chart2:
        st.subheader("🏢 Répartition par Direction")
        
        if "Direction libellé" in postes_df.columns:
            dir_count = postes_df["Direction"].value_counts()
            st.bar_chart(dir_count, color="#2E86C1")
        else:
            st.info("Données de direction non disponibles")

# ========================================
# PAGE 2 : LISTE COLLABORATEURS
# ========================================

elif page == "👥 Liste Collaborateurs":
    st.title("👥 Liste des Collaborateurs")
    
    # Filtres
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        filtre_priorite = st.multiselect(
            "Filtrer par priorité",
            options=collaborateurs_df["Priorité"].unique(),
            default=[]
        )
    
    with col_f2:
        filtre_rrh = st.multiselect(
            "Filtrer par RRH",
            options=collaborateurs_df["Périmètre RRH"].unique(),
            default=[]
        )
    
    with col_f3:
        filtre_entretien = st.selectbox(
            "Entretien RH",
            ["Tous", "Oui", "Non"]
        )
    
    # Appliquer les filtres
    df_filtered = collaborateurs_df.copy()
    
    if filtre_priorite:
        df_filtered = df_filtered[df_filtered["Priorité"].isin(filtre_priorite)]
    
    if filtre_rrh:
        df_filtered = df_filtered[df_filtered["Périmètre RRH"].isin(filtre_rrh)]
    
    if filtre_entretien != "Tous":
        df_filtered = df_filtered[df_filtered["Rencontre RH / Positionnement"].str.lower() == filtre_entretien.lower()]
    
    # Affichage
    st.dataframe(
        df_filtered[[
            "Matricule", "NOM", "Prénom", "Titre ou Fonction", 
            "Vœux 1", "Vœux 2", "Voeux 3", 
            "Date de rdv", "Priorité", "Référente RH"
        ]],
        use_container_width=True,
        hide_index=True
    )

# ========================================
# PAGE 3 : ENTRETIEN RH (NOUVEAU)
# ========================================

elif page == "📝 Entretien RH":
    st.title("📝 Conduite d'Entretien RH - CAP 2025")
    
    st.info("""
    Ce formulaire permet de formaliser le compte rendu de l'entretien avec le collaborateur.
    Les informations seront sauvegardées dans l'onglet "Entretien RH" du Google Sheet.
    """)
    
    # Sélection du collaborateur
    st.subheader("1️⃣ Sélection du collaborateur")
    
    collaborateur_names = (collaborateurs_df["NOM"] + " " + collaborateurs_df["Prénom"]).tolist()
    selected_collab = st.selectbox(
        "Rechercher un collaborateur",
        options=["-- Sélectionner --"] + collaborateur_names
    )
    
    if selected_collab != "-- Sélectionner --":
        # Récupérer les infos du collaborateur
        idx = collaborateur_names.index(selected_collab)
        collab = collaborateurs_df.iloc[idx]
        
        # Afficher les infos du collaborateur
        with st.container(border=True):
            col_info1, col_info2, col_info3 = st.columns(3)
            
            with col_info1:
                st.markdown(f"**Matricule** : {collab['Matricule']}")
                st.markdown(f"**Nom** : {collab['NOM']} {collab['Prénom']}")
                st.markdown(f"**Mail** : {collab['Mail']}")
            
            with col_info2:
                st.markdown(f"**Poste actuel** : {collab['Titre ou Fonction']}")
                st.markdown(f"**Direction** : {collab['Direction libellé']}")
                st.markdown(f"**Ancienneté** : {collab["Date d\\'ancienneté"]}")
            
            with col_info3:
                st.markdown(f"**RRH** : {collab['Référente RH']}")
                st.markdown(f"**Date RDV** : {collab['Date de rdv']}")
                st.markdown(f"**Priorité** : {collab['Priorité']}")
        
        st.divider()
        
        # Initialiser l'entretien data
        entretien_data = {
            "Matricule": collab['Matricule'],
            "Nom": collab['NOM'],
            "Prénom": collab['Prénom'],
            "Date_Entretien": datetime.now().strftime("%d/%m/%Y"),
            "Referente_RH": collab['Référente RH']
        }
        
        # Tabs pour les 3 vœux
        tab_voeu1, tab_voeu2, tab_voeu3, tab_avis = st.tabs([
            f"🎯 Vœu 1: {collab['Vœux 1']}", 
            f"🎯 Vœu 2: {collab['Vœux 2'] if collab['Vœux 2'] else 'Non renseigné'}", 
            f"🎯 Vœu 3: {collab['Voeux 3'] if collab['Voeux 3'] else 'Non renseigné'}",
            "💬 Avis RH"
        ])
        
        # ========== VŒEU 1 ==========
        with tab_voeu1:
            if collab['Vœux 1'] and collab['Vœux 1'] != "Positionnement manquant":
                st.subheader(f"Évaluation du Vœu 1 : {collab['Vœux 1']}")
                
                entretien_data["Voeu_1"] = collab['Vœux 1']
                
                st.markdown("#### 📋 Questions générales")
                entretien_data["V1_Motivations"] = st.text_area(
                    "Quelles sont vos motivations pour ce poste ?",
                    key="v1_motiv",
                    height=100
                )
                
                entretien_data["V1_Vision_Enjeux"] = st.text_area(
                    "Quelle est votre vision des enjeux du poste ?",
                    key="v1_vision",
                    height=100
                )
                
                entretien_data["V1_Premieres_Actions"] = st.text_area(
                    "Quelles seraient vos premières actions à la prise de poste ?",
                    key="v1_actions",
                    height=100
                )
                
                st.divider()
                st.markdown("#### 🎯 Évaluation des compétences")
                
                # Compétence 1
                col_comp1_1, col_comp1_2 = st.columns([1, 2])
                with col_comp1_1:
                    entretien_data["V1_Competence_1_Nom"] = st.text_input("Compétence 1", key="v1_c1_nom")
                    entretien_data["V1_Competence_1_Niveau"] = st.selectbox(
                        "Niveau",
                        ["Débutant", "Confirmé", "Expert"],
                        key="v1_c1_niv"
                    )
                with col_comp1_2:
                    entretien_data["V1_Competence_1_Justification"] = st.text_area(
                        "Justification et exemples concrets",
                        key="v1_c1_just",
                        height=100
                    )
                
                st.divider()
                
                # Compétence 2
                col_comp2_1, col_comp2_2 = st.columns([1, 2])
                with col_comp2_1:
                    entretien_data["V1_Competence_2_Nom"] = st.text_input("Compétence 2", key="v1_c2_nom")
                    entretien_data["V1_Competence_2_Niveau"] = st.selectbox(
                        "Niveau",
                        ["Débutant", "Confirmé", "Expert"],
                        key="v1_c2_niv"
                    )
                with col_comp2_2:
                    entretien_data["V1_Competence_2_Justification"] = st.text_area(
                        "Justification et exemples concrets",
                        key="v1_c2_just",
                        height=100
                    )
                
                st.divider()
                
                # Compétence 3
                col_comp3_1, col_comp3_2 = st.columns([1, 2])
                with col_comp3_1:
                    entretien_data["V1_Competence_3_Nom"] = st.text_input("Compétence 3", key="v1_c3_nom")
                    entretien_data["V1_Competence_3_Niveau"] = st.selectbox(
                        "Niveau",
                        ["Débutant", "Confirmé", "Expert"],
                        key="v1_c3_niv"
                    )
                with col_comp3_2:
                    entretien_data["V1_Competence_3_Justification"] = st.text_area(
                        "Justification et exemples concrets",
                        key="v1_c3_just",
                        height=100
                    )
                
                st.divider()
                st.markdown("#### 📊 Expérience")
                
                col_exp1, col_exp2 = st.columns([1, 2])
                with col_exp1:
                    entretien_data["V1_Experience_Niveau"] = st.selectbox(
                        "Niveau d'expérience dans des contextes comparables",
                        ["Débutant (0-3 ans)", "Confirmé (3-7 ans)", "Expert (8+ ans)"],
                        key="v1_exp_niv"
                    )
                with col_exp2:
                    entretien_data["V1_Experience_Justification"] = st.text_area(
                        "Quelle expérience justifie ce niveau ?",
                        key="v1_exp_just",
                        height=100
                    )
                
                st.divider()
                st.markdown("#### 🎓 Accompagnement et Formation")
                
                col_form1, col_form2 = st.columns([1, 2])
                with col_form1:
                    entretien_data["V1_Besoin_Accompagnement"] = st.radio(
                        "Besoin d'accompagnement / formation ?",
                        ["Non", "Oui"],
                        key="v1_form_besoin"
                    )
                with col_form2:
                    if entretien_data["V1_Besoin_Accompagnement"] == "Oui":
                        entretien_data["V1_Type_Accompagnement"] = st.text_area(
                            "Quels types de soutien ou d'accompagnement ?",
                            key="v1_form_type",
                            height=100
                        )
                    else:
                        entretien_data["V1_Type_Accompagnement"] = ""
            
            else:
                st.warning("Aucun vœu 1 renseigné pour ce collaborateur")
        
        # ========== VŒU 2 ==========
        with tab_voeu2:
            if collab['Vœux 2'] and collab['Vœux 2'] != "Positionnement manquant":
                st.subheader(f"Évaluation du Vœu 2 : {collab['Vœux 2']}")
                
                entretien_data["Voeu_2"] = collab['Vœux 2']
                
                st.markdown("#### 📋 Questions générales")
                entretien_data["V2_Motivations"] = st.text_area(
                    "Quelles sont vos motivations pour ce poste ?",
                    key="v2_motiv",
                    height=100
                )
                
                entretien_data["V2_Vision_Enjeux"] = st.text_area(
                    "Quelle est votre vision des enjeux du poste ?",
                    key="v2_vision",
                    height=100
                )
                
                entretien_data["V2_Premieres_Actions"] = st.text_area(
                    "Quelles seraient vos premières actions à la prise de poste ?",
                    key="v2_actions",
                    height=100
                )
                
                st.divider()
                st.markdown("#### 🎯 Évaluation des compétences")
                
                # Compétence 1
                col_comp1_1, col_comp1_2 = st.columns([1, 2])
                with col_comp1_1:
                    entretien_data["V2_Competence_1_Nom"] = st.text_input("Compétence 1", key="v2_c1_nom")
                    entretien_data["V2_Competence_1_Niveau"] = st.selectbox(
                        "Niveau",
                        ["Débutant", "Confirmé", "Expert"],
                        key="v2_c1_niv"
                    )
                with col_comp1_2:
                    entretien_data["V2_Competence_1_Justification"] = st.text_area(
                        "Justification et exemples concrets",
                        key="v2_c1_just",
                        height=100
                    )
                
                st.divider()
                
                # Compétence 2
                col_comp2_1, col_comp2_2 = st.columns([1, 2])
                with col_comp2_1:
                    entretien_data["V2_Competence_2_Nom"] = st.text_input("Compétence 2", key="v2_c2_nom")
                    entretien_data["V2_Competence_2_Niveau"] = st.selectbox(
                        "Niveau",
                        ["Débutant", "Confirmé", "Expert"],
                        key="v2_c2_niv"
                    )
                with col_comp2_2:
                    entretien_data["V2_Competence_2_Justification"] = st.text_area(
                        "Justification et exemples concrets",
                        key="v2_c2_just",
                        height=100
                    )
                
                st.divider()
                
                # Compétence 3
                col_comp3_1, col_comp3_2 = st.columns([1, 2])
                with col_comp3_1:
                    entretien_data["V2_Competence_3_Nom"] = st.text_input("Compétence 3", key="v2_c3_nom")
                    entretien_data["V2_Competence_3_Niveau"] = st.selectbox(
                        "Niveau",
                        ["Débutant", "Confirmé", "Expert"],
                        key="v2_c3_niv"
                    )
                with col_comp3_2:
                    entretien_data["V2_Competence_3_Justification"] = st.text_area(
                        "Justification et exemples concrets",
                        key="v2_c3_just",
                        height=100
                    )
                
                st.divider()
                st.markdown("#### 📊 Expérience")
                
                col_exp1, col_exp2 = st.columns([1, 2])
                with col_exp1:
                    entretien_data["V2_Experience_Niveau"] = st.selectbox(
                        "Niveau d'expérience dans des contextes comparables",
                        ["Débutant (0-3 ans)", "Confirmé (3-7 ans)", "Expert (8+ ans)"],
                        key="v2_exp_niv"
                    )
                with col_exp2:
                    entretien_data["V2_Experience_Justification"] = st.text_area(
                        "Quelle expérience justifie ce niveau ?",
                        key="v2_exp_just",
                        height=100
                    )
                
                st.divider()
                st.markdown("#### 🎓 Accompagnement et Formation")
                
                col_form1, col_form2 = st.columns([1, 2])
                with col_form1:
                    entretien_data["V2_Besoin_Accompagnement"] = st.radio(
                        "Besoin d'accompagnement / formation ?",
                        ["Non", "Oui"],
                        key="v2_form_besoin"
                    )
                with col_form2:
                    if entretien_data["V2_Besoin_Accompagnement"] == "Oui":
                        entretien_data["V2_Type_Accompagnement"] = st.text_area(
                            "Quels types de soutien ou d'accompagnement ?",
                            key="v2_form_type",
                            height=100
                        )
                    else:
                        entretien_data["V2_Type_Accompagnement"] = ""
            
            else:
                st.warning("Aucun vœu 2 renseigné pour ce collaborateur")
        
        # ========== VŒEU 3 ==========
        with tab_voeu3:
            if collab['Voeux 3'] and collab['Voeux 3'] != "Positionnement manquant":
                st.subheader(f"Évaluation du Vœu 3 : {collab['Voeux 3']}")
                
                entretien_data["Voeu_3"] = collab['Voeux 3']
                
                st.markdown("#### 📋 Questions générales")
                entretien_data["V3_Motivations"] = st.text_area(
                    "Quelles sont vos motivations pour ce poste ?",
                    key="v3_motiv",
                    height=100
                )
                
                entretien_data["V3_Vision_Enjeux"] = st.text_area(
                    "Quelle est votre vision des enjeux du poste ?",
                    key="v3_vision",
                    height=100
                )
                
                entretien_data["V3_Premieres_Actions"] = st.text_area(
                    "Quelles seraient vos premières actions à la prise de poste ?",
                    key="v3_actions",
                    height=100
                )
                
                st.divider()
                st.markdown("#### 🎯 Évaluation des compétences")
                
                # Compétence 1
                col_comp1_1, col_comp1_2 = st.columns([1, 2])
                with col_comp1_1:
                    entretien_data["V3_Competence_1_Nom"] = st.text_input("Compétence 1", key="v3_c1_nom")
                    entretien_data["V3_Competence_1_Niveau"] = st.selectbox(
                        "Niveau",
                        ["Débutant", "Confirmé", "Expert"],
                        key="v3_c1_niv"
                    )
                with col_comp1_2:
                    entretien_data["V3_Competence_1_Justification"] = st.text_area(
                        "Justification et exemples concrets",
                        key="v3_c1_just",
                        height=100
                    )
                
                st.divider()
                
                # Compétence 2
                col_comp2_1, col_comp2_2 = st.columns([1, 2])
                with col_comp2_1:
                    entretien_data["V3_Competence_2_Nom"] = st.text_input("Compétence 2", key="v3_c2_nom")
                    entretien_data["V3_Competence_2_Niveau"] = st.selectbox(
                        "Niveau",
                        ["Débutant", "Confirmé", "Expert"],
                        key="v3_c2_niv"
                    )
                with col_comp2_2:
                    entretien_data["V3_Competence_2_Justification"] = st.text_area(
                        "Justification et exemples concrets",
                        key="v3_c2_just",
                        height=100
                    )
                
                st.divider()
                
                # Compétence 3
                col_comp3_1, col_comp3_2 = st.columns([1, 2])
                with col_comp3_1:
                    entretien_data["V3_Competence_3_Nom"] = st.text_input("Compétence 3", key="v3_c3_nom")
                    entretien_data["V3_Competence_3_Niveau"] = st.selectbox(
                        "Niveau",
                        ["Débutant", "Confirmé", "Expert"],
                        key="v3_c3_niv"
                    )
                with col_comp3_2:
                    entretien_data["V3_Competence_3_Justification"] = st.text_area(
                        "Justification et exemples concrets",
                        key="v3_c3_just",
                        height=100
                    )
                
                st.divider()
                st.markdown("#### 📊 Expérience")
                
                col_exp1, col_exp2 = st.columns([1, 2])
                with col_exp1:
                    entretien_data["V3_Experience_Niveau"] = st.selectbox(
                        "Niveau d'expérience dans des contextes comparables",
                        ["Débutant (0-3 ans)", "Confirmé (3-7 ans)", "Expert (8+ ans)"],
                        key="v3_exp_niv"
                    )
                with col_exp2:
                    entretien_data["V3_Experience_Justification"] = st.text_area(
                        "Quelle expérience justifie ce niveau ?",
                        key="v3_exp_just",
                        height=100
                    )
                
                st.divider()
                st.markdown("#### 🎓 Accompagnement et Formation")
                
                col_form1, col_form2 = st.columns([1, 2])
                with col_form1:
                    entretien_data["V3_Besoin_Accompagnement"] = st.radio(
                        "Besoin d'accompagnement / formation ?",
                        ["Non", "Oui"],
                        key="v3_form_besoin"
                    )
                with col_form2:
                    if entretien_data["V3_Besoin_Accompagnement"] == "Oui":
                        entretien_data["V3_Type_Accompagnement"] = st.text_area(
                            "Quels types de soutien ou d'accompagnement ?",
                            key="v3_form_type",
                            height=100
                        )
                    else:
                        entretien_data["V3_Type_Accompagnement"] = ""
            
            else:
                st.warning("Aucun vœu 3 renseigné pour ce collaborateur")
        
        # ========== AVIS RH ==========
        with tab_avis:
            st.subheader("💬 Avis RH Final")
            
            entretien_data["Attentes_Manager"] = st.text_area(
                "Attentes vis-à-vis du futur manager & dans quels cas le solliciter ?",
                key="attentes_manager",
                height=150
            )
            
            entretien_data["Avis_RH_Synthese"] = st.text_area(
                "Avis RH - Synthèse globale de l'entretien",
                key="avis_synthese",
                height=200
            )
        
        # Bouton de sauvegarde
        st.divider()
        
        col_save1, col_save2, col_save3 = st.columns([1, 1, 1])
        
        with col_save2:
            if st.button("💾 Enregistrer l'entretien", type="primary", use_container_width=True):
                with st.spinner("Sauvegarde en cours..."):
                    success = save_entretien_to_gsheet(gsheet_client, SHEET_URL, entretien_data)
                    
                    if success:
                        st.success("✅ Entretien enregistré avec succès dans Google Sheets !")
                        time.sleep(2)
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("❌ Erreur lors de l'enregistrement")

# ========================================
# PAGE 4 : ANALYSE PAR POSTE
# ========================================

elif page == "🎯 Analyse par Poste":
    st.title("🎯 Analyse des Viviers par Poste")
    
    # Liste des postes ouverts à la mobilité
    postes_ouverts = postes_df[postes_df["Mobilité interne"].str.lower() == "oui"]["Poste"].tolist()
    
    # Analyse par poste
    job_analysis = []
    
    for poste in postes_ouverts:
        candidats = []
        
        for _, collab in collaborateurs_df.iterrows():
            if collab["Vœux 1"] == poste:
                candidats.append(f"{collab['NOM']} {collab['Prénom']} (V1)")
            elif collab["Vœux 2"] == poste:
                candidats.append(f"{collab['NOM']} {collab['Prénom']} (V2)")
            elif collab["Voeux 3"] == poste:
                candidats.append(f"{collab['NOM']} {collab['Prénom']} (V3)")
        
        job_analysis.append({
            "Poste": poste,
            "Nb_Candidats": len(candidats),
            "Candidats": candidats,
            "Statut": "⚠️ Aucun candidat" if len(candidats) == 0 else "✅ Vivier actif"
        })
    
    df_analysis = pd.DataFrame(job_analysis)
    
    # Filtre
    show_zero = st.checkbox("⚠️ Afficher uniquement les postes sans candidat")
    
    if show_zero:
        df_analysis = df_analysis[df_analysis["Nb_Candidats"] == 0]
    
    # Affichage
    st.dataframe(
        df_analysis,
        column_config={
            "Nb_Candidats": st.column_config.ProgressColumn(
                "Candidats",
                min_value=0,
                max_value=max(df_analysis["Nb_Candidats"].max(), 1),
                format="%d"
            ),
            "Candidats": st.column_config.ListColumn("Détail"),
        },
        use_container_width=True,
        hide_index=True
    )

# ========================================
# PAGE 5 : RÉFÉRENTIEL POSTES
# ========================================

elif page == "🌳 Référentiel Postes":
    st.title("🌳 Référentiel des Postes")
    
    # Filtres
    col_f1, col_f2 = st.columns(2)
    
    with col_f1:
        search = st.text_input("🔍 Rechercher un poste")
    
    with col_f2:
        filtre_mobilite = st.selectbox(
            "Filtre mobilité",
            ["Tous", "Oui", "Non"]
        )
    
    # Appliquer filtres
    df_postes = postes_df.copy()
    
    if search:
        df_postes = df_postes[df_postes["Poste"].str.contains(search, case=False, na=False)]
    
    if filtre_mobilite != "Tous":
        df_postes = df_postes[df_postes["Mobilité interne"].str.lower() == filtre_mobilite.lower()]
    
    # Affichage
    st.dataframe(
        df_postes,
        use_container_width=True,
        hide_index=True
    )

# --- FOOTER ---
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.9em;'>
    <p>CAP25 - Pilotage de la Mobilité Interne | Synchronisé avec Google Sheets</p>
</div>
""", unsafe_allow_html=True)




