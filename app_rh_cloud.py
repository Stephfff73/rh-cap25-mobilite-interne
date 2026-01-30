import streamlit as st
import pandas as pd
from datetime import datetime, date
import time
from google.oauth2 import service_account
import gspread
import pytz
import json

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="CAP25 - Pilotage Mobilité", 
    layout="wide", 
    page_icon="🏢",
    initial_sidebar_state="expanded"
)



# --- INITIALISATION DE SESSION STATE ---
def init_session_state():
    """Initialise toutes les variables de session nécessaires"""
    if 'entretien_data' not in st.session_state:
        st.session_state.entretien_data = {}
    
    if 'current_matricule' not in st.session_state:
        st.session_state.current_matricule = None
    
    if 'selected_collaborateur' not in st.session_state:
        st.session_state.selected_collaborateur = None
    
    if 'navigate_to_entretien' not in st.session_state:
        st.session_state.navigate_to_entretien = False
    
    if 'auto_save_enabled' not in st.session_state:
        st.session_state.auto_save_enabled = True
    
    if 'last_save_time' not in st.session_state:
        st.session_state.last_save_time = None
    
    if 'show_fiche_detail' not in st.session_state:
        st.session_state.show_fiche_detail = False
    
    if 'fiche_candidat' not in st.session_state:
        st.session_state.fiche_candidat = None


# --- CONFIGURATION GOOGLE SHEETS ---
@st.cache_resource
def get_gsheet_connection():
    try:
        creds_info = st.secrets["gcp_service_account"].to_dict()
        
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
            
        credentials = service_account.Credentials.from_service_account_info(
            creds_info,
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

@st.cache_data(ttl=30)  # Cache de 30 secondes pour plus de réactivité
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
        all_values = cap_sheet.get_all_values()
        headers = all_values[1]
        data = all_values[2:]
        
        collaborateurs_df = pd.DataFrame(data, columns=headers)
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

def load_entretien_from_gsheet(_client, sheet_url, matricule):
    """
    Charge un entretien existant depuis Google Sheets
    """
    try:
        spreadsheet = _client.open_by_url(sheet_url)
        worksheet = spreadsheet.worksheet("Entretien RH")
        
        all_records = worksheet.get_all_records()
        
        for record in all_records:
            if str(record.get("Matricule", "")) == str(matricule):
                return record
        
        return None
        
    except gspread.WorksheetNotFound:
        st.warning("L'onglet 'Entretien RH' n'existe pas encore. Il sera créé lors de la première sauvegarde.")
        return None
    except Exception as e:
        st.error(f"Erreur lors du chargement de l'entretien : {str(e)}")
        return None

def create_entretien_sheet_if_not_exists(_client, sheet_url):
    """
    Crée l'onglet "Entretien RH" s'il n'existe pas déjà.
    """
    try:
        spreadsheet = _client.open_by_url(sheet_url)
        
        try:
            spreadsheet.worksheet("Entretien RH")
            return True
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title="Entretien RH", rows="1000", cols="57")
            
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
                "Attentes_Manager", "Avis_RH_Synthese", "Decision_RH_Poste"
            ]
            
            worksheet.update('A1:BD1', [headers])
            return True
            
    except Exception as e:
        st.error(f"Erreur lors de la création de l'onglet 'Entretien RH' : {str(e)}")
        return False

def auto_save_entretien(gsheet_client, sheet_url, entretien_data):
    """Sauvegarde automatique silencieuse avec gestion des accès concurrents"""
    if entretien_data and entretien_data.get("Matricule"):
        try:
            save_entretien_to_gsheet(gsheet_client, sheet_url, entretien_data, show_success=False)
            paris_tz = pytz.timezone('Europe/Paris')
            st.session_state.last_save_time = datetime.now(paris_tz)
        except Exception as e:
            # Sauvegarde silencieuse - on ne bloque pas l'utilisateur en cas d'erreur
            pass

def save_entretien_to_gsheet(_client, sheet_url, entretien_data, show_success=True, max_retries=3):
    """
    Sauvegarde un entretien RH dans l'onglet "Entretien RH".
    Gère les sauvegardes concurrentes avec système de retry.
    """
    for attempt in range(max_retries):
        try:
            spreadsheet = _client.open_by_url(sheet_url)
            worksheet = spreadsheet.worksheet("Entretien RH")
            
            # Recharger les données à chaque tentative pour éviter les conflits
            all_records = worksheet.get_all_records()
            existing_row = None
            
            for idx, record in enumerate(all_records):
                if str(record.get("Matricule", "")) == str(entretien_data.get("Matricule", "")):
                    existing_row = idx + 2
                    break
            
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
                entretien_data.get("Avis_RH_Synthese", ""),
                entretien_data.get("Decision_RH_Poste", "")
            ]
            
            if existing_row:
                worksheet.update(f'A{existing_row}:BD{existing_row}', [row_data])
            else:
                worksheet.append_row(row_data)
            
            # Mettre à jour le temps de dernière sauvegarde en heure de Paris
            paris_tz = pytz.timezone('Europe/Paris')
            st.session_state.last_save_time = datetime.now(paris_tz)
            
            if show_success:
                st.success(f"✅ Sauvegarde effectuée à {st.session_state.last_save_time.strftime('%H:%M:%S')}")
            
            return True
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))  # Backoff exponentiel
                continue
            else:
                if show_success:
                    st.error(f"Erreur lors de la sauvegarde après {max_retries} tentatives : {str(e)}")
                return False

def update_voeu_retenu(_client, sheet_url, matricule, poste):
    """
    Met à jour la colonne 'Vœux Retenu' dans l'onglet CAP 2025
    """
    try:
        spreadsheet = _client.open_by_url(sheet_url)
        worksheet = spreadsheet.worksheet("CAP 2025")
        
        all_values = worksheet.get_all_values()
        headers = all_values[1]
        
        # Trouver l'index de la colonne "Vœux Retenu"
        try:
            voeu_retenu_col = headers.index("Vœux Retenu") + 1
            matricule_col = headers.index("Matricule") + 1
        except ValueError:
            st.error("Colonnes 'Vœux Retenu' ou 'Matricule' introuvables")
            return False
        
        # Trouver la ligne du collaborateur
        for idx, row in enumerate(all_values[2:], start=3):
            if row[matricule_col - 1] == str(matricule):
                # Mettre à jour la cellule
                worksheet.update_cell(idx, voeu_retenu_col, poste)
                
                # Vider le cache pour forcer le rechargement
                st.cache_data.clear()
                return True
        
        st.error("Matricule introuvable")
        return False
        
    except Exception as e:
        st.error(f"Erreur lors de la mise à jour : {str(e)}")
        return False

def update_commentaire_rh(_client, sheet_url, matricule, commentaire):
    """
    Ajoute un commentaire dans la colonne 'Commentaires RH' de l'onglet CAP 2025
    """
    try:
        spreadsheet = _client.open_by_url(sheet_url)
        worksheet = spreadsheet.worksheet("CAP 2025")
        
        all_values = worksheet.get_all_values()
        headers = all_values[1]
        
        # Trouver l'index des colonnes
        try:
            commentaire_col = headers.index("Commentaires RH") + 1
            matricule_col = headers.index("Matricule") + 1
        except ValueError:
            st.error("Colonnes 'Commentaires RH' ou 'Matricule' introuvables")
            return False
        
        # Trouver la ligne du collaborateur
        for idx, row in enumerate(all_values[2:], start=3):
            if row[matricule_col - 1] == str(matricule):
                # Récupérer le commentaire existant et ajouter le nouveau
                existing_comment = row[commentaire_col - 1]
                new_comment = f"{existing_comment}\n{commentaire}" if existing_comment else commentaire
                worksheet.update_cell(idx, commentaire_col, new_comment)
                
                # Vider le cache pour forcer le rechargement
                st.cache_data.clear()
                return True
        
        st.error("Matricule introuvable")
        return False
        
    except Exception as e:
        st.error(f"Erreur lors de la mise à jour : {str(e)}")
        return False

def calculate_anciennete(date_str):
    """Calcule l'ancienneté en années à partir d'une date"""
    if not date_str or date_str.strip() == "":
        return "N/A"
    
    try:
        for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
            try:
                date_entree = datetime.strptime(date_str, fmt)
                delta = datetime.now() - date_entree
                annees = delta.days / 365.25
                
                if annees < 1:
                    return "< 1 année"
                elif annees < 2:
                    return "1 année"
                else:
                    return f"{int(annees)} années"
            except ValueError:
                continue
        
        return date_str
    except:
        return date_str

def parse_date(date_str):
    """Parse une date en gérant différents formats"""
    if not date_str or date_str.strip() == "":
        return None
    
    for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None

def get_safe_value(value):
    """Retourne une valeur string sûre, évitant les Series pandas"""
    if isinstance(value, pd.Series):
        if len(value) > 0:
            val = value.iloc[0]
            return str(val) if pd.notna(val) and val != "" else ""
        return ""
    try:
        if pd.isna(value):
            return ""
    except (ValueError, TypeError):
        pass
    return str(value) if value else ""

# --- URL DU GOOGLE SHEET ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1BXez24VFNhb470PrCjwNIFx6GdJFqLnVh8nFf3gGGvw/edit?usp=sharing"

# --- INITIALISATION ---
init_session_state()

try:
    gsheet_client = get_gsheet_connection()
    if gsheet_client:
        st.sidebar.success("✅ Connexion Google Sheets établie")
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
    ["📊 Tableau de Bord", "👥 Gestion des Candidatures", "📝 Entretien RH", "🎯 Analyse par Poste", "🌳 Référentiel Postes"],
    label_visibility="collapsed"
)

# Bouton de rafraîchissement
st.sidebar.divider()
if st.sidebar.button("🔄 Rafraîchir les données", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()
# Heure de Paris
paris_tz = pytz.timezone('Europe/Paris')
paris_time = datetime.now(paris_tz)
st.sidebar.caption(f"Dernière mise à jour : {paris_time.strftime('%H:%M:%S')}")

# Afficher le temps de dernière sauvegarde si disponible
if st.session_state.last_save_time:
    st.sidebar.caption(f"💾 Dernière sauvegarde : {st.session_state.last_save_time.strftime('%H:%M:%S')}")

# ========================================
# PAGE 1 : TABLEAU DE BORD (Optimisé UX 2026)
# ========================================
elif page == " 📊 Tableau de Bord":
    
    # --- CSS PERSONNALISÉ POUR LE DASHBOARD ---
    st.markdown("""
    <style>
        /* Style des cartes KPI */
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            transition: transform 0.2s;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            border-color: #1967D2; /* Couleur Brand */
        }
        /* Titres de section plus discrets */
        h3 { font-size: 1.2rem; color: #555; font-weight: 600; margin-top: 20px;}
    </style>
    """, unsafe_allow_html=True)

    st.title("📊 Pilotage de la Campagne")
    st.markdown("Vue d'ensemble de l'avancement et des points d'attention.")

    # Calcul des KPI (Ton code existant, un peu nettoyé)
    kpis = calculate_kpis(collaborateurs_df)
    
    # --- LIGNE 1 : KPI MACRO (L'essentiel en un coup d'œil) ---
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Collaborateurs", 
            value=kpis['nb_collaborateurs'], 
            delta="Cibles identifiées", 
            delta_color="off"
        )
    with col2:
        # Calcul dynamique d'un % d'avancement
        progression = round((kpis['nb_entretiens_realises'] / kpis['nb_collaborateurs']) * 100, 1) if kpis['nb_collaborateurs'] > 0 else 0
        st.metric(
            label="Entretiens Réalisés", 
            value=kpis['nb_entretiens_realises'], 
            delta=f"{progression}% de l'objectif"
        )
    with col3:
        # Focus sur l'urgence
        st.metric(
            label="À Planifier", 
            value=kpis['nb_a_planifier'], 
            delta="Priorité haute", 
            delta_color="inverse" # Rouge si positif (car c'est une charge de travail)
        )
    with col4:
        st.metric(
            label="Mobilités Validées", 
            value=kpis['nb_voeux_retenus'], 
            delta="Succès confirmés", 
            delta_color="normal"
        )

    st.divider()

    # --- LIGNE 2 : ANALYSE GRAPHIQUE (UX : Comparaison visuelle) ---
    c_chart1, c_chart2 = st.columns([2, 1])

    with c_chart1:
        st.subheader("📈 Avancement par Direction")
        # Préparation des données pour le graph
        df_chart = collaborateurs_df.groupby("Direction libellé").apply(
            lambda x: pd.Series({
                "Total": len(x),
                "Réalisés": len(x[x["Statut Entretien"] == "Réalisé"])
            })
        ).reset_index()
        
        # Transformation format "Long" pour Altair (Stack bar)
        df_long = df_chart.melt('Direction libellé', var_name='Type', value_name='Nombre')
        
        chart = alt.Chart(df_long).mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
            x=alt.X('Direction libellé', axis=alt.Axis(labelAngle=-45, title=None)),
            y=alt.Y('Nombre', title=None),
            color=alt.Color('Type', scale=alt.Scale(domain=['Total', 'Réalisés'], range=['#E0E0E0', '#1967D2'])),
            tooltip=['Direction libellé', 'Type', 'Nombre']
        ).properties(height=350).configure_axis(grid=False).configure_view(strokeWidth=0)
        
        st.altair_chart(chart, use_container_width=True)

    with c_chart2:
        st.subheader("🎯 Taux de Transformation")
        # Donut Chart pour le statut global
        status_counts = collaborateurs_df["Statut Entretien"].value_counts().reset_index()
        status_counts.columns = ["Statut", "Nombre"]
        
        donut = alt.Chart(status_counts).mark_arc(innerRadius=50).encode(
            theta=alt.Theta("Nombre", stack=True),
            color=alt.Color("Statut", scale=alt.Scale(scheme="blues")),
            tooltip=["Statut", "Nombre"],
            order=alt.Order("Nombre", sort="descending")
        ).properties(height=350)
        
        st.altair_chart(donut, use_container_width=True)

    # --- LIGNE 3 : CALL TO ACTION (UX : "What's next?") ---
    st.info("💡 **Conseil** : Il reste **{} entretiens** à planifier. Rendez-vous dans l'onglet 'Suivi des Entretiens' pour relancer les collaborateurs.".format(kpis['nb_a_planifier']))
    
    # Graphiques
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("🔥 Top 10 des postes les plus demandés")
        
        all_voeux = pd.concat([
            collaborateurs_df["Vœux 1"],
            collaborateurs_df["Vœux 2"],
            collaborateurs_df["Voeux 3"]
        ])
        all_voeux = all_voeux[
            all_voeux.notna() & 
            (all_voeux.astype(str).str.strip() != "") & 
            (all_voeux.astype(str).str.strip() != "Positionnement manquant")
        ]
        
        if len(all_voeux) > 0:
            top_postes = all_voeux.value_counts().head(10)
            
            top_df = pd.DataFrame({
                "Classement": range(1, len(top_postes) + 1),
                "Poste": top_postes.index,
                "Nombre de vœux": top_postes.values
            })
            
            st.dataframe(
                top_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Classement": st.column_config.NumberColumn(width="small"),
                    "Nombre de vœux": st.column_config.NumberColumn(width="small"),
                    "Poste": st.column_config.TextColumn(width="large")
                }
            )
        else:
            st.info("Aucun vœu enregistré pour le moment")
    
    with col_chart2:
        st.subheader("⚠️ Flop 10 des postes les moins demandés")
        
        if len(all_voeux) > 0:
            flop_postes = all_voeux.value_counts().sort_values(ascending=True).head(10)
            
            flop_df = pd.DataFrame({
                "Classement": range(1, len(flop_postes) + 1),
                "Poste": flop_postes.index,
                "Nombre de vœux": flop_postes.values
            })
            
            st.dataframe(
                flop_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Classement": st.column_config.NumberColumn(width="small"),
                    "Nombre de vœux": st.column_config.NumberColumn(width="small"),
                    "Poste": st.column_config.TextColumn(width="large")
                }
            )
        else:
            st.info("Aucun vœu enregistré pour le moment")

# ========================================
# PAGE 2 : GESTION DES CANDIDATURES
# ========================================

elif page == "👥 Gestion des Candidatures":
    st.title("👥 Gestion des Candidatures")
    
    # Filtres
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
        filtre_direction = st.multiselect(
            "Filtrer par Direction",
            options=sorted(collaborateurs_df["Direction libellé"].unique()),
            default=[]
        )
    
    with col_f2:
        all_collabs = sorted((collaborateurs_df["NOM"] + " " + collaborateurs_df["Prénom"]).unique())
        filtre_collaborateur = st.multiselect(
            "Filtrer par Collaborateur",
            options=all_collabs,
            default=[]
        )
    
    with col_f3:
        search_nom = st.text_input("🔍 Rechercher un collaborateur par son nom")
    
    with col_f4:
        filtre_rrh = st.multiselect(
            "Filtrer par RRH",
            options=sorted(collaborateurs_df["Référente RH"].unique()),
            default=[]
        )
    
    filtre_date_rdv = st.date_input(
        "Filtrer par Date de rdv",
        value=None
    )
    
    # Appliquer les filtres
    df_filtered = collaborateurs_df.copy()
    df_filtered = df_filtered[df_filtered["Matricule"].notna() & (df_filtered["Matricule"].astype(str).str.strip() != "")]
    
    if filtre_direction:
        df_filtered = df_filtered[df_filtered["Direction libellé"].isin(filtre_direction)]
    
    if filtre_collaborateur:
        collab_filter_mask = df_filtered.apply(
            lambda row: f"{row['NOM']} {row['Prénom']}" in filtre_collaborateur, 
            axis=1
        )
        df_filtered = df_filtered[collab_filter_mask]
    
    if search_nom:
        df_filtered = df_filtered[df_filtered["NOM"].str.contains(search_nom, case=False, na=False)]
    
    if filtre_rrh:
        df_filtered = df_filtered[df_filtered["Référente RH"].isin(filtre_rrh)]
    
    if filtre_date_rdv:
        df_filtered = df_filtered[df_filtered["Date de rdv"].apply(
            lambda x: parse_date(x) == filtre_date_rdv
        )]
    
    # Préparer les données pour l'affichage
    display_df = pd.DataFrame()
    
    for idx, row in df_filtered.iterrows():
        anciennete = calculate_anciennete(get_safe_value(row.get("Date entrée groupe", "")))
        
        date_rdv = get_safe_value(row.get("Date de rdv", ""))
        heure_rdv = get_safe_value(row.get("Heure de rdv", ""))
        
        if date_rdv and date_rdv.strip() != "":
            entretien = f"{date_rdv} à {heure_rdv}" if heure_rdv and heure_rdv.strip() != "" else date_rdv
        else:
            entretien = ""
        
        assessment = get_safe_value(row.get("Assesment à planifier O/N", "Non"))
        if not assessment or assessment.strip() == "":
            assessment = "Non"
        
        prenom_manager = get_safe_value(row.get('Prénom Manager', ''))
        nom_manager = get_safe_value(row.get('Nom Manager', ''))
        manager_actuel = f"{prenom_manager} {nom_manager}".strip()
        
        voeu_1 = get_safe_value(row.get("Vœux 1", ""))
        voeu_2 = get_safe_value(row.get("Vœux 2", ""))
        voeu_3 = get_safe_value(row.get("Voeux 3", ""))
        
        if voeu_2 == "Positionnement manquant":
            voeu_2 = ""
        if voeu_3 == "Positionnement manquant":
            voeu_3 = ""
        
        display_row = {
            "Prénom": get_safe_value(row.get("Prénom", "")),
            "NOM": get_safe_value(row.get("NOM", "")),
            "Poste actuel": get_safe_value(row.get("Poste  libellé", "")),
            "CSP": get_safe_value(row.get("CSP", "")),
            "Classification": get_safe_value(row.get("Classification", "")),
            "Manager": get_safe_value(row.get("Manager", "")),
            "Nomade": get_safe_value(row.get("Nomade", "")),
            "Ancienneté": anciennete,
            "Direction": get_safe_value(row.get("Direction libellé", "")),
            "Manager actuel": manager_actuel,
            "Rencontre RH": get_safe_value(row.get("Rencontre RH / Positionnement", "")),
            "Priorité": get_safe_value(row.get("Priorité", "")),
            "Référente RH": get_safe_value(row.get("Référente RH", "")),
            "📅 Entretien": entretien,
            "Vœu 1": voeu_1,
            "Vœu 2": voeu_2,
            "Vœu 3": voeu_3,
            "Assessment": assessment,
            "Date Assessment": get_safe_value(row.get("Date Assessment", "")),
            "Vœux Retenu": get_safe_value(row.get("Vœux Retenu", "")),
            "Commentaires RH": get_safe_value(row.get("Commentaires RH", "")),
            "Matricule": get_safe_value(row.get("Matricule", ""))
        }
        
        display_df = pd.concat([display_df, pd.DataFrame([display_row])], ignore_index=True)
    
    # Affichage du tableau
    if not display_df.empty:
        st.dataframe(
            display_df.drop(columns=["Matricule"]),
            use_container_width=True,
            hide_index=True
        )
        
        st.divider()
        
        # Sélection d'un collaborateur pour accéder à l'entretien
        st.subheader("🔍 Accès rapide à un entretien RH")
        
        col_select1, col_select2 = st.columns([3, 1])
        
        with col_select1:
            selected_for_entretien = st.selectbox(
                "Sélectionner un collaborateur pour accéder à son entretien",
                options=["-- Sélectionner --"] + [
                    f"{row['NOM']} {row['Prénom']}" 
                    for _, row in display_df.iterrows()
                ],
                key="select_entretien_from_list"
            )
        
        with col_select2:
            if st.button("➡️ Aller à l'entretien", type="primary", disabled=(selected_for_entretien == "-- Sélectionner --"), key="goto_entretien_btn"):
            # Récupérer le matricule du collaborateur sélectionné
                collab_mask = (display_df["NOM"] + " " + display_df["Prénom"]) == selected_for_entretien
                if collab_mask.any():
                    matricule = display_df[collab_mask]["Matricule"].iloc[0]
 # Charger l'entretien existant
                    existing_entretien = load_entretien_from_gsheet(gsheet_client, SHEET_URL, matricule)
            
            # Récupérer les infos du collaborateur depuis CAP 2025
                    collab_full_mask = (collaborateurs_df["NOM"] + " " + collaborateurs_df["Prénom"]) == selected_for_entretien
                    collab = collaborateurs_df[collab_full_mask].iloc[0]
            
                    if existing_entretien:
                        st.session_state.entretien_data = existing_entretien
                    else:
                        st.session_state.entretien_data = {
                            "Matricule": matricule,
                            "Nom": get_safe_value(collab.get('NOM', '')),
                            "Prénom": get_safe_value(collab.get('Prénom', '')),
                            "Date_Entretien": datetime.now().strftime("%d/%m/%Y"),
                            "Referente_RH": get_safe_value(collab.get('Référente RH', '')),
                            "Voeu_1": get_safe_value(collab.get('Vœux 1', '')),
                            "Voeu_2": get_safe_value(collab.get('Vœux 2', '')),
                            "Voeu_3": get_safe_value(collab.get('Voeux 3', ''))
                      }
            
                    st.session_state.current_matricule = matricule
                    st.session_state.selected_collaborateur = selected_for_entretien
                    st.session_state.navigate_to_entretien = True
            
            # Forcer la navigation vers la page Entretien RH
                    st.switch_page("app_rh_cloud.py")  # Ou le nom de votre fichier principal

# ========================================
# PAGE 3 : ENTRETIEN RH (PARTIE 1/2)
# ========================================

elif page == "📝 Entretien RH":
    st.title("📝 Conduite d'Entretien RH - CAP 2025")
    
    # Info box avec sauvegarde automatique
    col_info1, col_info2 = st.columns([3, 1])
    with col_info1:
        st.info("""
        📝 Vos saisies sont sauvegardées automatiquement dans Google Sheets.
        💡 Vous pouvez revenir sur cette page à tout moment pour consulter ou modifier un entretien.
        """)
    
    with col_info2:
        if st.button("💾 Sauvegarder maintenant", type="secondary", use_container_width=True):
            if st.session_state.entretien_data and st.session_state.current_matricule:
                save_entretien_to_gsheet(gsheet_client, SHEET_URL, st.session_state.entretien_data, show_success=True)
    
    st.divider()
    
    # ===== SECTION 1 : SÉLECTION DU COLLABORATEUR =====
    st.subheader("1️⃣ Sélection du collaborateur")
    
    # Création de deux colonnes pour les modes d'accès
    col_mode1, col_mode2 = st.columns(2)
    
    with col_mode1:
        st.markdown("#### 🆕 Nouvel entretien")
        
        col_dir, col_collab = st.columns([1, 2])
        
        with col_dir:
            selected_direction = st.selectbox(
                "Filtrer par Direction",
                options=["-- Toutes --"] + sorted(collaborateurs_df["Direction libellé"].unique()),
                key="filter_direction_new"
            )
        
        if selected_direction == "-- Toutes --":
            filtered_collabs_df = collaborateurs_df
        else:
            filtered_collabs_df = collaborateurs_df[collaborateurs_df["Direction libellé"] == selected_direction]
        
        collaborateur_list = sorted(
            (filtered_collabs_df["NOM"] + " " + filtered_collabs_df["Prénom"]).tolist()
        )
        
        with col_collab:
            # Vérifier s'il y a une navigation depuis une autre page
            default_index = 0
            if st.session_state.get('navigate_to_entretien') and st.session_state.get('selected_collaborateur'):
                if st.session_state['selected_collaborateur'] in collaborateur_list:
                    default_index = collaborateur_list.index(st.session_state['selected_collaborateur']) + 1
                st.session_state['navigate_to_entretien'] = False
            
            selected_collab_new = st.selectbox(
                "Sélectionner un collaborateur",
                options=["-- Sélectionner --"] + collaborateur_list,
                index=default_index,
                key="select_collab_new"
            )
        
        if st.button("▶️ Démarrer/Reprendre l'entretien", type="primary", disabled=(selected_collab_new == "-- Sélectionner --"), use_container_width=True):
            # Récupérer les infos du collaborateur
            collab_mask = (collaborateurs_df["NOM"] + " " + collaborateurs_df["Prénom"]) == selected_collab_new
            collab = collaborateurs_df[collab_mask].iloc[0]
            matricule = get_safe_value(collab.get('Matricule', ''))
            
            # Charger l'entretien existant ou initialiser un nouveau
            existing_entretien = load_entretien_from_gsheet(gsheet_client, SHEET_URL, matricule)
            
            if existing_entretien:
                # Charger les données existantes
                st.session_state.entretien_data = existing_entretien
                st.info(f"✅ Entretien existant chargé pour {selected_collab_new}")
            else:
                # Initialiser un nouvel entretien
                st.session_state.entretien_data = {
                    "Matricule": matricule,
                    "Nom": get_safe_value(collab.get('NOM', '')),
                    "Prénom": get_safe_value(collab.get('Prénom', '')),
                    "Date_Entretien": datetime.now().strftime("%d/%m/%Y"),
                    "Referente_RH": get_safe_value(collab.get('Référente RH', '')),
                    "Voeu_1": get_safe_value(collab.get('Vœux 1', '')),
                    "Voeu_2": get_safe_value(collab.get('Vœux 2', '')),
                    "Voeu_3": get_safe_value(collab.get('Voeux 3', ''))
                }
            
            st.session_state.current_matricule = matricule
            st.session_state.selected_collaborateur = selected_collab_new
            st.rerun()
    
    with col_mode2:
        st.markdown("#### 📂 Consulter un entretien existant")
        
        # Charger la liste des entretiens existants
        try:
            spreadsheet = gsheet_client.open_by_url(SHEET_URL)
            worksheet = spreadsheet.worksheet("Entretien RH")
            all_records = worksheet.get_all_records()
            
            entretiens_existants = [f"{record['Nom']} {record['Prénom']}" for record in all_records if record.get('Matricule')]
            
            if entretiens_existants:
                selected_existing = st.selectbox(
                    "Entretiens déjà sauvegardés",
                    options=["-- Sélectionner --"] + sorted(entretiens_existants),
                    key="select_existing_entretien"
                )
                
                if st.button("📖 Ouvrir cet entretien", type="secondary", disabled=(selected_existing == "-- Sélectionner --"), use_container_width=True):
                    # Trouver le matricule correspondant
                    for record in all_records:
                        if f"{record['Nom']} {record['Prénom']}" == selected_existing:
                            st.session_state.entretien_data = record
                            st.session_state.current_matricule = record['Matricule']
                            st.session_state.selected_collaborateur = selected_existing
                            st.success(f"✅ Entretien chargé : {selected_existing}")
                            st.rerun()
                            break
            else:
                st.info("Aucun entretien sauvegardé pour le moment")
                
        except Exception as e:
            st.warning("Impossible de charger les entretiens existants")
    
    # ===== SECTION 2 : FORMULAIRE D'ENTRETIEN =====
    if st.session_state.current_matricule and st.session_state.selected_collaborateur:
        st.divider()
        
        # Récupérer les infos du collaborateur depuis CAP 2025
        collab_mask = (collaborateurs_df["NOM"] + " " + collaborateurs_df["Prénom"]) == st.session_state.selected_collaborateur
        if collab_mask.any():
            collab = collaborateurs_df[collab_mask].iloc[0]
            
            # Afficher les infos du collaborateur
            with st.container(border=True):
                col_info1, col_info2, col_info3 = st.columns(3)
                
                with col_info1:
                    st.markdown(f"**Matricule** : {get_safe_value(collab.get('Matricule', 'N/A'))}")
                    st.markdown(f"**Nom** : {get_safe_value(collab.get('NOM', ''))} {get_safe_value(collab.get('Prénom', ''))}")
                    st.markdown(f"**Mail** : {get_safe_value(collab.get('Mail', 'N/A'))}")
                
                with col_info2:
                    st.markdown(f"**Poste actuel** : {get_safe_value(collab.get('Poste  libellé', 'N/A'))}")
                    st.markdown(f"**Direction** : {get_safe_value(collab.get('Direction libellé', 'N/A'))}")
                    anciennete_display = calculate_anciennete(get_safe_value(collab.get("Date entrée groupe", "")))
                    st.markdown(f"**Ancienneté** : {anciennete_display}")
                
                with col_info3:
                    st.markdown(f"**RRH** : {get_safe_value(collab.get('Référente RH', 'N/A'))}")
                    st.markdown(f"**Date RDV** : {get_safe_value(collab.get('Date de rdv', 'N/A'))}")
                    st.markdown(f"**Priorité** : {get_safe_value(collab.get('Priorité', 'N/A'))}")
            
            st.divider()
            
            # Bouton pour changer de collaborateur
            if st.button("🔄 Sélectionner un autre collaborateur"):
                st.session_state.current_matricule = None
                st.session_state.selected_collaborateur = None
                st.session_state.entretien_data = {}
                st.rerun()
            
            # Tabs pour les 3 vœux
            voeu1_label = st.session_state.entretien_data.get('Voeu_1', 'Non renseigné')
            voeu2_label = st.session_state.entretien_data.get('Voeu_2', 'Non renseigné')
            voeu3_label = st.session_state.entretien_data.get('Voeu_3', 'Non renseigné')
            
            tab_voeu1, tab_voeu2, tab_voeu3, tab_avis = st.tabs([
                f"🎯 Vœu 1: {voeu1_label if voeu1_label else 'Non renseigné'}", 
                f"🎯 Vœu 2: {voeu2_label if voeu2_label else 'Non renseigné'}", 
                f"🎯 Vœu 3: {voeu3_label if voeu3_label else 'Non renseigné'}",
                "💬 Avis RH"
            ])
            
           # ========== VŒEU 1 ==========
            with tab_voeu1:
                if voeu1_label and voeu1_label != "Positionnement manquant" and voeu1_label != "Non renseigné":
                    st.subheader(f"Évaluation du Vœu 1 : {voeu1_label}")
                    
                    # Afficher un indicateur de dernière sauvegarde
                    if st.session_state.last_save_time:
                        st.caption(f"💾 Dernière sauvegarde automatique : {st.session_state.last_save_time.strftime('%H:%M:%S')}")
                    
                    st.markdown("#### 📋 Questions générales")
                    
                    v1_motiv = st.text_area(
                        "Quelles sont vos motivations pour ce poste ?",
                        value=st.session_state.entretien_data.get("V1_Motivations", ""),
                        key="v1_motiv",
                        height=100
                    )
                    if v1_motiv != st.session_state.entretien_data.get("V1_Motivations", ""):
                        st.session_state.entretien_data["V1_Motivations"] = v1_motiv
                        auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    v1_vision = st.text_area(
                        "Quelle est votre vision des enjeux du poste ?",
                        value=st.session_state.entretien_data.get("V1_Vision_Enjeux", ""),
                        key="v1_vision",
                        height=100
                    )
                    if v1_vision != st.session_state.entretien_data.get("V1_Vision_Enjeux", ""):
                        st.session_state.entretien_data["V1_Vision_Enjeux"] = v1_vision
                        auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    v1_actions = st.text_area(
                        "Quelles seraient vos premières actions à la prise de poste ?",
                        value=st.session_state.entretien_data.get("V1_Premieres_Actions", ""),
                        key="v1_actions",
                        height=100
                    )
                    if v1_actions != st.session_state.entretien_data.get("V1_Premieres_Actions", ""):
                        st.session_state.entretien_data["V1_Premieres_Actions"] = v1_actions
                        auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    st.markdown("#### 🎯 Évaluation des compétences")
                    
                    # Compétence 1
                    col_comp1_1, col_comp1_2 = st.columns([1, 2])
                    with col_comp1_1:
                        v1_c1_nom = st.text_input(
                            "Compétence 1",
                            value=st.session_state.entretien_data.get("V1_Competence_1_Nom", ""),
                            key="v1_c1_nom"
                        )
                        if v1_c1_nom != st.session_state.entretien_data.get("V1_Competence_1_Nom", ""):
                            st.session_state.entretien_data["V1_Competence_1_Nom"] = v1_c1_nom
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        
                        niveau_options = ["Débutant", "Confirmé", "Expert"]
                        current_niveau = st.session_state.entretien_data.get("V1_Competence_1_Niveau", "Débutant")
                        niveau_index = niveau_options.index(current_niveau) if current_niveau in niveau_options else 0
                        
                        v1_c1_niv = st.selectbox(
                            "Niveau",
                            niveau_options,
                            index=niveau_index,
                            key="v1_c1_niv"
                        )
                        if v1_c1_niv != st.session_state.entretien_data.get("V1_Competence_1_Niveau", ""):
                            st.session_state.entretien_data["V1_Competence_1_Niveau"] = v1_c1_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_comp1_2:
                        v1_c1_just = st.text_area(
                            "Justification et exemples concrets",
                            value=st.session_state.entretien_data.get("V1_Competence_1_Justification", ""),
                            key="v1_c1_just",
                            height=100
                        )
                        if v1_c1_just != st.session_state.entretien_data.get("V1_Competence_1_Justification", ""):
                            st.session_state.entretien_data["V1_Competence_1_Justification"] = v1_c1_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    
                    # Compétence 2
                    col_comp2_1, col_comp2_2 = st.columns([1, 2])
                    with col_comp2_1:
                        v1_c2_nom = st.text_input(
                            "Compétence 2",
                            value=st.session_state.entretien_data.get("V1_Competence_2_Nom", ""),
                            key="v1_c2_nom"
                        )
                        if v1_c2_nom != st.session_state.entretien_data.get("V1_Competence_2_Nom", ""):
                            st.session_state.entretien_data["V1_Competence_2_Nom"] = v1_c2_nom
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        
                        current_niveau = st.session_state.entretien_data.get("V1_Competence_2_Niveau", "Débutant")
                        niveau_index = niveau_options.index(current_niveau) if current_niveau in niveau_options else 0
                        
                        v1_c2_niv = st.selectbox(
                            "Niveau",
                            niveau_options,
                            index=niveau_index,
                            key="v1_c2_niv"
                        )
                        if v1_c2_niv != st.session_state.entretien_data.get("V1_Competence_2_Niveau", ""):
                            st.session_state.entretien_data["V1_Competence_2_Niveau"] = v1_c2_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_comp2_2:
                        v1_c2_just = st.text_area(
                            "Justification et exemples concrets",
                            value=st.session_state.entretien_data.get("V1_Competence_2_Justification", ""),
                            key="v1_c2_just",
                            height=100
                        )
                        if v1_c2_just != st.session_state.entretien_data.get("V1_Competence_2_Justification", ""):
                            st.session_state.entretien_data["V1_Competence_2_Justification"] = v1_c2_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    
                    # Compétence 3
                    col_comp3_1, col_comp3_2 = st.columns([1, 2])
                    with col_comp3_1:
                        v1_c3_nom = st.text_input(
                            "Compétence 3",
                            value=st.session_state.entretien_data.get("V1_Competence_3_Nom", ""),
                            key="v1_c3_nom"
                        )
                        if v1_c3_nom != st.session_state.entretien_data.get("V1_Competence_3_Nom", ""):
                            st.session_state.entretien_data["V1_Competence_3_Nom"] = v1_c3_nom
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        
                        current_niveau = st.session_state.entretien_data.get("V1_Competence_3_Niveau", "Débutant")
                        niveau_index = niveau_options.index(current_niveau) if current_niveau in niveau_options else 0
                        
                        v1_c3_niv = st.selectbox(
                            "Niveau",
                            niveau_options,
                            index=niveau_index,
                            key="v1_c3_niv"
                        )
                        if v1_c3_niv != st.session_state.entretien_data.get("V1_Competence_3_Niveau", ""):
                            st.session_state.entretien_data["V1_Competence_3_Niveau"] = v1_c3_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_comp3_2:
                        v1_c3_just = st.text_area(
                            "Justification et exemples concrets",
                            value=st.session_state.entretien_data.get("V1_Competence_3_Justification", ""),
                            key="v1_c3_just",
                            height=100
                        )
                        if v1_c3_just != st.session_state.entretien_data.get("V1_Competence_3_Justification", ""):
                            st.session_state.entretien_data["V1_Competence_3_Justification"] = v1_c3_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    st.markdown("#### 📊 Expérience")
                    
                    col_exp1, col_exp2 = st.columns([1, 2])
                    with col_exp1:
                        exp_options = ["Débutant (0-3 ans)", "Confirmé (3-7 ans)", "Expert (8+ ans)"]
                        current_exp = st.session_state.entretien_data.get("V1_Experience_Niveau", "Débutant (0-3 ans)")
                        exp_index = exp_options.index(current_exp) if current_exp in exp_options else 0
                        
                        v1_exp_niv = st.selectbox(
                            "Niveau d'expérience dans des contextes comparables",
                            exp_options,
                            index=exp_index,
                            key="v1_exp_niv"
                        )
                        if v1_exp_niv != st.session_state.entretien_data.get("V1_Experience_Niveau", ""):
                            st.session_state.entretien_data["V1_Experience_Niveau"] = v1_exp_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_exp2:
                        v1_exp_just = st.text_area(
                            "Quelle expérience justifie ce niveau ?",
                            value=st.session_state.entretien_data.get("V1_Experience_Justification", ""),
                            key="v1_exp_just",
                            height=100
                        )
                        if v1_exp_just != st.session_state.entretien_data.get("V1_Experience_Justification", ""):
                            st.session_state.entretien_data["V1_Experience_Justification"] = v1_exp_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    st.markdown("#### 🎓 Accompagnement et Formation")
                    
                    col_form1, col_form2 = st.columns([1, 2])
                    with col_form1:
                        accomp_options = ["Non", "Oui"]
                        current_accomp = st.session_state.entretien_data.get("V1_Besoin_Accompagnement", "Non")
                        accomp_index = accomp_options.index(current_accomp) if current_accomp in accomp_options else 0
                        
                        v1_besoin = st.radio(
                            "Besoin d'accompagnement / formation ?",
                            accomp_options,
                            index=accomp_index,
                            key="v1_form_besoin"
                        )
                        if v1_besoin != st.session_state.entretien_data.get("V1_Besoin_Accompagnement", ""):
                            st.session_state.entretien_data["V1_Besoin_Accompagnement"] = v1_besoin
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_form2:
                        if v1_besoin == "Oui":
                            v1_type = st.text_area(
                                "Quels types de soutien ou d'accompagnement ?",
                                value=st.session_state.entretien_data.get("V1_Type_Accompagnement", ""),
                                key="v1_form_type",
                                height=100
                            )
                            if v1_type != st.session_state.entretien_data.get("V1_Type_Accompagnement", ""):
                                st.session_state.entretien_data["V1_Type_Accompagnement"] = v1_type
                                auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        else:
                            if st.session_state.entretien_data.get("V1_Type_Accompagnement", "") != "":
                                st.session_state.entretien_data["V1_Type_Accompagnement"] = ""
                                auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    # Auto-save après chaque onglet
                    if st.button("💾 Sauvegarder Vœu 1", key="save_v1"):
                        save_entretien_to_gsheet(gsheet_client, SHEET_URL, st.session_state.entretien_data, show_success=True)
                
                else:
                    st.warning("Aucun vœu 1 renseigné pour ce collaborateur")
            
           # ========== VŒEU 2 ==========
            with tab_voeu2:
                if voeu2_label and voeu2_label != "Positionnement manquant" and voeu2_label != "Non renseigné":
                    st.subheader(f"Évaluation du Vœu 2 : {voeu2_label}")
                    
                    # Afficher un indicateur de dernière sauvegarde
                    if st.session_state.last_save_time:
                        st.caption(f"💾 Dernière sauvegarde automatique : {st.session_state.last_save_time.strftime('%H:%M:%S')}")
                    
                    st.markdown("#### 📋 Questions générales")
                    
                    v2_motiv = st.text_area(
                        "Quelles sont vos motivations pour ce poste ?",
                        value=st.session_state.entretien_data.get("V2_Motivations", ""),
                        key="v2_motiv",
                        height=100
                    )
                    if v2_motiv != st.session_state.entretien_data.get("V2_Motivations", ""):
                        st.session_state.entretien_data["V2_Motivations"] = v2_motiv
                        auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    v2_vision = st.text_area(
                        "Quelle est votre vision des enjeux du poste ?",
                        value=st.session_state.entretien_data.get("V2_Vision_Enjeux", ""),
                        key="v2_vision",
                        height=100
                    )
                    if v2_vision != st.session_state.entretien_data.get("V2_Vision_Enjeux", ""):
                        st.session_state.entretien_data["V2_Vision_Enjeux"] = v2_vision
                        auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    v2_actions = st.text_area(
                        "Quelles seraient vos premières actions à la prise de poste ?",
                        value=st.session_state.entretien_data.get("V2_Premieres_Actions", ""),
                        key="v2_actions",
                        height=100
                    )
                    if v2_actions != st.session_state.entretien_data.get("V2_Premieres_Actions", ""):
                        st.session_state.entretien_data["V2_Premieres_Actions"] = v2_actions
                        auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    st.markdown("#### 🎯 Évaluation des compétences")
                    
                    # Compétence 1
                    col_comp1_1, col_comp1_2 = st.columns([1, 2])
                    with col_comp1_1:
                        v2_c1_nom = st.text_input(
                            "Compétence 1",
                            value=st.session_state.entretien_data.get("V2_Competence_1_Nom", ""),
                            key="v2_c1_nom"
                        )
                        if v2_c1_nom != st.session_state.entretien_data.get("V2_Competence_1_Nom", ""):
                            st.session_state.entretien_data["V2_Competence_1_Nom"] = v2_c1_nom
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        
                        niveau_options = ["Débutant", "Confirmé", "Expert"]
                        current_niveau = st.session_state.entretien_data.get("V2_Competence_1_Niveau", "Débutant")
                        niveau_index = niveau_options.index(current_niveau) if current_niveau in niveau_options else 0
                        
                        v2_c1_niv = st.selectbox(
                            "Niveau",
                            niveau_options,
                            index=niveau_index,
                            key="v2_c1_niv"
                        )
                        if v2_c1_niv != st.session_state.entretien_data.get("V2_Competence_1_Niveau", ""):
                            st.session_state.entretien_data["V2_Competence_1_Niveau"] = v2_c1_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_comp1_2:
                        v2_c1_just = st.text_area(
                            "Justification et exemples concrets",
                            value=st.session_state.entretien_data.get("V2_Competence_1_Justification", ""),
                            key="v2_c1_just",
                            height=100
                        )
                        if v2_c1_just != st.session_state.entretien_data.get("V2_Competence_1_Justification", ""):
                            st.session_state.entretien_data["V2_Competence_1_Justification"] = v2_c1_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    
                    # Compétence 2
                    col_comp2_1, col_comp2_2 = st.columns([1, 2])
                    with col_comp2_1:
                        v2_c2_nom = st.text_input(
                            "Compétence 2",
                            value=st.session_state.entretien_data.get("V2_Competence_2_Nom", ""),
                            key="v2_c2_nom"
                        )
                        if v2_c2_nom != st.session_state.entretien_data.get("V2_Competence_2_Nom", ""):
                            st.session_state.entretien_data["V2_Competence_2_Nom"] = v2_c2_nom
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        
                        current_niveau = st.session_state.entretien_data.get("V2_Competence_2_Niveau", "Débutant")
                        niveau_index = niveau_options.index(current_niveau) if current_niveau in niveau_options else 0
                        
                        v2_c2_niv = st.selectbox(
                            "Niveau",
                            niveau_options,
                            index=niveau_index,
                            key="v2_c2_niv"
                        )
                        if v2_c2_niv != st.session_state.entretien_data.get("V2_Competence_2_Niveau", ""):
                            st.session_state.entretien_data["V2_Competence_2_Niveau"] = v2_c2_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_comp2_2:
                        v2_c2_just = st.text_area(
                            "Justification et exemples concrets",
                            value=st.session_state.entretien_data.get("V2_Competence_2_Justification", ""),
                            key="v2_c2_just",
                            height=100
                        )
                        if v2_c2_just != st.session_state.entretien_data.get("V2_Competence_2_Justification", ""):
                            st.session_state.entretien_data["V2_Competence_2_Justification"] = v2_c2_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    
                    # Compétence 3
                    col_comp3_1, col_comp3_2 = st.columns([1, 2])
                    with col_comp3_1:
                        v2_c3_nom = st.text_input(
                            "Compétence 3",
                            value=st.session_state.entretien_data.get("V2_Competence_3_Nom", ""),
                            key="v2_c3_nom"
                        )
                        if v2_c3_nom != st.session_state.entretien_data.get("V2_Competence_3_Nom", ""):
                            st.session_state.entretien_data["V2_Competence_3_Nom"] = v2_c3_nom
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        
                        current_niveau = st.session_state.entretien_data.get("V2_Competence_3_Niveau", "Débutant")
                        niveau_index = niveau_options.index(current_niveau) if current_niveau in niveau_options else 0
                        
                        v2_c3_niv = st.selectbox(
                            "Niveau",
                            niveau_options,
                            index=niveau_index,
                            key="v2_c3_niv"
                        )
                        if v2_c3_niv != st.session_state.entretien_data.get("V2_Competence_3_Niveau", ""):
                            st.session_state.entretien_data["V2_Competence_3_Niveau"] = v2_c3_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_comp3_2:
                        v2_c3_just = st.text_area(
                            "Justification et exemples concrets",
                            value=st.session_state.entretien_data.get("V2_Competence_3_Justification", ""),
                            key="v2_c3_just",
                            height=100
                        )
                        if v2_c3_just != st.session_state.entretien_data.get("V2_Competence_3_Justification", ""):
                            st.session_state.entretien_data["V2_Competence_3_Justification"] = v2_c3_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    st.markdown("#### 📊 Expérience")
                    
                    col_exp1, col_exp2 = st.columns([1, 2])
                    with col_exp1:
                        exp_options = ["Débutant (0-3 ans)", "Confirmé (3-7 ans)", "Expert (8+ ans)"]
                        current_exp = st.session_state.entretien_data.get("V2_Experience_Niveau", "Débutant (0-3 ans)")
                        exp_index = exp_options.index(current_exp) if current_exp in exp_options else 0
                        
                        v2_exp_niv = st.selectbox(
                            "Niveau d'expérience dans des contextes comparables",
                            exp_options,
                            index=exp_index,
                            key="v2_exp_niv"
                        )
                        if v2_exp_niv != st.session_state.entretien_data.get("V2_Experience_Niveau", ""):
                            st.session_state.entretien_data["V2_Experience_Niveau"] = v2_exp_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_exp2:
                        v2_exp_just = st.text_area(
                            "Quelle expérience justifie ce niveau ?",
                            value=st.session_state.entretien_data.get("V2_Experience_Justification", ""),
                            key="v2_exp_just",
                            height=100
                        )
                        if v2_exp_just != st.session_state.entretien_data.get("V2_Experience_Justification", ""):
                            st.session_state.entretien_data["V2_Experience_Justification"] = v2_exp_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    st.markdown("#### 🎓 Accompagnement et Formation")
                    
                    col_form1, col_form2 = st.columns([1, 2])
                    with col_form1:
                        accomp_options = ["Non", "Oui"]
                        current_accomp = st.session_state.entretien_data.get("V2_Besoin_Accompagnement", "Non")
                        accomp_index = accomp_options.index(current_accomp) if current_accomp in accomp_options else 0
                        
                        v2_besoin = st.radio(
                            "Besoin d'accompagnement / formation ?",
                            accomp_options,
                            index=accomp_index,
                            key="v2_form_besoin"
                        )
                        if v2_besoin != st.session_state.entretien_data.get("V2_Besoin_Accompagnement", ""):
                            st.session_state.entretien_data["V2_Besoin_Accompagnement"] = v2_besoin
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_form2:
                        if v2_besoin == "Oui":
                            v2_type = st.text_area(
                                "Quels types de soutien ou d'accompagnement ?",
                                value=st.session_state.entretien_data.get("V2_Type_Accompagnement", ""),
                                key="v2_form_type",
                                height=100
                            )
                            if v2_type != st.session_state.entretien_data.get("V2_Type_Accompagnement", ""):
                                st.session_state.entretien_data["V2_Type_Accompagnement"] = v2_type
                                auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        else:
                            if st.session_state.entretien_data.get("V2_Type_Accompagnement", "") != "":
                                st.session_state.entretien_data["V2_Type_Accompagnement"] = ""
                                auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    if st.button("💾 Sauvegarder Vœu 2", key="save_v2"):
                        save_entretien_to_gsheet(gsheet_client, SHEET_URL, st.session_state.entretien_data, show_success=True)
                
                else:
                    st.warning("Aucun vœu 2 renseigné pour ce collaborateur")
            
           # ========== VŒEU 3 ==========
            with tab_voeu3:
                if voeu3_label and voeu3_label != "Positionnement manquant" and voeu3_label != "Non renseigné":
                    st.subheader(f"Évaluation du Vœu 3 : {voeu3_label}")
                    
                    # Afficher un indicateur de dernière sauvegarde
                    if st.session_state.last_save_time:
                        st.caption(f"💾 Dernière sauvegarde automatique : {st.session_state.last_save_time.strftime('%H:%M:%S')}")
                    
                    st.markdown("#### 📋 Questions générales")
                    
                    v3_motiv = st.text_area(
                        "Quelles sont vos motivations pour ce poste ?",
                        value=st.session_state.entretien_data.get("V3_Motivations", ""),
                        key="v3_motiv",
                        height=100
                    )
                    if v3_motiv != st.session_state.entretien_data.get("V3_Motivations", ""):
                        st.session_state.entretien_data["V3_Motivations"] = v3_motiv
                        auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    v3_vision = st.text_area(
                        "Quelle est votre vision des enjeux du poste ?",
                        value=st.session_state.entretien_data.get("V3_Vision_Enjeux", ""),
                        key="v3_vision",
                        height=100
                    )
                    if v3_vision != st.session_state.entretien_data.get("V3_Vision_Enjeux", ""):
                        st.session_state.entretien_data["V3_Vision_Enjeux"] = v3_vision
                        auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    v3_actions = st.text_area(
                        "Quelles seraient vos premières actions à la prise de poste ?",
                        value=st.session_state.entretien_data.get("V3_Premieres_Actions", ""),
                        key="v3_actions",
                        height=100
                    )
                    if v3_actions != st.session_state.entretien_data.get("V3_Premieres_Actions", ""):
                        st.session_state.entretien_data["V3_Premieres_Actions"] = v3_actions
                        auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    st.markdown("#### 🎯 Évaluation des compétences")
                    
                    # Compétence 1
                    col_comp1_1, col_comp1_2 = st.columns([1, 2])
                    with col_comp1_1:
                        v3_c1_nom = st.text_input(
                            "Compétence 1",
                            value=st.session_state.entretien_data.get("V3_Competence_1_Nom", ""),
                            key="v3_c1_nom"
                        )
                        if v3_c1_nom != st.session_state.entretien_data.get("V3_Competence_1_Nom", ""):
                            st.session_state.entretien_data["V3_Competence_1_Nom"] = v3_c1_nom
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        
                        niveau_options = ["Débutant", "Confirmé", "Expert"]
                        current_niveau = st.session_state.entretien_data.get("V3_Competence_1_Niveau", "Débutant")
                        niveau_index = niveau_options.index(current_niveau) if current_niveau in niveau_options else 0
                        
                        v3_c1_niv = st.selectbox(
                            "Niveau",
                            niveau_options,
                            index=niveau_index,
                            key="v3_c1_niv"
                        )
                        if v3_c1_niv != st.session_state.entretien_data.get("V3_Competence_1_Niveau", ""):
                            st.session_state.entretien_data["V3_Competence_1_Niveau"] = v3_c1_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_comp1_2:
                        v3_c1_just = st.text_area(
                            "Justification et exemples concrets",
                            value=st.session_state.entretien_data.get("V3_Competence_1_Justification", ""),
                            key="v3_c1_just",
                            height=100
                        )
                        if v3_c1_just != st.session_state.entretien_data.get("V3_Competence_1_Justification", ""):
                            st.session_state.entretien_data["V3_Competence_1_Justification"] = v3_c1_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    
                    # Compétence 2
                    col_comp2_1, col_comp2_2 = st.columns([1, 2])
                    with col_comp2_1:
                        v3_c2_nom = st.text_input(
                            "Compétence 2",
                            value=st.session_state.entretien_data.get("V3_Competence_2_Nom", ""),
                            key="v3_c2_nom"
                        )
                        if v3_c2_nom != st.session_state.entretien_data.get("V3_Competence_2_Nom", ""):
                            st.session_state.entretien_data["V3_Competence_2_Nom"] = v3_c2_nom
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        
                        current_niveau = st.session_state.entretien_data.get("V3_Competence_2_Niveau", "Débutant")
                        niveau_index = niveau_options.index(current_niveau) if current_niveau in niveau_options else 0
                        
                        v3_c2_niv = st.selectbox(
                            "Niveau",
                            niveau_options,
                            index=niveau_index,
                            key="v3_c2_niv"
                        )
                        if v3_c2_niv != st.session_state.entretien_data.get("V3_Competence_2_Niveau", ""):
                            st.session_state.entretien_data["V3_Competence_2_Niveau"] = v3_c2_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_comp2_2:
                        v3_c2_just = st.text_area(
                            "Justification et exemples concrets",
                            value=st.session_state.entretien_data.get("V3_Competence_2_Justification", ""),
                            key="v3_c2_just",
                            height=100
                        )
                        if v3_c2_just != st.session_state.entretien_data.get("V3_Competence_2_Justification", ""):
                            st.session_state.entretien_data["V3_Competence_2_Justification"] = v3_c2_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    
                    # Compétence 3
                    col_comp3_1, col_comp3_2 = st.columns([1, 2])
                    with col_comp3_1:
                        v3_c3_nom = st.text_input(
                            "Compétence 3",
                            value=st.session_state.entretien_data.get("V3_Competence_3_Nom", ""),
                            key="v3_c3_nom"
                        )
                        if v3_c3_nom != st.session_state.entretien_data.get("V3_Competence_3_Nom", ""):
                            st.session_state.entretien_data["V3_Competence_3_Nom"] = v3_c3_nom
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        
                        current_niveau = st.session_state.entretien_data.get("V3_Competence_3_Niveau", "Débutant")
                        niveau_index = niveau_options.index(current_niveau) if current_niveau in niveau_options else 0
                        
                        v3_c3_niv = st.selectbox(
                            "Niveau",
                            niveau_options,
                            index=niveau_index,
                            key="v3_c3_niv"
                        )
                        if v3_c3_niv != st.session_state.entretien_data.get("V3_Competence_3_Niveau", ""):
                            st.session_state.entretien_data["V3_Competence_3_Niveau"] = v3_c3_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_comp3_2:
                        v3_c3_just = st.text_area(
                            "Justification et exemples concrets",
                            value=st.session_state.entretien_data.get("V3_Competence_3_Justification", ""),
                            key="v3_c3_just",
                            height=100
                        )
                        if v3_c3_just != st.session_state.entretien_data.get("V3_Competence_3_Justification", ""):
                            st.session_state.entretien_data["V3_Competence_3_Justification"] = v3_c3_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    st.markdown("#### 📊 Expérience")
                    
                    col_exp1, col_exp2 = st.columns([1, 2])
                    with col_exp1:
                        exp_options = ["Débutant (0-3 ans)", "Confirmé (3-7 ans)", "Expert (8+ ans)"]
                        current_exp = st.session_state.entretien_data.get("V3_Experience_Niveau", "Débutant (0-3 ans)")
                        exp_index = exp_options.index(current_exp) if current_exp in exp_options else 0
                        
                        v3_exp_niv = st.selectbox(
                            "Niveau d'expérience dans des contextes comparables",
                            exp_options,
                            index=exp_index,
                            key="v3_exp_niv"
                        )
                        if v3_exp_niv != st.session_state.entretien_data.get("V3_Experience_Niveau", ""):
                            st.session_state.entretien_data["V3_Experience_Niveau"] = v3_exp_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_exp2:
                        v3_exp_just = st.text_area(
                            "Quelle expérience justifie ce niveau ?",
                            value=st.session_state.entretien_data.get("V3_Experience_Justification", ""),
                            key="v3_exp_just",
                            height=100
                        )
                        if v3_exp_just != st.session_state.entretien_data.get("V3_Experience_Justification", ""):
                            st.session_state.entretien_data["V3_Experience_Justification"] = v3_exp_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    st.markdown("#### 🎓 Accompagnement et Formation")
                    
                    col_form1, col_form2 = st.columns([1, 2])
                    with col_form1:
                        accomp_options = ["Non", "Oui"]
                        current_accomp = st.session_state.entretien_data.get("V3_Besoin_Accompagnement", "Non")
                        accomp_index = accomp_options.index(current_accomp) if current_accomp in accomp_options else 0
                        
                        v3_besoin = st.radio(
                            "Besoin d'accompagnement / formation ?",
                            accomp_options,
                            index=accomp_index,
                            key="v3_form_besoin"
                        )
                        if v3_besoin != st.session_state.entretien_data.get("V3_Besoin_Accompagnement", ""):
                            st.session_state.entretien_data["V3_Besoin_Accompagnement"] = v3_besoin
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_form2:
                        if v3_besoin == "Oui":
                            v3_type = st.text_area(
                                "Quels types de soutien ou d'accompagnement ?",
                                value=st.session_state.entretien_data.get("V3_Type_Accompagnement", ""),
                                key="v3_form_type",
                                height=100
                            )
                            if v3_type != st.session_state.entretien_data.get("V3_Type_Accompagnement", ""):
                                st.session_state.entretien_data["V3_Type_Accompagnement"] = v3_type
                                auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        else:
                            if st.session_state.entretien_data.get("V3_Type_Accompagnement", "") != "":
                                st.session_state.entretien_data["V3_Type_Accompagnement"] = ""
                                auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    if st.button("💾 Sauvegarder Vœu 3", key="save_v3"):
                        save_entretien_to_gsheet(gsheet_client, SHEET_URL, st.session_state.entretien_data, show_success=True)
                
                else:
                    st.warning("Aucun vœu 3 renseigné pour ce collaborateur")
            
           # ========== AVIS RH ==========
            with tab_avis:
                st.subheader("💬 Avis RH Final")
                
                # Afficher un indicateur de dernière sauvegarde
                if st.session_state.last_save_time:
                    st.caption(f"💾 Dernière sauvegarde automatique : {st.session_state.last_save_time.strftime('%H:%M:%S')}")
                
                attentes_mgr = st.text_area(
                    "Attentes vis-à-vis du futur manager & dans quels cas le solliciter ?",
                    value=st.session_state.entretien_data.get("Attentes_Manager", ""),
                    key="attentes_manager",
                    height=150
                )
                if attentes_mgr != st.session_state.entretien_data.get("Attentes_Manager", ""):
                    st.session_state.entretien_data["Attentes_Manager"] = attentes_mgr
                    auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                
                avis_synthese = st.text_area(
                    "Avis RH - Synthèse globale de l'entretien",
                    value=st.session_state.entretien_data.get("Avis_RH_Synthese", ""),
                    key="avis_synthese",
                    height=200
                )
                if avis_synthese != st.session_state.entretien_data.get("Avis_RH_Synthese", ""):
                    st.session_state.entretien_data["Avis_RH_Synthese"] = avis_synthese
                    auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                
                st.divider()
                st.markdown("#### 🎯 Décision RH")
                
                # Liste des vœux du collaborateur
                voeux_list = []
                if voeu1_label and voeu1_label != "Positionnement manquant" and voeu1_label != "Non renseigné":
                    voeux_list.append(voeu1_label)
                if voeu2_label and voeu2_label != "Positionnement manquant" and voeu2_label != "Non renseigné":
                    voeux_list.append(voeu2_label)
                if voeu3_label and voeu3_label != "Positionnement manquant" and voeu3_label != "Non renseigné":
                    voeux_list.append(voeu3_label)
                
                voeux_list.append("Autre")
                
                # Index de la décision actuelle
                current_decision = st.session_state.entretien_data.get("Decision_RH_Poste", "")
                if current_decision and current_decision in voeux_list:
                    decision_index = voeux_list.index(current_decision) + 1
                else:
                    decision_index = 0
                
                decision_rh = st.selectbox(
                    "Décision RH",
                    options=["-- Aucune décision --"] + voeux_list,
                    index=decision_index,
                    key="decision_rh"
                )

                # ✅ Variable pour stocker le poste final sélectionné
                poste_final = None
                autre_poste_selectionne = None

                if decision_rh != "-- Aucune décision --":
                    if decision_rh == "Autre":
                        st.markdown("##### 🔍 Rechercher un autre poste")
                        search_poste = st.text_input("Rechercher un poste", key="search_autre_poste")
                        
                        if search_poste:
                            postes_filtres = postes_df[postes_df["Poste"].str.contains(search_poste, case=False, na=False)]
                            
                            if not postes_filtres.empty:
                                autre_poste_selectionne = st.selectbox(
                                    "Sélectionner un poste",
                                    options=["-- Sélectionner --"] + postes_filtres["Poste"].tolist(),
                                    key="select_autre_poste"
                                )
                                
                                if autre_poste_selectionne != "-- Sélectionner --":
                                    poste_final = autre_poste_selectionne
                                    st.session_state.entretien_data["Decision_RH_Poste"] = autre_poste_selectionne
                            else:
                                st.info("Aucun poste trouvé avec ce terme de recherche")
                    else:
                        poste_final = decision_rh
                        st.session_state.entretien_data["Decision_RH_Poste"] = decision_rh
                
                # Si une décision est prise, afficher la confirmation
                if poste_final:
                    st.markdown(f"##### Validez-vous le poste **{poste_final}** pour le collaborateur **{st.session_state.entretien_data.get('Prénom', '')} {st.session_state.entretien_data.get('Nom', '')}** ?")
                    
                    col_btn1, col_btn2, col_btn3 = st.columns(3)
                    
                    with col_btn1:
                        if st.button("❌ Non", key="btn_non", use_container_width=True):
                            st.session_state.entretien_data["Decision_RH_Poste"] = ""
                            st.info("Décision annulée")
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_btn2:
                        if st.button("🟠 Oui en option RH", key="btn_option", type="secondary", use_container_width=True):
                            # Ajouter dans "Commentaires RH" - utiliser poste_final au lieu de decision_rh
                            commentaire = f"Option RH à l'issue entretien : {poste_final}"
                            success = update_commentaire_rh(gsheet_client, SHEET_URL, st.session_state.current_matricule, commentaire)
                            
                            if success:
                                # Sauvegarder la décision dans l'entretien
                                st.session_state.entretien_data["Decision_RH_Poste"] = f"Option: {poste_final}"
                                save_entretien_to_gsheet(gsheet_client, SHEET_URL, st.session_state.entretien_data, show_success=False)
                                
                                st.success("✅ Option RH enregistrée avec succès !")
                                time.sleep(2)
                                st.rerun()
                    
                    with col_btn3:
                        if st.button("🟢 Oui, vœu retenu", key="btn_retenu", type="primary", use_container_width=True):
                            # Mettre à jour "Vœux Retenu" - utiliser poste_final au lieu de decision_rh
                            success = update_voeu_retenu(gsheet_client, SHEET_URL, st.session_state.current_matricule, poste_final)
                            
                            if success:
                                # Sauvegarder la décision dans l'entretien
                                st.session_state.entretien_data["Decision_RH_Poste"] = f"Retenu: {poste_final}"
                                save_entretien_to_gsheet(gsheet_client, SHEET_URL, st.session_state.entretien_data, show_success=False)
                                
                                st.success("✅ Vœu retenu enregistré avec succès !")
                                time.sleep(2)
                                st.rerun()
                
                # Bouton de sauvegarde final
                st.divider()
                if st.button("💾 Sauvegarder l'entretien complet", type="primary", use_container_width=True):
                    save_entretien_to_gsheet(gsheet_client, SHEET_URL, st.session_state.entretien_data, show_success=True)

# ========================================
# PAGE 4 : ANALYSE PAR POSTE
# ========================================

elif page == "🎯 Analyse par Poste":
    st.title("🎯 Analyse des Viviers par Poste")
    
    # Liste des postes ouverts à la mobilité avec leur nombre total
    postes_ouverts_df = postes_df[postes_df["Mobilité interne"].str.lower() == "oui"].copy()
    
    # Analyse par poste
    job_analysis = []
    
    for _, poste_row in postes_ouverts_df.iterrows():
        poste = poste_row["Poste"]
        nb_postes_total = int(poste_row.get("Nombre total de postes", 1))
        
        # Compter les postes attribués
        nb_postes_attribues = len(collaborateurs_df[
            (collaborateurs_df["Vœux Retenu"] == poste)
        ])
        
        # Calculer les postes disponibles
        nb_postes_disponibles = nb_postes_total - nb_postes_attribues
        
        candidats = []
        candidats_data = []
        
        for _, collab in collaborateurs_df.iterrows():
            if collab.get("Vœux 1") == poste:
                candidats.append(f"{get_safe_value(collab.get('NOM', ''))} {get_safe_value(collab.get('Prénom', ''))} (V1)")
                candidats_data.append({
                    "nom": f"{get_safe_value(collab.get('NOM', ''))} {get_safe_value(collab.get('Prénom', ''))}",
                    "matricule": get_safe_value(collab.get('Matricule', ''))
                })
            elif collab.get("Vœux 2") == poste:
                candidats.append(f"{get_safe_value(collab.get('NOM', ''))} {get_safe_value(collab.get('Prénom', ''))} (V2)")
                candidats_data.append({
                    "nom": f"{get_safe_value(collab.get('NOM', ''))} {get_safe_value(collab.get('Prénom', ''))}",
                    "matricule": get_safe_value(collab.get('Matricule', ''))
                })
            elif collab.get("Voeux 3") == poste:
                candidats.append(f"{get_safe_value(collab.get('NOM', ''))} {get_safe_value(collab.get('Prénom', ''))} (V3)")
                candidats_data.append({
                    "nom": f"{get_safe_value(collab.get('NOM', ''))} {get_safe_value(collab.get('Prénom', ''))}",
                    "matricule": get_safe_value(collab.get('Matricule', ''))
                })
        
        nb_candidats = len(candidats)
        
        # Déterminer le statut
        if nb_postes_disponibles == 0:
            statut = "✅ Poste(s) pourvu(s)"
        elif nb_candidats == 0:
            statut = "⚠️ Aucun candidat"
        elif nb_candidats < nb_postes_disponibles:
            statut = f"⚠️ Manque {nb_postes_disponibles - nb_candidats} candidat(s)"
        elif nb_candidats == nb_postes_disponibles:
            statut = "✅ Vivier actif"
        else:
            # Calcul du ratio de tension
            ratio = nb_candidats / nb_postes_disponibles if nb_postes_disponibles > 0 else nb_candidats
            if ratio <= 2:
                statut = "🔶 Tension"
            elif ratio <= 3:
                statut = "🔴 Forte tension"
            else:
                statut = "🔴🔴 Très forte tension"
        
        job_analysis.append({
            "Poste": poste,
            "Direction": poste_row.get("Direction", "N/A"),
            "Postes disponibles": nb_postes_disponibles,
            "Postes attribués": nb_postes_attribues,
            "Nb_Candidats": nb_candidats,
            "Candidats": ", ".join(candidats) if candidats else "",
            "Candidats_Data": candidats_data,
            "Statut": statut
        })
    
    df_analysis = pd.DataFrame(job_analysis)
    
    # Filtres
    col_filter1, col_filter2, col_filter3 = st.columns(3)
    
    with col_filter1:
        show_zero = st.checkbox("⚠️ Afficher uniquement les postes sans candidat")
    
    with col_filter2:
        filtre_direction_analyse = st.multiselect(
            "Filtrer par Direction",
            options=sorted(df_analysis["Direction"].unique()),
            default=[]
        )
    
    with col_filter3:
        statuts_possibles = [
            "⚠️ Aucun candidat",
            "⚠️ Manque",
            "✅ Vivier actif",
            "🔶 Tension",
            "🔴 Forte tension",
            "🔴🔴 Très forte tension",
            "✅ Poste(s) pourvu(s)"
        ]
        filtre_statut = st.multiselect(
            "Filtrer par Statut",
            options=statuts_possibles,
            default=[]
        )
    
    # Appliquer les filtres
    df_filtered_analysis = df_analysis.copy()
    
    if show_zero:
        df_filtered_analysis = df_filtered_analysis[df_filtered_analysis["Nb_Candidats"] == 0]
    
    if filtre_direction_analyse:
        df_filtered_analysis = df_filtered_analysis[df_filtered_analysis["Direction"].isin(filtre_direction_analyse)]
    
    if filtre_statut:
        def match_statut(statut_row):
            for filtre in filtre_statut:
                if filtre == "⚠️ Manque":
                    if statut_row.startswith("⚠️ Manque"):
                        return True
                elif statut_row == filtre:
                    return True
            return False
        
        df_filtered_analysis = df_filtered_analysis[df_filtered_analysis["Statut"].apply(match_statut)]
    
    # Affichage
    if not df_filtered_analysis.empty:
        st.dataframe(
            df_filtered_analysis.drop(columns=["Candidats_Data"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Nb_Candidats": st.column_config.NumberColumn(
                    "Nombre de candidats",
                    format="%d"
                ),
                "Postes disponibles": st.column_config.NumberColumn(
                    "Postes disponibles",
                    format="%d"
                ),
                "Postes attribués": st.column_config.NumberColumn(
                    "Postes attribués",
                    format="%d"
                )
            }
        )
        
        st.divider()
        
        # Section pour accéder aux fiches détaillées
        st.subheader("🔍 Accès aux fiches candidats")
        
        postes_tries = sorted(df_filtered_analysis["Poste"].tolist())
        poste_selected = st.selectbox(
            "Sélectionner un poste pour voir ses candidats",
            options=["-- Sélectionner --"] + postes_tries
        )
        
        if poste_selected != "-- Sélectionner --":
            candidats_du_poste = df_filtered_analysis[df_filtered_analysis["Poste"] == poste_selected]["Candidats_Data"].iloc[0]
            
            if len(candidats_du_poste) > 0:
                col_cand1, col_cand2 = st.columns([3, 1])
                
                with col_cand1:
                    candidat_selected = st.selectbox(
                        "Sélectionner un candidat",
                        options=["-- Sélectionner --"] + [c["nom"] for c in candidats_du_poste]
                    )
                
                with col_cand2:
                    if st.button("➡️ Voir la fiche", type="primary", disabled=(candidat_selected == "-- Sélectionner --")):
                        st.session_state['show_fiche_detail'] = True
                        st.session_state['fiche_candidat'] = candidat_selected
                
                # Afficher la fiche détaillée si demandé
                if st.session_state.get('show_fiche_detail') and st.session_state.get('fiche_candidat') == candidat_selected:
                    st.divider()
                    st.subheader(f"📋 Fiche détaillée : {candidat_selected}")
                    
                    collab_mask = (collaborateurs_df["NOM"] + " " + collaborateurs_df["Prénom"]) == candidat_selected
                    if collab_mask.any():
                        collab = collaborateurs_df[collab_mask].iloc[0]
                        
                        with st.container(border=True):
                            col_info1, col_info2, col_info3 = st.columns(3)
                            
                            with col_info1:
                                matricule = get_safe_value(collab.get('Matricule', ''))
                                nom = get_safe_value(collab.get('NOM', ''))
                                prenom = get_safe_value(collab.get('Prénom', ''))
                                mail = get_safe_value(collab.get('Mail', ''))
                                
                                st.markdown(f"**Matricule** : {matricule if matricule else 'N/A'}")
                                st.markdown(f"**Nom** : {nom} {prenom}")
                                st.markdown(f"**Mail** : {mail if mail else 'N/A'}")
                            
                            with col_info2:
                                poste_actuel = get_safe_value(collab.get('Poste  libellé', ''))
                                direction = get_safe_value(collab.get('Direction libellé', ''))
                                date_entree = get_safe_value(collab.get("Date entrée groupe", ""))
                                anciennete_display = calculate_anciennete(date_entree)
                                
                                st.markdown(f"**Poste actuel** : {poste_actuel if poste_actuel else 'N/A'}")
                                st.markdown(f"**Direction** : {direction if direction else 'N/A'}")
                                st.markdown(f"**Ancienneté** : {anciennete_display}")
                            
                            with col_info3:
                                rrh = get_safe_value(collab.get('Référente RH', ''))
                                date_rdv = get_safe_value(collab.get('Date de rdv', ''))
                                priorite = get_safe_value(collab.get('Priorité', ''))
                                
                                st.markdown(f"**RRH** : {rrh if rrh else 'N/A'}")
                                st.markdown(f"**Date RDV** : {date_rdv if date_rdv else 'N/A'}")
                                st.markdown(f"**Priorité** : {priorite if priorite else 'N/A'}")
                        
                        if st.button("➡️ Accéder à l'entretien RH complet", type="secondary"):
                            st.session_state['selected_collaborateur'] = candidat_selected
                            st.session_state['navigate_to_entretien'] = True
                            st.rerun()
            else:
                st.info("Aucun candidat pour ce poste")
    else:
        st.info("Aucun poste ne correspond aux filtres sélectionnés")

# ========================================
# PAGE 5 : RÉFÉRENTIEL POSTES
# ========================================

elif page == "🌳 Référentiel Postes":
    st.title("🌳 Référentiel des Postes")
    
    # Filtres
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        search = st.text_input("🔍 Rechercher un poste")
    
    with col_f2:
        filtre_direction_ref = st.selectbox(
            "Filtrer par Direction",
            options=["Toutes"] + sorted(postes_df["Direction"].unique())
        )
    
    with col_f3:
        filtre_mobilite = st.selectbox(
            "Filtre mobilité",
            ["Tous", "Oui", "Non"]
        )
    
    # Appliquer filtres
    df_postes = postes_df.copy()
    
    if search:
        df_postes = df_postes[df_postes["Poste"].str.contains(search, case=False, na=False)]
    
    if filtre_direction_ref != "Toutes":
        df_postes = df_postes[df_postes["Direction"] == filtre_direction_ref]
    
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
<div style='text-align: center; color: #999; font-size: 0.9em;'>
    <p>CAP25 - Pilotage de la Mobilité Interne | Synchronisé avec Google Sheets</p>
</div>
""", unsafe_allow_html=True)




