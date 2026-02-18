import streamlit as st
import pandas as pd
from datetime import datetime, date
import time
from google.oauth2 import service_account
import gspread
import pytz
import json
import altair as alt
import io
import plotly.graph_objects as go
import plotly.express as px
from collections import defaultdict


# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="CAP25 - Pilotage Mobilité v.05/02/26",  # ← Changer la version
    layout="wide", 
    page_icon="🏢",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
html, body, [class*="css"]  {
    font-family: 'Inter', sans-serif;
    background-color: #F8FAFC;
    color: #1F2937;
}

h1, h2, h3 {
    font-weight: 600;
    color: #0F2A44;
}

section[data-testid="stMetric"] {
    background: white;
    padding: 16px;
    border-radius: 12px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.stDataFrame {
    border-radius: 12px;
    overflow: hidden;
}

div[data-testid="stHorizontalBlock"] {
    gap: 1.2rem;
}
</style>
""", unsafe_allow_html=True)


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
    
    # NOUVEAU : Pour forcer le rechargement de l'entretien
    if 'force_reload_entretien' not in st.session_state:
        st.session_state.force_reload_entretien = False

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

def api_call_with_retry(func, max_retries=5, initial_delay=1):
    """
    Exécute un appel API avec retry et backoff exponentiel
    pour gérer les limites de quota Google Sheets
    """
    import time
    import random
    
    for attempt in range(max_retries):
        try:
            return func()
        except gspread.exceptions.APIError as e:
            if e.response.status_code == 429:
                if attempt < max_retries - 1:
                    delay = initial_delay * (2 ** attempt) + random.uniform(0, 1)
                    st.warning(f"⏳ Limite de quota API atteinte. Nouvelle tentative dans {delay:.1f}s...")
                    time.sleep(delay)
                    continue
                else:
                    st.error("❌ Impossible de charger les données après plusieurs tentatives. Veuillez réessayer dans quelques minutes.")
                    raise
            else:
                raise
        except Exception as e:
            raise
    
    return None

@st.cache_data(ttl=60)
def load_data_from_gsheet(_client, sheet_url):
    """
    Charge les données depuis Google Sheets avec gestion du quota.
    Onglets : CAP 2025 (collaborateurs) et Postes (référentiel)
    """
    try:
        spreadsheet = api_call_with_retry(lambda: _client.open_by_url(sheet_url))
    except Exception as e:
        st.error(f"Impossible d'ouvrir le Google Sheet : {str(e)}")
        return pd.DataFrame(), pd.DataFrame()
    
    # Charger l'onglet "CAP 2025" (collaborateurs)
    try:
        cap_sheet = api_call_with_retry(lambda: spreadsheet.worksheet("CAP 2025"))
        all_values = api_call_with_retry(lambda: cap_sheet.get_all_values())
        
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
        postes_sheet = api_call_with_retry(lambda: spreadsheet.worksheet("Postes"))
        postes_data = api_call_with_retry(lambda: postes_sheet.get_all_records())
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
    Charge un entretien existant depuis Google Sheets avec gestion du quota
    """
    try:
        spreadsheet = api_call_with_retry(lambda: _client.open_by_url(sheet_url))
        worksheet = api_call_with_retry(lambda: spreadsheet.worksheet("Entretien RH"))
        
        all_records = api_call_with_retry(lambda: worksheet.get_all_records())
        
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
            worksheet = spreadsheet.add_worksheet(title="Entretien RH", rows="1000", cols="76")  # ← MODIFIÉ : 59 → 76 colonnes
            
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
                "Attentes_Manager", "Avis_RH_Synthese", "Decision_RH_Poste",
                # ✅ NOUVEAU : Vœu 4
                "Voeu_4", "V4_Motivations", "V4_Vision_Enjeux", "V4_Premieres_Actions",
                "V4_Competence_1_Nom", "V4_Competence_1_Niveau", "V4_Competence_1_Justification",
                "V4_Competence_2_Nom", "V4_Competence_2_Niveau", "V4_Competence_2_Justification",
                "V4_Competence_3_Nom", "V4_Competence_3_Niveau", "V4_Competence_3_Justification",
                "V4_Experience_Niveau", "V4_Experience_Justification",
                "V4_Besoin_Accompagnement", "V4_Type_Accompagnement"
            ]
            
            worksheet.update('A1:BX1', [headers])  # ← MODIFIÉ : BG1 → BX1
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
                entretien_data.get("Decision_RH_Poste", ""),
                # ✅ NOUVEAU : Vœu 4
                entretien_data.get("Voeu_4", ""),
                entretien_data.get("V4_Motivations", ""),
                entretien_data.get("V4_Vision_Enjeux", ""),
                entretien_data.get("V4_Premieres_Actions", ""),
                entretien_data.get("V4_Competence_1_Nom", ""),
                entretien_data.get("V4_Competence_1_Niveau", ""),
                entretien_data.get("V4_Competence_1_Justification", ""),
                entretien_data.get("V4_Competence_2_Nom", ""),
                entretien_data.get("V4_Competence_2_Niveau", ""),
                entretien_data.get("V4_Competence_2_Justification", ""),
                entretien_data.get("V4_Competence_3_Nom", ""),
                entretien_data.get("V4_Competence_3_Niveau", ""),
                entretien_data.get("V4_Competence_3_Justification", ""),
                entretien_data.get("V4_Experience_Niveau", ""),
                entretien_data.get("V4_Experience_Justification", ""),
                entretien_data.get("V4_Besoin_Accompagnement", ""),
                entretien_data.get("V4_Type_Accompagnement", "")
            ]
            
            if existing_row:
                worksheet.update(f'A{existing_row}:BX{existing_row}', [row_data])  # ← MODIFIÉ : BG → BX
            else:
                worksheet.append_row(row_data)
            
            paris_tz = pytz.timezone('Europe/Paris')
            st.session_state.last_save_time = datetime.now(paris_tz)
            
            if show_success:
                st.success(f"✅ Sauvegarde effectuée à {st.session_state.last_save_time.strftime('%H:%M:%S')}")
            
            return True
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
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
        
        try:
            voeu_retenu_col = headers.index("Vœux Retenu") + 1
            matricule_col = headers.index("Matricule") + 1
        except ValueError:
            st.error("Colonnes 'Vœux Retenu' ou 'Matricule' introuvables")
            return False
        
        for idx, row in enumerate(all_values[2:], start=3):
            if row[matricule_col - 1] == str(matricule):
                worksheet.update_cell(idx, voeu_retenu_col, poste)
                st.cache_data.clear()
                return True
        
        st.error("Matricule introuvable")
        return False
        
    except Exception as e:
        st.error(f"Erreur lors de la mise à jour : {str(e)}")
        return False

# NOUVELLE FONCTION : Mise à jour du Vœu 4
def update_voeu_4(_client, sheet_url, matricule, poste):
    """
    Met à jour la colonne 'Voeux 4' dans l'onglet CAP 2025
    """
    try:
        spreadsheet = _client.open_by_url(sheet_url)
        worksheet = spreadsheet.worksheet("CAP 2025")
        
        all_values = worksheet.get_all_values()
        headers = all_values[1]
        
        # Vérifier si la colonne Voeux 4 existe, sinon la créer
        if "Voeux 4" not in headers:
            # Ajouter la colonne en fin de ligne d'en-têtes
            voeux_4_col = len(headers) + 1
            worksheet.update_cell(2, voeux_4_col, "Voeux 4")
        else:
            voeux_4_col = headers.index("Voeux 4") + 1
        
        try:
            matricule_col = headers.index("Matricule") + 1
        except ValueError:
            st.error("Colonne 'Matricule' introuvable")
            return False
        
        for idx, row in enumerate(all_values[2:], start=3):
            if row[matricule_col - 1] == str(matricule):
                worksheet.update_cell(idx, voeux_4_col, poste)
                st.cache_data.clear()
                return True
        
        st.error("Matricule introuvable")
        return False
        
    except Exception as e:
        st.error(f"Erreur lors de la mise à jour du Vœu 4 : {str(e)}")
        return False

# NOUVELLE FONCTION : Réorganiser les vœux
def update_voeux_order(_client, sheet_url, matricule, voeu1, voeu2, voeu3):
    """
    Met à jour l'ordre des vœux dans l'onglet CAP 2025
    """
    try:
        spreadsheet = _client.open_by_url(sheet_url)
        worksheet = spreadsheet.worksheet("CAP 2025")
        
        all_values = worksheet.get_all_values()
        headers = all_values[1]
        
        try:
            voeu1_col = headers.index("Vœux 1") + 1
            voeu2_col = headers.index("Vœux 2") + 1
            voeu3_col = headers.index("Voeux 3") + 1
            matricule_col = headers.index("Matricule") + 1
        except ValueError as e:
            st.error(f"Colonnes de vœux introuvables : {str(e)}")
            return False
        
        for idx, row in enumerate(all_values[2:], start=3):
            if row[matricule_col - 1] == str(matricule):
                worksheet.update_cell(idx, voeu1_col, voeu1)
                worksheet.update_cell(idx, voeu2_col, voeu2)
                worksheet.update_cell(idx, voeu3_col, voeu3)
                st.cache_data.clear()
                return True
        
        st.error("Matricule introuvable")
        return False
        
    except Exception as e:
        st.error(f"Erreur lors de la réorganisation des vœux : {str(e)}")
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
        
        try:
            commentaire_col = headers.index("Commentaires RH") + 1
            matricule_col = headers.index("Matricule") + 1
        except ValueError:
            st.error("Colonnes 'Commentaires RH' ou 'Matricule' introuvables")
            return False
        
        for idx, row in enumerate(all_values[2:], start=3):
            if row[matricule_col - 1] == str(matricule):
                existing_comment = row[commentaire_col - 1]
                new_comment = f"{existing_comment}\n{commentaire}" if existing_comment else commentaire
                worksheet.update_cell(idx, commentaire_col, new_comment)
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

def to_excel(df):
    """Convertit un DataFrame en fichier Excel en mémoire avec formatage"""
    output = io.BytesIO()
    
    # ✅ CORRECTION : Utiliser openpyxl au lieu de xlsxwriter
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Données')
        
        # Accéder au workbook et à la feuille
        workbook = writer.book
        worksheet = writer.sheets['Données']
        
        # Formatage des en-têtes
        from openpyxl.styles import Font, PatternFill, Alignment
        
        header_fill = PatternFill(start_color="008080", end_color="008080", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # Auto-ajuster la largeur des colonnes
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    return output.getvalue()

def get_voeux_alternatifs(df_collabs, matricule, voeu_bloque):
    collab = df_collabs[df_collabs['Matricule'] == matricule]
    if collab.empty:
        return ""
    
    collab = collab.iloc[0]
    
    voeux = []
    
    if voeu_bloque != "Vœu 1":
        v1 = get_safe_value(collab.get('Vœux 1', ''))
        if v1 and v1 != 'Positionnement manquant':
            voeux.append(f"V1: {v1}")
    
    if voeu_bloque != "Vœu 2":
        v2 = get_safe_value(collab.get('Vœux 2', ''))
        if v2 and v2 != 'Positionnement manquant':
            voeux.append(f"V2: {v2}")
    
    if voeu_bloque != "Vœu 3":
        v3 = get_safe_value(collab.get('Voeux 3', ''))
        if v3 and v3 != 'Positionnement manquant':
            voeux.append(f"V3: {v3}")
    
    if voeu_bloque != "Vœu 4":
        v4 = get_safe_value(collab.get('Voeux 4', ''))
        if v4 and v4 != 'Positionnement manquant':
            voeux.append(f"V4: {v4}")
    
    return " | ".join(voeux) if voeux else "Aucun vœu alternatif"

 # ========================================
# FONCTIONS UTILITAIRES & CACHE
# ========================================

@st.cache_data(ttl=600) # Cache les données pour 10 minutes ou jusqu'au reboot
def prepare_aggregated_data(df_postes, df_collabs):
    """
    Traitement vectorisé optimisé pour la performance.
    Remplace les boucles for imbriquées par des opérations Pandas natives.
    """
    # 1. NETTOYAGE DES POSTES (Le filtre critique demandé)
    # On normalise la colonne des vacances
    col_vacants = "Nombre de postes vacants " # Attention à l'espace final dans votre source
    
    # Conversion en numérique, les erreurs deviennent NaN
    df_postes["_vacants_clean"] = pd.to_numeric(df_postes[col_vacants], errors='coerce')
    
    # FILTRE STRICT : On ne garde que les postes avec > 0 vacance définie
    df_p_clean = df_postes[df_postes["_vacants_clean"] > 0].copy()
    
    if df_p_clean.empty:
        return pd.DataFrame()

    # 2. PRÉPARATION DES COLLABORATEURS (Format "Long")
    # On transforme les colonnes Vœux 1, 2, 3, 4 en lignes pour pouvoir grouper
    # On normalise les noms de colonnes (parfois "Vœux", parfois "Voeux")
    cols_to_map = {
        "Vœux 1": "1", "Vœux 2": "2", "Voeux 3": "3", "Voeux 4": "4"
    }
    
    # On s'assure que les colonnes existent
    existing_cols = [c for c in cols_to_map.keys() if c in df_collabs.columns]
    
    # On crée une vue simplifiée : [Poste Actuel, Vœu, Rang]
    df_melted = df_collabs.melt(
        id_vars=['Poste libellé'], # Votre colonne poste actuel
        value_vars=existing_cols,
        var_name="Source_Voeu",
        value_name="Poste_Vise"
    )
    
    # Nettoyage des vœux vides
    df_melted = df_melted[df_melted["Poste_Vise"].notna() & (df_melted["Poste_Vise"] != "")]
    df_melted["Rang"] = df_melted["Source_Voeu"].map(cols_to_map).astype(int)

    # 3. AGGRÉGATION (Comptage et Profils)
    # Compte total par poste visé
    counts = df_melted.groupby("Poste_Vise").size().reset_index(name="CANDIDATURES TOTAL")
    
    # Compte par rang (Vœu 1, Vœu 2...)
    pivot_ranks = df_melted.pivot_table(
        index="Poste_Vise", 
        columns="Rang", 
        aggfunc='size', 
        fill_value=0
    ).add_prefix("Vœu ")
    
    # Agrégation des profils métiers (concaténation de texte optimisée)
    # Ex: On veut savoir d'où viennent les gens pour le Vœu 1
    v1_only = df_melted[df_melted["Rang"] == 1]
    
    def get_profiles_summary(sub_df):
        if sub_df.empty: return ""
        counts = sub_df['Poste libellé'].value_counts()
        return "; ".join([f"{metier} ({nb})" for metier, nb in counts.items()])

    # On applique cela pour chaque poste visé (uniquement sur le Vœu 1 pour alléger, ou tout)
    profiles_summary = v1_only.groupby("Poste_Vise").apply(get_profiles_summary).reset_index(name="PROFILS (V1)")

    # 4. FUSION FINALE
    # On part des postes ouverts (Master Data)
    df_final = df_p_clean.merge(counts, left_on="Poste", right_on="Poste_Vise", how="left")
    df_final = df_final.merge(pivot_ranks, left_on="Poste", right_index=True, how="left")
    df_final = df_final.merge(profiles_summary, left_on="Poste", right_on="Poste_Vise", how="left")
    
    # Remplir les NaN par 0 pour les chiffres
    numeric_cols = ["CANDIDATURES TOTAL"] + [c for c in df_final.columns if c.startswith("Vœu ")]
    df_final[numeric_cols] = df_final[numeric_cols].fillna(0)
    
    # Calcul de la tension (Candidats / Postes)
    df_final["Tension"] = df_final["CANDIDATURES TOTAL"] / df_final["_vacants_clean"]
    
    # Sélection et renommage propre pour l'affichage
    display_cols = {
        "Poste": "POSTE PROJETE",
        "Direction": "DIRECTION",
        "_vacants_clean": "POSTES OUVERTS",
        "CANDIDATURES TOTAL": "TOTAL CANDIDATS",
        "Tension": "TENSION",
        "PROFILS (V1)": "ORIGINE CANDIDATS (V1)"
    }
    # Ajouter les colonnes de voeux dynamiquement
    for col in df_final.columns:
        if col.startswith("Vœu "):
            display_cols[col] = col.upper()

    df_final = df_final.rename(columns=display_cols)
    
    # On garde les colonnes pertinentes
    final_columns = list(display_cols.values())
    return df_final[final_columns]           

def badge_priorite(p):
    colors = {
        "Priorité 1": "🔴",
        "Priorité 2": "🟠",
        "Priorité 3": "🟡",
        "Priorité 4": "🟢"
    }
    return f"{colors.get(p, '⚪')} {p}"

# ========================================
# FONCTIONS POUR L'ORGANIGRAMME
# ========================================

def create_org_structure(df, postes_df, mode="actuel"):
    """
    Crée une structure hiérarchique de l'organisation
    mode: "actuel" ou "cap2025"
    """
    org_structure = defaultdict(lambda: defaultdict(list))
    
    if mode == "actuel":
        # Organisation actuelle basée sur "Direction libellé" et "Emploi libellé"
        for _, row in df.iterrows():
            direction = get_safe_value(row.get('Direction libellé', '')), 'Non renseigné'
            service = get_safe_value(row.get('Service libellé', '')), 'Non renseigné'
            poste = get_safe_value(row.get('Poste libellé', '')), 'Non renseigné'
            nom = f"{get_safe_value(row.get('NOM', ''))} {get_safe_value(row.get('Prénom', ''))}"
            
            org_structure[direction][service].append({
                'nom': nom,
                'poste': poste,
                'matricule': get_safe_value(row.get('Matricule', ''))
            })
    else:  # CAP 2025
        # Filtrer uniquement les collaborateurs avec "Vœux Retenu" non vide
        df_with_voeu = df[df['Vœux Retenu'].notna() & (df['Vœux Retenu'] != '')].copy()
        
        # Créer un dictionnaire de mapping Poste → Direction depuis l'onglet Postes
        poste_to_direction = {}
        if not postes_df.empty:
            for _, poste_row in postes_df.iterrows():
                poste_name = get_safe_value(poste_row.get('Poste', ''))
                direction_name = get_safe_value(poste_row.get('Direction', ''))
                if poste_name:
                    poste_to_direction[poste_name] = direction_name
        
        # Construire l'organigramme CAP 2025
        for _, row in df_with_voeu.iterrows():
            voeu_retenu = get_safe_value(row.get('Vœux Retenu', ''))
            
            if voeu_retenu:
                # Trouver la direction correspondante dans le référentiel Postes
                direction = poste_to_direction.get(voeu_retenu, 'Direction non trouvée')
                
                # Pour le service, on peut soit :
                # 1. Utiliser le service actuel (si maintien)
                # 2. Utiliser "Service" de l'onglet Postes si disponible
                # 3. Mettre "À définir"
                service = get_safe_value(row.get('Service libellé', '')), 'À définir'
                
                poste = voeu_retenu
                nom = f"{get_safe_value(row.get('NOM', ''))} {get_safe_value(row.get('Prénom', ''))}"
                
                org_structure[direction][service].append({
                    'nom': nom,
                    'poste': poste,
                    'matricule': get_safe_value(row.get('Matricule', ''))
                })
    
    return org_structure

def create_sankey_diagram(df, postes_df):
    """Crée un diagramme Sankey pour visualiser les flux de mobilité"""
    
    # Créer le mapping Poste → Direction depuis l'onglet Postes
    poste_to_direction = {}
    if not postes_df.empty:
        for _, poste_row in postes_df.iterrows():
            poste_name = get_safe_value(poste_row.get('Poste', ''))
            direction_name = get_safe_value(poste_row.get('Direction', ''))
            if poste_name:
                poste_to_direction[poste_name] = direction_name
    
    # Filtrer uniquement les collaborateurs avec "Vœux Retenu"
    df_with_voeu = df[df['Vœux Retenu'].notna() & (df['Vœux Retenu'] != '')].copy()
    
    # Préparer les données pour Sankey
    sources = []
    targets = []
    values = []
    labels = set()
    
    for _, row in df_with_voeu.iterrows():
        poste_actuel = get_safe_value(row.get('Poste libellé', '')), 'Non renseigné'
        voeu_retenu = get_safe_value(row.get('Vœux Retenu', ''))
        
        if voeu_retenu:
            labels.add(f"ACTUEL: {poste_actuel}")
            labels.add(f"CAP25: {voeu_retenu}")
    
    labels_list = sorted(list(labels))
    label_to_idx = {label: idx for idx, label in enumerate(labels_list)}
    
    # Créer les flux
    flux_count = defaultdict(int)
    
    for _, row in df_with_voeu.iterrows():
        poste_actuel = get_safe_value(row.get('Poste libellé', '')), 'Non renseigné'
        voeu_retenu = get_safe_value(row.get('Vœux Retenu', ''))
        
        if voeu_retenu:
            source_label = f"ACTUEL: {poste_actuel}"
            target_label = f"CAP25: {voeu_retenu}"
            
            flux_count[(source_label, target_label)] += 1
    
    # Convertir en listes pour Plotly
    for (source_label, target_label), count in flux_count.items():
        sources.append(label_to_idx[source_label])
        targets.append(label_to_idx[target_label])
        values.append(count)
    
    # Créer le diagramme Sankey
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=labels_list,
            color=["#3B82F6" if "ACTUEL" in l else "#10B981" for l in labels_list]
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color="rgba(100, 116, 139, 0.3)"
        )
    )])
    
    fig.update_layout(
        title="Flux de mobilité : Organisation actuelle → CAP 2025",
        font=dict(size=10),
        height=800
    )
    
    return fig

def create_treemap(org_structure, title):
    """Crée un treemap de l'organisation"""
    
    # Préparer les données pour le treemap
    labels = []
    parents = []
    values = []
    colors = []
    
    # Palette de couleurs par direction
    color_palette = px.colors.qualitative.Set3
    direction_colors = {}
    
    for idx, direction in enumerate(org_structure.keys()):
        direction_colors[direction] = color_palette[idx % len(color_palette)]
        
        # Ajouter la direction
        labels.append(direction)
        parents.append("")
        values.append(0)  # Sera recalculé
        colors.append(direction_colors[direction])
        
        for service, collaborateurs in org_structure[direction].items():
            # Ajouter le service
            service_label = f"{direction}/{service}"
            labels.append(service_label)
            parents.append(direction)
            values.append(len(collaborateurs))
            colors.append(direction_colors[direction])
    
    # Recalculer les valeurs des directions
    for i, label in enumerate(labels):
        if parents[i] == "":
            values[i] = sum(v for j, v in enumerate(values) if parents[j] == label)
    
    fig = go.Figure(go.Treemap(
        labels=labels,
        parents=parents,
        values=values,
        marker=dict(colors=colors),
        textposition="middle center",
        textfont=dict(size=12)
    ))
    
    fig.update_layout(
        title=title,
        height=600,
        margin=dict(t=50, l=0, r=0, b=0)
    )
    
    return fig

def get_poste_capacity(postes_df, poste_name):
    """Retourne la capacité d'un poste depuis le référentiel"""
    if postes_df.empty:
        return None
    
    matching_rows = postes_df[postes_df['Poste'] == poste_name]
    if not matching_rows.empty:
        capacity = matching_rows.iloc[0].get('Nombre total de postes', None)
        try:
            return int(capacity) if capacity else None
        except:
            return None
    return None


# --- URL DU GOOGLE SHEET ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1BXez24VFNhb470PrCjwNIFx6GdJFqLnVh8nFf3gGGvw/edit?usp=sharing"

# --- INITIALISATION ---
init_session_state()

try:
    gsheet_client = get_gsheet_connection()
    if gsheet_client:
        create_entretien_sheet_if_not_exists(gsheet_client, SHEET_URL)
    else:
        st.sidebar.error("❌ Erreur de connexion")
        st.stop()
except Exception as e:
    st.sidebar.error(f"❌ Erreur : {str(e)}")
    st.stop()

# --- CHARGEMENT DES DONNÉES (AVANT LA SIDEBAR) ---
with st.spinner("Chargement des données..."):
    collaborateurs_df, postes_df = load_data_from_gsheet(gsheet_client, SHEET_URL)

# ✅ VÉRIFICATION ET CRÉATION DE LA COLONNE "Vœux Retenu" SI MANQUANTE
if not collaborateurs_df.empty:
    # Nettoyer les noms de colonnes : strip + normaliser les espaces multiples
    collaborateurs_df.columns = collaborateurs_df.columns.str.strip()
    
    # DEBUG : Afficher les colonnes chargées
    #st.sidebar.write("🔍 DEBUG - Colonnes disponibles:", list(collaborateurs_df.columns[:20]))  # Afficher les 10 premières
    
    if "Vœux Retenu" not in collaborateurs_df.columns:
        collaborateurs_df["Vœux Retenu"] = ""

if collaborateurs_df.empty or postes_df.empty:
    st.error("Impossible de charger les données. Vérifiez la structure du Google Sheet.")
    st.stop()

# --- CSS POUR SIDEBAR ULTRA-COMPACTE ---
st.sidebar.markdown("""
    <style>
        /* Supprime TOUT le padding en haut */
        [data-testid="stSidebarUserContent"] {
            padding-top: 0rem !important;
        }
        [data-testid="stSidebarNav"] {
            padding-top: 0px !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- BANDEAU CONNEXION EN HAUT (FOND VERT) ---
st.sidebar.markdown("""
<div style='background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
            padding: 8px 12px; 
            border-radius: 0px; 
            margin: 0; 
            margin-bottom: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
    <p style='color: white; 
              font-size: 0.85em; 
              font-weight: 600; 
              margin: 0; 
              text-align: center;
              letter-spacing: 0.5px;'>
        ✅ Connexion établie avec Google Sheets
    </p>
</div>
""", unsafe_allow_html=True)

# --- TITRE + LOGO (PLUS COMPACTS) ---
st.sidebar.markdown("<h3 style='color: #ea2b5e; margin: 0px 0 8px 0; padding: 0; line-height: 1.1; font-size: 1.35rem;'>🏢 CAP25 - Mobilité interne</h3>", unsafe_allow_html=True)

st.sidebar.image("Logo - BO RH in'li.png", width=250)

st.sidebar.markdown("<hr style='margin: 8px 0px 10px 0px; border: none; border-top: 1px solid #e5e7eb;'>", unsafe_allow_html=True)

# --- MENU NAVIGATION ---
page = st.sidebar.radio(
    "Navigation",
    [
        "📊 Tableau de Bord", 
        "👥 Gestion des Candidatures", 
        "📝 Entretien RH", 
        "💻🔍 Candidatures/Poste",
        "🎯 Analyse par Poste", 
        "🗒️🔁 Tableau agrégé AM",
        "🚀✨ Commission RH",
        "🌳 Référentiel Postes",
        "🏛️ Organigramme Cap25"
    ],
    label_visibility="collapsed"
)

st.sidebar.markdown("<div style='margin: 10px 0;'></div>", unsafe_allow_html=True)

if st.sidebar.button("🔄 Rafraîchir les données", use_container_width=True):
    st.sidebar.caption("ℹ️ Les données sont mises en cache pendant 1 minute")
    st.sidebar.warning("⚠️ Rafraîchissement en cours...")
    time.sleep(1)
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("<div style='margin: 8px 0;'></div>", unsafe_allow_html=True)

paris_tz = pytz.timezone('Europe/Paris')
paris_time = datetime.now(paris_tz)
st.sidebar.caption(f"Dernière MAJ : {paris_time.strftime('%H:%M:%S')}")

if st.session_state.last_save_time:
    st.sidebar.caption(f"💾 Sauvegarde : {st.session_state.last_save_time.strftime('%H:%M:%S')}")

st.sidebar.markdown("<div style='margin: 18px 0;'></div>", unsafe_allow_html=True)

# Logo en bas
col_logo = st.sidebar.columns([1, 2, 1])
with col_logo[1]:
    st.sidebar.image("Logo- in'li.png", width=210)
    
# ========================================
# PAGE 1 : TABLEAU DE BORD - VERSION PRO
# ========================================

if page == "📊 Tableau de Bord":
    paris_tz = pytz.timezone('Europe/Paris')
    now = datetime.now(paris_tz)
    
    st.title("📊 Tableau de Bord - Vue d'ensemble")
    st.markdown(f"<p style='font-style: italic; color: #ea2b5e; font-size: 1.1em; font-weight: 500;'>📌 Avancement global de la mobilité interne au {now.strftime('%d/%m/%Y')} à {now.strftime('%H:%M')}</p>", unsafe_allow_html=True)
    st.divider()
    
    # ===== MÉTRIQUES PRINCIPALES =====
    st.subheader("🎯 Indicateurs clés")
    
    nb_collaborateurs = len(collaborateurs_df[
        (collaborateurs_df["Matricule"].notna()) & 
        (collaborateurs_df["Matricule"] != "") &
        (collaborateurs_df["Rencontre RH / Positionnement"].str.upper() == "OUI")
    ])
    
    postes_ouverts_df = postes_df[postes_df["Mobilité interne"].str.lower() == "oui"]
    nb_postes_ouverts = int(postes_ouverts_df["Nombre total de postes"].sum()) if "Nombre total de postes" in postes_df.columns else len(postes_ouverts_df)
    
    nb_postes_attribues = len(collaborateurs_df[
        (collaborateurs_df["Vœux Retenu"].notna()) & 
        (collaborateurs_df["Vœux Retenu"].astype(str).str.strip() != "")
    ])
    
    pct_attribution = (nb_postes_attribues / nb_postes_ouverts * 100) if nb_postes_ouverts > 0 else 0
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 20px; border-radius: 12px; color: white;'>
            <h3 style='margin:0; color: white;'>👥 Collaborateurs</h3>
            <h1 style='margin:10px 0; color: white;'>{}</h1>
            <p style='margin:0; opacity: 0.9;'>à repositionner</p>
        </div>
        """.format(nb_collaborateurs), unsafe_allow_html=True)
    
    with c2:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                    padding: 20px; border-radius: 12px; color: white;'>
            <h3 style='margin:0; color: white;'>📢 Postes ouverts</h3>
            <h1 style='margin:10px 0; color: white;'>{}</h1>
            <p style='margin:0; opacity: 0.9;'>mobilité interne</p>
        </div>
        """.format(nb_postes_ouverts), unsafe_allow_html=True)
    
    with c3:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); 
                    padding: 20px; border-radius: 12px; color: white;'>
            <h3 style='margin:0; color: white;'>🎯 Taux d'affectation</h3>
            <h1 style='margin:10px 0; color: white;'>{:.1f}%</h1>
            <p style='margin:0; opacity: 0.9;'>{} postes pourvus</p>
        </div>
        """.format(pct_attribution, nb_postes_attribues), unsafe_allow_html=True)
        
        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        col_prog1, col_prog2 = st.columns([pct_attribution, 100 - pct_attribution] if pct_attribution < 100 else [100, 0.1])
        with col_prog1:
            st.markdown(f"""
            <div style='background: #10b981; height: 25px; border-radius: 12px; 
                        display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;'>
                {pct_attribution:.1f}%
            </div>
            """, unsafe_allow_html=True)
        if pct_attribution < 100:
            with col_prog2:
                st.markdown(f"""
                <div style='background: #e5e7eb; height: 25px; border-radius: 12px; 
                            display: flex; align-items: center; justify-content: center; color: #6b7280;'>
                    {100 - pct_attribution:.1f}%
                </div>
                """, unsafe_allow_html=True)
    
    st.divider()
    
    # ===== PRIORITÉS =====
    st.subheader("⭐ Ventilation des Priorités")
    
    nb_priorite_1 = len(collaborateurs_df[collaborateurs_df["Priorité"] == "Priorité 1"])
    nb_priorite_2 = len(collaborateurs_df[collaborateurs_df["Priorité"] == "Priorité 2"])
    nb_priorite_3_4 = len(collaborateurs_df[
        (collaborateurs_df["Priorité"] == "Priorité 3") | 
        (collaborateurs_df["Priorité"] == "Priorité 4")
    ])
    
    total_priorites = nb_priorite_1 + nb_priorite_2 + nb_priorite_3_4
    pct_p1 = (nb_priorite_1 / total_priorites * 100) if total_priorites > 0 else 0
    pct_p2 = (nb_priorite_2 / total_priorites * 100) if total_priorites > 0 else 0
    pct_p3_4 = (nb_priorite_3_4 / total_priorites * 100) if total_priorites > 0 else 0
    
    col5, col6, col7 = st.columns(3)
    
    with col5:
        st.metric("🔴 Priorité 1", nb_priorite_1, delta=f"{int(pct_p1)}%", delta_color="off")
        st.markdown(f"<p style='color: #10b981; font-weight: bold; margin-top: -10px;'>{int(pct_p1)}% du total</p>", unsafe_allow_html=True)
    
    with col6:
        st.metric("🟠 Priorité 2", nb_priorite_2, delta=f"{int(pct_p2)}%", delta_color="off")
        st.markdown(f"<p style='color: #10b981; font-weight: bold; margin-top: -10px;'>{int(pct_p2)}% du total</p>", unsafe_allow_html=True)
    
    with col7:
        st.metric("🟡 Priorité 3 et 4", nb_priorite_3_4, delta=f"{int(pct_p3_4)}%", delta_color="off")
        st.markdown(f"<p style='color: #10b981; font-weight: bold; margin-top: -10px;'>{int(pct_p3_4)}% du total</p>", unsafe_allow_html=True)
    
    st.divider()
    
    # ===== ENTRETIENS =====
    st.subheader("🗓️ Pilotage des entretiens RH")
    
    today = date.today()
    entretiens_planifies = 0
    entretiens_aujourd_hui = 0
    entretiens_realises = 0
    
    for idx, row in collaborateurs_df.iterrows():
        date_rdv = parse_date(row.get("Date de rdv", ""))
        if date_rdv:
            if date_rdv > today:
                entretiens_planifies += 1
            elif date_rdv == today:
                entretiens_aujourd_hui += 1
            elif date_rdv < today:
                entretiens_realises += 1
    
    total_entretiens = entretiens_planifies + entretiens_aujourd_hui + entretiens_realises
    pct_planifies = (entretiens_planifies / total_entretiens * 100) if total_entretiens > 0 else 0
    pct_aujourd_hui = (entretiens_aujourd_hui / total_entretiens * 100) if total_entretiens > 0 else 0
    pct_realises = (entretiens_realises / total_entretiens * 100) if total_entretiens > 0 else 0
    
    col9, col10, col11 = st.columns(3)
    
    with col9:
        st.metric("⏳ Entretiens planifiés", entretiens_planifies)
        st.markdown(f"<p style='color: #10b981; font-weight: bold; margin-top: -10px;'>{int(pct_planifies)}% du total</p>", unsafe_allow_html=True)
    
    with col10:
        st.metric("✅ Entretiens réalisés", entretiens_realises)
        st.markdown(f"<p style='color: #10b981; font-weight: bold; margin-top: -10px;'>{int(pct_realises)}% du total</p>", unsafe_allow_html=True)
    
    with col11:
        st.metric("⏰ Aujourd'hui", entretiens_aujourd_hui)
        st.markdown(f"<p style='color: #10b981; font-weight: bold; margin-top: -10px;'>{int(pct_aujourd_hui)}% du total</p>", unsafe_allow_html=True)
    
    st.divider()
    
    # --- SECTION 3 : LE TOP & FLOP (La MasterClass visuelle) ---
    st.subheader("📊 La demande par poste")
    
    # Préparation des données (Voeux 1, 2 et 3 combinés)
    all_voeux = pd.concat([collaborateurs_df["Vœux 1"], collaborateurs_df["Vœux 2"], collaborateurs_df["Voeux 3"]])
    all_voeux = all_voeux[all_voeux.notna() & (all_voeux.str.strip() != "") & (all_voeux != "Positionnement manquant")]

    if all_voeux.empty:
        st.info("Aucune donnée de vœux disponible.")
    else:
        col_top, col_flop = st.columns(2)
        
        # --- TABLEAU GAUCHE : TOP 10 ---
        with col_top:
            st.markdown("##### 🔥 Top 10 : Les plus demandés")
            top_data = all_voeux.value_counts().head(10).reset_index()
            top_data.columns = ["Poste", "Demandes"]
            top_max = top_data["Demandes"].max() # Pour l'échelle de la barre
            
            st.dataframe(
                top_data,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Poste": st.column_config.TextColumn(
                        "Intitulé du poste",
                        width="medium", # Laisse de la place au texte
                        help="Intitulé officiel du poste"
                    ),
                    "Demandes": st.column_config.ProgressColumn(
                        "Nombre de voeux",
                        help="Nombre de vœux cumulés",
                        format="%d",
                        min_value=0,
                        max_value=int(top_max), # Echelle relative au max
                        width="small" # Compact
                    ),
                },
                height=400 # Hauteur fixe pour alignement
            )

        # --- TABLEAU DROITE : FLOP 10 (Attention) ---
        with col_flop:
            st.markdown("##### ⚠️ Postes : En manque d'attractivité")
            # On prend ceux qui ont des voeux mais le moins (tail), ou 0 si on avait la liste complète
            flop_data = all_voeux.value_counts().tail(10).sort_values().reset_index()
            flop_data.columns = ["Poste", "Demandes"]
            
            st.dataframe(
                flop_data,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Poste": st.column_config.TextColumn(
                        "Intitulé du poste",
                        width="medium"
                    ),
                    "Demandes": st.column_config.ProgressColumn(
                        "Nombre de voeux",
                        format="%d",
                        min_value=0,
                        max_value=int(top_max), # On garde la même échelle que le TOP pour comparer visuellement !
                        width="small"
                        # Note: Streamlit ne permet pas encore de changer la couleur de la barre nativement en rouge via API simple
                        # mais le contexte "Attention" suffit.
                    ),
                },
                height=400
            )


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
            "Poste actuel": get_safe_value(row.get('Poste libellé', "")),
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
            width="stretch",
            hide_index=True
        )
        
        st.divider()



        st.subheader("📤 Exporter les données")

        # Déterminer si des filtres sont actifs
        filtres_actifs_candidatures = bool(filtre_direction) or bool(filtre_collaborateur) or bool(search_nom) or bool(filtre_rrh) or (filtre_date_rdv is not None)

        if filtres_actifs_candidatures:
            st.info("💡 Le fichier exporté contiendra les données **filtrées** affichées dans le tableau ci-dessus.")

        excel_file = to_excel(display_df.drop(columns=["Matricule"]))

        st.download_button(
            label="📥 Télécharger en Excel",
            data=excel_file,
            file_name=f"CAP25_Candidatures_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        
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
                    st.rerun()

# ========================================
# PAGE 3 : ENTRETIEN RH (VERSION FINALE AVEC VŒUX 4)
# ========================================

elif page == "📝 Entretien RH":
    st.title("📝 Conduite d'Entretien RH - CAP 2025")
    
    col_info1, col_info2 = st.columns([3, 1])
    with col_info1:
        st.info("""
        📝 Vos saisies sont sauvegardées automatiquement dans Google Sheets.
        💡 Vous pouvez revenir sur cette page à tout moment pour consulter ou modifier un entretien.
        """)
    
    with col_info2:
        if st.button("💾 Sauvegarder maintenant", type="secondary", width="stretch"):
            if st.session_state.entretien_data and st.session_state.current_matricule:
                save_entretien_to_gsheet(gsheet_client, SHEET_URL, st.session_state.entretien_data, show_success=True)
    
    st.divider()
    
    # ===== SECTION 1 : SÉLECTION DU COLLABORATEUR =====
    st.subheader("1️⃣ Sélection du collaborateur")
    
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
            filtered_collabs_df = collaborateurs_df.copy()
        else:
            filtered_collabs_df = collaborateurs_df[collaborateurs_df["Direction libellé"] == selected_direction].copy()
        
        # ✅ FILTRER : uniquement les collaborateurs avec NOM et Prénom non vides
        filtered_collabs_df = filtered_collabs_df[
            (filtered_collabs_df["NOM"].notna()) & 
            (filtered_collabs_df["NOM"].astype(str).str.strip() != "") &
            (filtered_collabs_df["Prénom"].notna()) & 
            (filtered_collabs_df["Prénom"].astype(str).str.strip() != "")
        ]
        
        collaborateur_list = sorted(
            (filtered_collabs_df["NOM"] + " " + filtered_collabs_df["Prénom"]).tolist()
        )
        
        with col_collab:
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
        
        if st.button("▶️ Démarrer/Reprendre l'entretien", type="primary", disabled=(selected_collab_new == "-- Sélectionner --"), width="stretch"):
            collab_mask = (collaborateurs_df["NOM"] + " " + collaborateurs_df["Prénom"]) == selected_collab_new
            collab = collaborateurs_df[collab_mask].iloc[0]
            matricule = get_safe_value(collab.get('Matricule', ''))
            
            existing_entretien = load_entretien_from_gsheet(gsheet_client, SHEET_URL, matricule)
            
            if existing_entretien:
                st.session_state.entretien_data = existing_entretien
                st.info(f"✅ Entretien existant chargé pour {selected_collab_new}")
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
            st.session_state.selected_collaborateur = selected_collab_new
            st.rerun()
    


    with col_mode2:
        st.markdown("#### 📂 Consulter un entretien existant")
    
        # ✅ SI UN ENTRETIEN EST DÉJÀ OUVERT, VERROUILLER LA SÉLECTION
        if st.session_state.current_matricule:
            st.warning(f"📌 Entretien en cours : **{st.session_state.selected_collaborateur}**")
            st.caption("Utilisez le bouton '🔄 Sélectionner un autre collaborateur' pour changer.")
        else:
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
                
                    if st.button("📖 Ouvrir cet entretien", type="secondary", disabled=(selected_existing == "-- Sélectionner --"), width="stretch"):
                        for record in all_records:
                            if f"{record['Nom']} {record['Prénom']}" == selected_existing:
                                st.session_state.entretien_data = record.copy()
                                st.session_state.current_matricule = record['Matricule']
                                st.session_state.selected_collaborateur = selected_existing
                                st.session_state.force_reload_entretien = True
                            
                                st.success(f"✅ Entretien chargé : {selected_existing}")
                                time.sleep(0.5)
                                st.rerun()
                                break
                else:
                    st.info("Aucun entretien sauvegardé pour le moment")
                    
            except Exception as e:
                st.warning("Impossible de charger les entretiens existants")
    
    # ===== SECTION 2 : FORMULAIRE D'ENTRETIEN =====
    if st.session_state.current_matricule and st.session_state.selected_collaborateur:
        st.divider()
        
        # 🔄 RECHARGER LES VŒUX DEPUIS GOOGLE SHEETS
        collab_mask = (collaborateurs_df["NOM"] + " " + collaborateurs_df["Prénom"]) == st.session_state.selected_collaborateur
        if collab_mask.any():
            collab = collaborateurs_df[collab_mask].iloc[0]
            
            # ✅ MISE À JOUR : Recharger les vœux actuels depuis CAP 2025
            voeu1_actuel_gsheet = get_safe_value(collab.get('Vœux 1', ''))
            voeu2_actuel_gsheet = get_safe_value(collab.get('Vœux 2', ''))
            voeu3_actuel_gsheet = get_safe_value(collab.get('Voeux 3', ''))
            voeu4_actuel_gsheet = get_safe_value(collab.get('Voeux 4', ''))
            
            # Mettre à jour st.session_state.entretien_data avec les valeurs du Google Sheet
            st.session_state.entretien_data['Voeu_1'] = voeu1_actuel_gsheet
            st.session_state.entretien_data['Voeu_2'] = voeu2_actuel_gsheet
            st.session_state.entretien_data['Voeu_3'] = voeu3_actuel_gsheet
            st.session_state.entretien_data['Voeu_4'] = voeu4_actuel_gsheet
            
            with st.container(border=True):
                col_info1, col_info2, col_info3 = st.columns(3)
                
                with col_info1:
                    st.markdown(f"**Matricule** : {get_safe_value(collab.get('Matricule', 'N/A'))}")
                    st.markdown(f"**Nom** : {get_safe_value(collab.get('NOM', ''))} {get_safe_value(collab.get('Prénom', ''))}")
                    st.markdown(f"**Mail** : {get_safe_value(collab.get('Mail', 'N/A'))}")
                
                with col_info2:
                    st.markdown(f"**Poste actuel** : {get_safe_value(collab.get('Poste libellé', 'N/A'))}")
                    st.markdown(f"**Direction** : {get_safe_value(collab.get('Direction libellé', 'N/A'))}")
                    anciennete_display = calculate_anciennete(get_safe_value(collab.get("Date entrée groupe", "")))
                    st.markdown(f"**Ancienneté** : {anciennete_display}")
                
                with col_info3:
                    st.markdown(f"**RRH** : {get_safe_value(collab.get('Référente RH', 'N/A'))}")
                    st.markdown(f"**Date RDV** : {get_safe_value(collab.get('Date de rdv', 'N/A'))}")
                    st.markdown(f"**Priorité** : {get_safe_value(collab.get('Priorité', 'N/A'))}")
            
            st.divider()
            
            if st.button("🔄 Sélectionner un autre collaborateur"):
                st.session_state.current_matricule = None
                st.session_state.selected_collaborateur = None
                st.session_state.entretien_data = {}
                st.rerun()
            
            # ===== NOUVEAU MODULE : GESTION DES VŒUX =====
            st.subheader("🎯 Gestion des vœux du collaborateur")
            
            with st.expander("✏️ Modifier l'ordre des vœux", expanded=False):
                st.markdown("Vous pouvez réorganiser les vœux du collaborateur ci-dessous :")
                
                voeux_actuels = [v for v in [voeu1_actuel_gsheet, voeu2_actuel_gsheet, voeu3_actuel_gsheet] if v and v != "Positionnement manquant"]
                
                if len(voeux_actuels) > 0:
                    col_v1, col_v2, col_v3 = st.columns(3)
                    
                    with col_v1:
                        new_voeu1 = st.selectbox(
                            "Nouveau Vœu 1",
                            options=voeux_actuels,
                            index=0 if voeu1_actuel_gsheet in voeux_actuels else 0,
                            key="reorder_v1"
                        )
                    
                    with col_v2:
                        remaining_v2 = [v for v in voeux_actuels if v != new_voeu1]
                        new_voeu2 = st.selectbox(
                            "Nouveau Vœu 2",
                            options=[""] + remaining_v2,
                            index=0,
                            key="reorder_v2"
                        )
                    
                    with col_v3:
                        remaining_v3 = [v for v in voeux_actuels if v != new_voeu1 and v != new_voeu2]
                        new_voeu3 = st.selectbox(
                            "Nouveau Vœu 3",
                            options=[""] + remaining_v3,
                            index=0,
                            key="reorder_v3"
                        )
                    
                    if st.button("✅ Valider le nouvel ordre", type="primary", key="validate_reorder"):
                        success = update_voeux_order(
                            gsheet_client, 
                            SHEET_URL, 
                            st.session_state.current_matricule,
                            new_voeu1,
                            new_voeu2 if new_voeu2 else "",
                            new_voeu3 if new_voeu3 else ""
                        )
                        
                        if success:
                            st.session_state.entretien_data['Voeu_1'] = new_voeu1
                            st.session_state.entretien_data['Voeu_2'] = new_voeu2 if new_voeu2 else ""
                            st.session_state.entretien_data['Voeu_3'] = new_voeu3 if new_voeu3 else ""
                            
                            st.success("✅ Ordre des vœux mis à jour avec succès !")
                            time.sleep(1)
                            st.rerun()
                else:
                    st.info("Aucun vœu renseigné pour ce collaborateur")
            
            with st.expander("➕ Ajouter un Vœu 4", expanded=False):
                st.markdown("##### 🔍 Rechercher et ajouter un Vœu 4")
                
                search_voeu4 = st.text_input("Rechercher un poste", key="search_voeu4")
                
                if search_voeu4:
                    postes_filtres = postes_df[postes_df["Poste"].str.contains(search_voeu4, case=False, na=False)]
                    
                    if not postes_filtres.empty:
                        voeu4_selectionne = st.selectbox(
                            "Sélectionner le Vœu 4",
                            options=["-- Sélectionner --"] + postes_filtres["Poste"].tolist(),
                            key="select_voeu4"
                        )
                        
                        if voeu4_selectionne != "-- Sélectionner --":
                            st.markdown(f"**Confirmez-vous l'ajout du vœu « {voeu4_selectionne} » pour {st.session_state.entretien_data.get('Prénom', '')} {st.session_state.entretien_data.get('Nom', '')} ?**")
                            
                            col_btn_v4_1, col_btn_v4_2 = st.columns(2)
                            
                            with col_btn_v4_1:
                                if st.button("❌ Annuler", key="cancel_voeu4"):
                                    st.info("Ajout du Vœu 4 annulé")
                            
                            with col_btn_v4_2:
                                if st.button("✅ Oui, je confirme", type="primary", key="confirm_voeu4"):
                                    success = update_voeu_4(
                                        gsheet_client,
                                        SHEET_URL,
                                        st.session_state.current_matricule,
                                        voeu4_selectionne
                                    )
                                    
                                    if success:
                                        st.session_state.entretien_data['Voeu_4'] = voeu4_selectionne
                                        
                                        st.success(f"✅ Vœu 4 « {voeu4_selectionne} » ajouté avec succès !")
                                        time.sleep(2)
                                        st.rerun()
                    else:
                        st.info("Aucun poste trouvé avec ce terme de recherche")
            
            st.divider()
            
            # ===== CRÉATION DYNAMIQUE DES ONGLETS =====
            voeu1_label = st.session_state.entretien_data.get('Voeu_1', '')
            voeu2_label = st.session_state.entretien_data.get('Voeu_2', '')
            voeu3_label = st.session_state.entretien_data.get('Voeu_3', '')
            voeu4_label = st.session_state.entretien_data.get('Voeu_4', '')
            
            # Construire la liste des onglets dynamiquement
            tab_labels = []
            tab_keys = []
            
            if voeu1_label and voeu1_label != "Positionnement manquant":
                tab_labels.append(f"🎯 Vœu 1: {voeu1_label}")
                tab_keys.append("V1")
            
            if voeu2_label and voeu2_label != "Positionnement manquant":
                tab_labels.append(f"🎯 Vœu 2: {voeu2_label}")
                tab_keys.append("V2")
            
            if voeu3_label and voeu3_label != "Positionnement manquant":
                tab_labels.append(f"🎯 Vœu 3: {voeu3_label}")
                tab_keys.append("V3")
            
            if voeu4_label and voeu4_label != "Positionnement manquant":
                tab_labels.append(f"🎯 Vœu 4: {voeu4_label}")
                tab_keys.append("V4")
            
            tab_labels.append("💬 Avis RH")
            tab_keys.append("AVIS")
            
            # Créer les onglets dynamiquement
            tabs = st.tabs(tab_labels)
            
            # ===== FONCTION GÉNÉRIQUE POUR RENDRE UN ONGLET VŒEU =====
            def render_voeu_tab(tab_container, voeu_num, voeu_label, prefix):
                """
                Fonction générique pour afficher le contenu d'un onglet vœu
                """
                with tab_container:
                    st.subheader(f"Évaluation du Vœu {voeu_num} : {voeu_label}")
                    
                    if st.session_state.last_save_time:
                        st.caption(f"💾 Dernière sauvegarde automatique : {st.session_state.last_save_time.strftime('%H:%M:%S')}")
                    
                    st.markdown("#### 📋 Questions générales")
                    
                    # Motivations
                    motiv = st.text_area(
                        "Quelles sont vos motivations pour ce poste ?",
                        value=st.session_state.entretien_data.get(f"{prefix}Motivations", ""),
                        key=f"{prefix.lower()}motiv",
                        height=100
                    )
                    if motiv != st.session_state.entretien_data.get(f"{prefix}Motivations", ""):
                        st.session_state.entretien_data[f"{prefix}Motivations"] = motiv
                        auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    # Vision des enjeux
                    vision = st.text_area(
                        "Quelle est votre vision des enjeux du poste ?",
                        value=st.session_state.entretien_data.get(f"{prefix}Vision_Enjeux", ""),
                        key=f"{prefix.lower()}vision",
                        height=100
                    )
                    if vision != st.session_state.entretien_data.get(f"{prefix}Vision_Enjeux", ""):
                        st.session_state.entretien_data[f"{prefix}Vision_Enjeux"] = vision
                        auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    # Premières actions
                    actions = st.text_area(
                        "Quelles seraient vos premières actions à la prise de poste ?",
                        value=st.session_state.entretien_data.get(f"{prefix}Premieres_Actions", ""),
                        key=f"{prefix.lower()}actions",
                        height=100
                    )
                    if actions != st.session_state.entretien_data.get(f"{prefix}Premieres_Actions", ""):
                        st.session_state.entretien_data[f"{prefix}Premieres_Actions"] = actions
                        auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    st.markdown("#### 🎯 Évaluation des compétences")
                    
                    # Compétence 1
                    col_comp1_1, col_comp1_2 = st.columns([1, 2])
                    with col_comp1_1:
                        c1_nom = st.text_input(
                            "Compétence 1",
                            value=st.session_state.entretien_data.get(f"{prefix}Competence_1_Nom", ""),
                            key=f"{prefix.lower()}c1_nom"
                        )
                        if c1_nom != st.session_state.entretien_data.get(f"{prefix}Competence_1_Nom", ""):
                            st.session_state.entretien_data[f"{prefix}Competence_1_Nom"] = c1_nom
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        
                        # ✅ CORRECTION : Option vide par défaut
                        niveau_options = ["", "Débutant", "Confirmé", "Expert"]
                        current_niveau = st.session_state.entretien_data.get(f"{prefix}Competence_1_Niveau", "")
                        niveau_index = niveau_options.index(current_niveau) if current_niveau in niveau_options else 0
                        
                        c1_niv = st.selectbox(
                            "Niveau",
                            niveau_options,
                            index=niveau_index,
                            key=f"{prefix.lower()}c1_niv"
                        )
                        if c1_niv != st.session_state.entretien_data.get(f"{prefix}Competence_1_Niveau", ""):
                            st.session_state.entretien_data[f"{prefix}Competence_1_Niveau"] = c1_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_comp1_2:
                        c1_just = st.text_area(
                            "Justification et exemples concrets",
                            value=st.session_state.entretien_data.get(f"{prefix}Competence_1_Justification", ""),
                            key=f"{prefix.lower()}c1_just",
                            height=100
                        )
                        if c1_just != st.session_state.entretien_data.get(f"{prefix}Competence_1_Justification", ""):
                            st.session_state.entretien_data[f"{prefix}Competence_1_Justification"] = c1_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    
                    # Compétence 2
                    col_comp2_1, col_comp2_2 = st.columns([1, 2])
                    with col_comp2_1:
                        c2_nom = st.text_input(
                            "Compétence 2",
                            value=st.session_state.entretien_data.get(f"{prefix}Competence_2_Nom", ""),
                            key=f"{prefix.lower()}c2_nom"
                        )
                        if c2_nom != st.session_state.entretien_data.get(f"{prefix}Competence_2_Nom", ""):
                            st.session_state.entretien_data[f"{prefix}Competence_2_Nom"] = c2_nom
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        
                        current_niveau = st.session_state.entretien_data.get(f"{prefix}Competence_2_Niveau", "")
                        niveau_index = niveau_options.index(current_niveau) if current_niveau in niveau_options else 0
                        
                        c2_niv = st.selectbox(
                            "Niveau",
                            niveau_options,
                            index=niveau_index,
                            key=f"{prefix.lower()}c2_niv"
                        )
                        if c2_niv != st.session_state.entretien_data.get(f"{prefix}Competence_2_Niveau", ""):
                            st.session_state.entretien_data[f"{prefix}Competence_2_Niveau"] = c2_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_comp2_2:
                        c2_just = st.text_area(
                            "Justification et exemples concrets",
                            value=st.session_state.entretien_data.get(f"{prefix}Competence_2_Justification", ""),
                            key=f"{prefix.lower()}c2_just",
                            height=100
                        )
                        if c2_just != st.session_state.entretien_data.get(f"{prefix}Competence_2_Justification", ""):
                            st.session_state.entretien_data[f"{prefix}Competence_2_Justification"] = c2_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    
                    # Compétence 3
                    col_comp3_1, col_comp3_2 = st.columns([1, 2])
                    with col_comp3_1:
                        c3_nom = st.text_input(
                            "Compétence 3",
                            value=st.session_state.entretien_data.get(f"{prefix}Competence_3_Nom", ""),
                            key=f"{prefix.lower()}c3_nom"
                        )
                        if c3_nom != st.session_state.entretien_data.get(f"{prefix}Competence_3_Nom", ""):
                            st.session_state.entretien_data[f"{prefix}Competence_3_Nom"] = c3_nom
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        
                        current_niveau = st.session_state.entretien_data.get(f"{prefix}Competence_3_Niveau", "")
                        niveau_index = niveau_options.index(current_niveau) if current_niveau in niveau_options else 0
                        
                        c3_niv = st.selectbox(
                            "Niveau",
                            niveau_options,
                            index=niveau_index,
                            key=f"{prefix.lower()}c3_niv"
                        )
                        if c3_niv != st.session_state.entretien_data.get(f"{prefix}Competence_3_Niveau", ""):
                            st.session_state.entretien_data[f"{prefix}Competence_3_Niveau"] = c3_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_comp3_2:
                        c3_just = st.text_area(
                            "Justification et exemples concrets",
                            value=st.session_state.entretien_data.get(f"{prefix}Competence_3_Justification", ""),
                            key=f"{prefix.lower()}c3_just",
                            height=100
                        )
                        if c3_just != st.session_state.entretien_data.get(f"{prefix}Competence_3_Justification", ""):
                            st.session_state.entretien_data[f"{prefix}Competence_3_Justification"] = c3_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    st.markdown("#### 📊 Expérience")
                    
                    col_exp1, col_exp2 = st.columns([1, 2])
                    with col_exp1:
                        # ✅ CORRECTION : Option vide par défaut
                        exp_options = ["", "Débutant (0-3 ans)", "Confirmé (3-7 ans)", "Expert (8+ ans)"]
                        current_exp = st.session_state.entretien_data.get(f"{prefix}Experience_Niveau", "")
                        exp_index = exp_options.index(current_exp) if current_exp in exp_options else 0
                        
                        exp_niv = st.selectbox(
                            "Niveau d'expérience dans des contextes comparables",
                            exp_options,
                            index=exp_index,
                            key=f"{prefix.lower()}exp_niv"
                        )
                        if exp_niv != st.session_state.entretien_data.get(f"{prefix}Experience_Niveau", ""):
                            st.session_state.entretien_data[f"{prefix}Experience_Niveau"] = exp_niv
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_exp2:
                        exp_just = st.text_area(
                            "Quelle expérience justifie ce niveau ?",
                            value=st.session_state.entretien_data.get(f"{prefix}Experience_Justification", ""),
                            key=f"{prefix.lower()}exp_just",
                            height=100
                        )
                        if exp_just != st.session_state.entretien_data.get(f"{prefix}Experience_Justification", ""):
                            st.session_state.entretien_data[f"{prefix}Experience_Justification"] = exp_just
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    st.divider()
                    st.markdown("#### 🎓 Accompagnement et Formation")
                    
                    col_form1, col_form2 = st.columns([1, 2])
                    with col_form1:
                        accomp_options = ["Non", "Oui"]
                        current_accomp = st.session_state.entretien_data.get(f"{prefix}Besoin_Accompagnement", "Non")
                        accomp_index = accomp_options.index(current_accomp) if current_accomp in accomp_options else 0
                        
                        besoin = st.radio(
                            "Besoin d'accompagnement / formation ?",
                            accomp_options,
                            index=accomp_index,
                            key=f"{prefix.lower()}form_besoin"
                        )
                        if besoin != st.session_state.entretien_data.get(f"{prefix}Besoin_Accompagnement", ""):
                            st.session_state.entretien_data[f"{prefix}Besoin_Accompagnement"] = besoin
                            auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    with col_form2:
                        if besoin == "Oui":
                            type_accomp = st.text_area(
                                "Quels types de soutien ou d'accompagnement ?",
                                value=st.session_state.entretien_data.get(f"{prefix}Type_Accompagnement", ""),
                                key=f"{prefix.lower()}form_type",
                                height=100
                            )
                            if type_accomp != st.session_state.entretien_data.get(f"{prefix}Type_Accompagnement", ""):
                                st.session_state.entretien_data[f"{prefix}Type_Accompagnement"] = type_accomp
                                auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                        else:
                            if st.session_state.entretien_data.get(f"{prefix}Type_Accompagnement", "") != "":
                                st.session_state.entretien_data[f"{prefix}Type_Accompagnement"] = ""
                                auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                    
                    if st.button(f"💾 Sauvegarder Vœu {voeu_num}", key=f"save_{prefix.lower()}"):
                        save_entretien_to_gsheet(gsheet_client, SHEET_URL, st.session_state.entretien_data, show_success=True)
            
            # ===== AFFICHAGE DES ONGLETS =====
            tab_idx = 0
            
            for key in tab_keys:
                if key == "V1":
                    render_voeu_tab(tabs[tab_idx], 1, voeu1_label, "V1_")
                    tab_idx += 1
                elif key == "V2":
                    render_voeu_tab(tabs[tab_idx], 2, voeu2_label, "V2_")
                    tab_idx += 1
                elif key == "V3":
                    render_voeu_tab(tabs[tab_idx], 3, voeu3_label, "V3_")
                    tab_idx += 1
                elif key == "V4":
                    render_voeu_tab(tabs[tab_idx], 4, voeu4_label, "V4_")
                    tab_idx += 1
                elif key == "AVIS":
                    # ===== ONGLET AVIS RH =====
                    with tabs[tab_idx]:
                        st.subheader("💬 Avis RH Final")
                        
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
                        
                        voeux_list = []
                        if voeu1_label and voeu1_label != "Positionnement manquant":
                            voeux_list.append(voeu1_label)
                        if voeu2_label and voeu2_label != "Positionnement manquant":
                            voeux_list.append(voeu2_label)
                        if voeu3_label and voeu3_label != "Positionnement manquant":
                            voeux_list.append(voeu3_label)
                        if voeu4_label and voeu4_label != "Positionnement manquant":
                            voeux_list.append(voeu4_label)
                        
                        voeux_list.append("Autre")
                        
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

                        poste_final = None

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
                        
                        if poste_final:
                            st.markdown(f"##### Validez-vous le poste **{poste_final}** pour le collaborateur **{st.session_state.entretien_data.get('Prénom', '')} {st.session_state.entretien_data.get('Nom', '')}** ?")
                            
                            col_btn1, col_btn2, col_btn3 = st.columns(3)
                            
                            with col_btn1:
                                if st.button("❌ Non", key="btn_non", width="stretch"):
                                    st.session_state.entretien_data["Decision_RH_Poste"] = ""
                                    st.info("Décision annulée")
                                    auto_save_entretien(gsheet_client, SHEET_URL, st.session_state.entretien_data)
                            
                            with col_btn2:
                                if st.button("🟠 Oui en option RH", key="btn_option", type="secondary", width="stretch"):
                                    commentaire = f"Option RH à l'issue entretien : {poste_final}"
                                    success = update_commentaire_rh(gsheet_client, SHEET_URL, st.session_state.current_matricule, commentaire)
                                    
                                    if success:
                                        st.session_state.entretien_data["Decision_RH_Poste"] = f"Option: {poste_final}"
                                        save_entretien_to_gsheet(gsheet_client, SHEET_URL, st.session_state.entretien_data, show_success=False)
                                        
                                        st.success("✅ Option RH enregistrée avec succès !")
                                        time.sleep(2)
                                        st.rerun()
                            

                            with col_btn3:
                                if st.button("🟢 Oui, vœu retenu", key="btn_retenu", type="primary", use_container_width=True):
                                    success = update_voeu_retenu(gsheet_client, SHEET_URL, st.session_state.current_matricule, poste_final)
                
                                    if success:
                                        st.session_state.entretien_data["Decision_RH_Poste"] = f"Retenu: {poste_final}"
                                        save_entretien_to_gsheet(gsheet_client, SHEET_URL, st.session_state.entretien_data, show_success=False)
                    
                                        st.success("✅ Vœu retenu enregistré avec succès !")
                                        time.sleep(2)
                                        st.rerun()
        
                                        st.divider()
        
                        if st.button("💾 Sauvegarder l'entretien complet", type="primary", use_container_width=True):
                            save_entretien_to_gsheet(gsheet_client, SHEET_URL, st.session_state.entretien_data, show_success=True)

# ========================================
# NOUVELLE PAGE : COMPARATIF DES CANDIDATURES PAR POSTE
# ========================================

elif page == "💻🔍 Candidatures/Poste":
    st.title("💻 Comparatif des Candidatures par Poste")
    
    st.markdown("""
    Cette page vous permet de comparer côte à côte tous les entretiens RH des candidats pour un poste donné.
    Les candidats sont classés par ordre de vœu (V1 > V2 > V3 > V4) puis au sein de chaque voeu par ordre alphabétique.
    """)
    
    st.divider()

    # ===== FILTRES =====
    st.subheader("🔍 Filtres")
    
    # ✅ FILTRE AUTOMATIQUE : Postes mobilité interne uniquement (pas de checkbox)
    postes_filtres_df = postes_df[postes_df["Mobilité interne"].str.lower() == "oui"].copy()
    
    # Filtre par Direction
    directions_postes = sorted(postes_filtres_df["Direction"].unique())
    filtre_direction_poste = st.multiselect(
        "Filtrer par Direction",
        options=directions_postes,
        default=[],
        help="💡 Seuls les postes ouverts à la mobilité interne sont affichés"
    )

    if filtre_direction_poste:
        postes_filtres_df = postes_filtres_df[postes_filtres_df["Direction"].isin(filtre_direction_poste)]
  
    # Sélection du poste
    postes_list = sorted(postes_filtres_df["Poste"].unique())
    
    st.info(f"📌 **{len(postes_list)} postes** ouverts à la mobilité interne{' pour la/les direction(s) sélectionnée(s)' if filtre_direction_poste else ''}")
    
    poste_compare = st.selectbox(
        "🎯 Sélectionner un poste à analyser",
        options=["-- Sélectionner --"] + postes_list,
        key="select_poste_compare"
    )

    
    if poste_compare != "-- Sélectionner --":
        st.subheader(f"📊 Analyse comparative pour : **{poste_compare}**")
        
        # Charger tous les entretiens
        try:
            spreadsheet = gsheet_client.open_by_url(SHEET_URL)
            worksheet_entretiens = spreadsheet.worksheet("Entretien RH")
            all_entretiens = worksheet_entretiens.get_all_records()
            
            # Trouver les candidats pour ce poste
            candidats_data = []
            
            for _, collab in collaborateurs_df.iterrows():
                voeu_match = None
                ordre_voeu = 99  # Pour le tri
                
                voeu1 = get_safe_value(collab.get('Vœux 1', ''))
                voeu2 = get_safe_value(collab.get('Vœux 2', ''))
                voeu3 = get_safe_value(collab.get('Voeux 3', ''))
                voeu4 = get_safe_value(collab.get('Voeux 4', '')) 
                
                if voeu1 == poste_compare:
                    voeu_match = "Vœu 1"
                    ordre_voeu = 1
                elif voeu2 == poste_compare:
                    voeu_match = "Vœu 2"
                    ordre_voeu = 2
                elif voeu3 == poste_compare:
                    voeu_match = "Vœu 3"
                    ordre_voeu = 3
                elif voeu4 == poste_compare:
                    voeu_match = "Vœu 4"
                    ordre_voeu = 4                   
                
                if voeu_match:
                    matricule = get_safe_value(collab.get('Matricule', ''))
                    nom = get_safe_value(collab.get('NOM', ''))
                    prenom = get_safe_value(collab.get('Prénom', ''))
                    
                    # Trouver l'entretien correspondant
                    entretien = None
                    for ent in all_entretiens:
                        if str(ent.get('Matricule', '')) == str(matricule):
                            entretien = ent
                            break
                    
                    candidats_data.append({
                        'ordre_voeu': ordre_voeu,
                        'nom': nom,
                        'prenom': prenom,
                        'voeu_match': voeu_match,
                        'matricule': matricule,
                        'entretien': entretien,
                        'poste_actuel': get_safe_value(collab.get('Poste libellé', '')),
                        'anciennete': calculate_anciennete(get_safe_value(collab.get("Date entrée groupe", ""))),
                        'priorite': get_safe_value(collab.get('Priorité', ''))
                    })
            
            # Trier : d'abord par ordre de vœu, puis par nom
            candidats_data.sort(key=lambda x: (x['ordre_voeu'], x['nom'], x['prenom']))
            
            if len(candidats_data) == 0:
                st.info(f"Aucun candidat n'a émis de vœu pour le poste « {poste_compare} »")
            else:
                st.success(f"**{len(candidats_data)} candidat(s)** trouvé(s) pour ce poste")

                # Calcul des statistiques par vœu
                nb_v1 = sum(1 for c in candidats_data if c['voeu_match'] == "Vœu 1")
                nb_v2 = sum(1 for c in candidats_data if c['voeu_match'] == "Vœu 2")
                nb_v3 = sum(1 for c in candidats_data if c['voeu_match'] == "Vœu 3")
                nb_v4 = sum(1 for c in candidats_data if c['voeu_match'] == "Vœu 4")
                total_cand = len(candidats_data)

                pct_v1 = (nb_v1 / total_cand * 100) if total_cand > 0 else 0
                pct_v2 = (nb_v2 / total_cand * 100) if total_cand > 0 else 0
                pct_v3 = (nb_v3 / total_cand * 100) if total_cand > 0 else 0
                pct_v4 = (nb_v4 / total_cand * 100) if total_cand > 0 else 0

                st.markdown(f"""
                **Ventilation détaillée :**  
                Vœu 1 : **{nb_v1}** soit {pct_v1:.0f}% — Vœu 2 : **{nb_v2}** soit {pct_v2:.0f}% — Vœu 3 : **{nb_v3}** soit {pct_v3:.0f}% — Vœu 4 : **{nb_v4}** soit {pct_v4:.0f}%
                """)                
                
                # Créer le tableau comparatif
                tableau_comparatif = []
                
                for cand in candidats_data:
                    entretien = cand['entretien']
                    
                    # Déterminer quel vœu correspond au poste
                    prefix = ""
                    if cand['voeu_match'] == "Vœu 1":
                        prefix = "V1_"
                    elif cand['voeu_match'] == "Vœu 2":
                        prefix = "V2_"
                    elif cand['voeu_match'] == "Vœu 3":
                        prefix = "V3_"
                    elif cand['voeu_match'] == "Vœu 4":
                        prefix = "V4_"                        
                    
                    row_data = {
                        "Rang de vœu": cand['voeu_match'],
                        "NOM": cand['nom'],
                        "Prénom": cand['prenom'],
                        "Poste actuel": cand['poste_actuel'],
                        "Ancienneté": cand['anciennete'],
                        "Priorité": cand['priorite'],
                    }
                    
                    if entretien:
                        row_data.update({
                            "Motivations": entretien.get(f"{prefix}Motivations", ""),
                            "Vision des enjeux": entretien.get(f"{prefix}Vision_Enjeux", ""),
                            "Premières actions": entretien.get(f"{prefix}Premieres_Actions", ""),
                            "Compétence 1": entretien.get(f"{prefix}Competence_1_Nom", ""),
                            "Niveau C1": entretien.get(f"{prefix}Competence_1_Niveau", ""),
                            "Justif. C1": entretien.get(f"{prefix}Competence_1_Justification", ""),
                            "Compétence 2": entretien.get(f"{prefix}Competence_2_Nom", ""),
                            "Niveau C2": entretien.get(f"{prefix}Competence_2_Niveau", ""),
                            "Justif. C2": entretien.get(f"{prefix}Competence_2_Justification", ""),
                            "Compétence 3": entretien.get(f"{prefix}Competence_3_Nom", ""),
                            "Niveau C3": entretien.get(f"{prefix}Competence_3_Niveau", ""),
                            "Justif. C3": entretien.get(f"{prefix}Competence_3_Justification", ""),
                            "Expérience": entretien.get(f"{prefix}Experience_Niveau", ""),
                            "Justif. Expérience": entretien.get(f"{prefix}Experience_Justification", ""),
                            "Besoin accompagnement": entretien.get(f"{prefix}Besoin_Accompagnement", ""),
                            "Type accompagnement": entretien.get(f"{prefix}Type_Accompagnement", ""),
                            "Avis RH": entretien.get("Avis_RH_Synthese", ""),
                            "Décision RH": entretien.get("Decision_RH_Poste", "")
                        })
                    else:
                        row_data.update({
                            "Motivations": "❌ Entretien non réalisé",
                            "Vision des enjeux": "",
                            "Premières actions": "",
                            "Compétence 1": "",
                            "Niveau C1": "",
                            "Justif. C1": "",
                            "Compétence 2": "",
                            "Niveau C2": "",
                            "Justif. C2": "",
                            "Compétence 3": "",
                            "Niveau C3": "",
                            "Justif. C3": "",
                            "Expérience": "",
                            "Justif. Expérience": "",
                            "Besoin accompagnement": "",
                            "Type accompagnement": "",
                            "Avis RH": "",
                            "Décision RH": ""
                        })
                    
                    tableau_comparatif.append(row_data)
                
                df_comparatif = pd.DataFrame(tableau_comparatif)
                
                # Affichage du tableau
                st.dataframe(
                    df_comparatif,
                    width="stretch",
                    hide_index=True
                )
                
                st.divider()
                


                
                # ✅ MODULE EXPORT AVEC MESSAGE CONDITIONNEL
                st.subheader("📥 Export Excel")
                
                filtres_actifs_export = bool(filtre_direction_poste)
                
                col_exp1, col_exp2 = st.columns([3, 1])
                
                with col_exp1:
                    if filtres_actifs_export:
                        st.info("💡 Le fichier exporté contiendra les données **filtrées** affichées dans le tableau ci-dessus.")
                
                with col_exp2:
                    excel_data = to_excel(df_comparatif)
                    
                    st.download_button(
                        label="📥 Télécharger en Excel",
                        data=excel_data,
                        file_name=f"comparatif_candidatures_{poste_compare.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )

        
        except Exception as e:
            st.error(f"Erreur lors du chargement des entretiens : {str(e)}")


# ========================================
# NOUVELLE PAGE : TABLEAU AGRÉGÉ POUR ALICE
# ========================================

elif page == "🗒️🔁 Tableau agrégé AM":
    st.title("🗒️🔁 Tableau Agrégé des Vœux - Vue Direction")
    
    st.markdown("""
    Ce tableau synthétise tous les vœux émis par poste Cap 25 avec le détail des profils métiers actuels des candidats.
   
    **Note : Seuls les postes ouverts à la mobilité sont affichés.**
    """)
    
    st.divider()
    
    # ===== CONSTRUCTION DU TABLEAU AGRÉGÉ =====
    aggregated_data = []
    
    for _, poste_row in postes_df.iterrows():
        # --- FILTRAGE : On ignore si "Nombre de postes vacants" est vide ---
        raw_vacants = poste_row.get("Nombre de postes vacants ", "")
        
        # Vérification robuste : si c'est null, NaN, ou une chaîne vide/espaces
        if pd.isna(raw_vacants) or str(raw_vacants).strip() == "":
            continue  # On passe au poste suivant immédiatement
            
        poste = poste_row.get("Poste", "")
        direction = poste_row.get("Direction", "")
        
        # Conversion sécurisée en int maintenant qu'on sait que ce n'est pas vide
        try:
            postes_ouverts = int(float(raw_vacants)) # float permet de gérer le cas "3.0" issu d'Excel
        except (ValueError, TypeError):
            # Si la valeur est "Inconnu" ou du texte, on décide soit de mettre 0, soit de sauter.
            # Ici, je mets 0 par sécurité, mais vous pouvez mettre 'continue' si vous voulez exclure les erreurs de format.
            postes_ouverts = 0
        
        # Initialiser les compteurs
        candidatures_v1 = 0
        candidatures_v2 = 0
        candidatures_v3 = 0
        candidatures_v4 = 0
        
        profils_v1 = {}
        profils_v2 = {}
        profils_v3 = {}
        profils_v4 = {}
        
        # Parcourir les collaborateurs
        for _, collab in collaborateurs_df.iterrows():
            poste_actuel = get_safe_value(collab.get('Poste libellé', "N/A"))
            
            # Vœu 1
            if get_safe_value(collab.get("Vœux 1", "")) == poste:
                candidatures_v1 += 1
                profils_v1[poste_actuel] = profils_v1.get(poste_actuel, 0) + 1
            
            # Vœu 2
            if get_safe_value(collab.get("Vœux 2", "")) == poste:
                candidatures_v2 += 1
                profils_v2[poste_actuel] = profils_v2.get(poste_actuel, 0) + 1
            
            # Vœu 3
            if get_safe_value(collab.get("Voeux 3", "")) == poste:
                candidatures_v3 += 1
                profils_v3[poste_actuel] = profils_v3.get(poste_actuel, 0) + 1
            
            # Vœu 4
            if get_safe_value(collab.get("Voeux 4", "")) == poste:
                candidatures_v4 += 1
                profils_v4[poste_actuel] = profils_v4.get(poste_actuel, 0) + 1
        
        # Formater les profils métiers
        def format_profils(profils_dict):
            if not profils_dict:
                return ""
            return "; ".join([f"{prof} ({count})" for prof, count in profils_dict.items()])
        
        candidatures_total = candidatures_v1 + candidatures_v2 + candidatures_v3 + candidatures_v4
        
        aggregated_data.append({
            "POSTE PROJETE": poste,
            "DIRECTION": direction,
            "POSTES OUVERTS": postes_ouverts,
            "CANDIDATURES TOTAL": candidatures_total,
            "CANDIDATURES VŒUX 1": candidatures_v1,
            "PROFILS DE METIER / CANDIDAT (Vœux 1)": format_profils(profils_v1),
            "CANDIDATURES VŒUX 2": candidatures_v2,
            "PROFILS DE METIER / CANDIDAT (Vœux 2)": format_profils(profils_v2),
            "CANDIDATURES VŒUX 3": candidatures_v3,
            "PROFILS DE METIER / CANDIDAT (Vœux 3)": format_profils(profils_v3),
            "CANDIDATURES VŒUX 4": candidatures_v4,
            "PROFILS DE METIER / CANDIDAT (Vœux 4)": format_profils(profils_v4)
        })
    
    df_aggregated = pd.DataFrame(aggregated_data)
    
    # Gestion du cas où le dataframe est vide après filtrage
    if df_aggregated.empty:
        st.warning("Aucun poste avec des vacances déclarées n'a été trouvé.")
    else:
        # ===== FILTRES =====
        st.subheader("🔍 Filtres")
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            filtre_direction_agg = st.multiselect(
                "Filtrer par Direction",
                options=sorted(df_aggregated["DIRECTION"].unique()),
                default=[]
            )
        
        with col_f2:
            max_cand = int(df_aggregated["CANDIDATURES TOTAL"].max()) if not df_aggregated.empty else 10
            filtre_min_candidatures = st.slider(
                "Nombre minimum de candidatures totales",
                min_value=0,
                max_value=max_cand,
                value=0
            )
        
        # Appliquer les filtres
        df_filtered_agg = df_aggregated.copy()
        
        if filtre_direction_agg:
            df_filtered_agg = df_filtered_agg[df_filtered_agg["DIRECTION"].isin(filtre_direction_agg)]
        
        df_filtered_agg = df_filtered_agg[df_filtered_agg["CANDIDATURES TOTAL"] >= filtre_min_candidatures]
        
        # Tri par nombre de candidatures décroissant
        df_filtered_agg = df_filtered_agg.sort_values("CANDIDATURES TOTAL", ascending=False)
        
        # Déterminer si des filtres sont actifs
        filtres_actifs = bool(filtre_direction_agg) or filtre_min_candidatures > 0
        
        st.divider()
        
        # ===== STATISTIQUES RAPIDES =====
        st.subheader("📈 Statistiques Rapides")
        
        # Calculs statistiques GLOBALES
        total_postes_ouverts_global = int(df_aggregated["POSTES OUVERTS"].sum())
        total_candidatures_global = int(df_aggregated["CANDIDATURES TOTAL"].sum())
        avg_cand_global = df_aggregated["CANDIDATURES TOTAL"].mean() if not df_aggregated.empty else 0
        postes_sans_candidat_global = len(df_aggregated[df_aggregated["CANDIDATURES TOTAL"] == 0])
        
        # Calculs statistiques FILTRÉES
        total_postes_ouverts_filtre = int(df_filtered_agg["POSTES OUVERTS"].sum())
        total_candidatures_filtre = int(df_filtered_agg["CANDIDATURES TOTAL"].sum())
        avg_cand_filtre = df_filtered_agg["CANDIDATURES TOTAL"].mean() if not df_filtered_agg.empty else 0
        postes_sans_candidat_filtre = len(df_filtered_agg[df_filtered_agg["CANDIDATURES TOTAL"] == 0])
        
        # Affichage des cartes
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        
        # ===== CARTE 1 : POSTES OUVERTS =====
        with col_stat1:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 10px;'>
                <h4 style='margin:0; color: white; font-size: 0.9rem; opacity: 0.9;'>📍 Postes Ouverts</h4>
                <h1 style='margin:10px 0; color: white; font-size: 2.5rem;'>{total_postes_ouverts_global}</h1>
                <p style='margin:0; opacity: 0.8; font-size: 0.85rem;'>📊 Vue globale</p>
            </div>
            """, unsafe_allow_html=True)
            
            if filtres_actifs:
                delta_pct = (total_postes_ouverts_filtre / total_postes_ouverts_global * 100) if total_postes_ouverts_global > 0 else 0
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #8e9eab 0%, #eef2f3 100%); 
                            padding: 15px; border-radius: 12px; color: #1F2937; text-align: center; border: 2px solid #667eea;'>
                    <h4 style='margin:0; color: #667eea; font-size: 0.85rem; font-weight: bold;'>🔍 Vue filtrée</h4>
                    <h2 style='margin:10px 0; color: #1F2937; font-size: 1.8rem;'>{total_postes_ouverts_filtre}</h2>
                    <p style='margin:0; color: #6B7280; font-size: 0.8rem;'>{delta_pct:.1f}% du total</p>
                </div>
                """, unsafe_allow_html=True)
        
        # ===== CARTE 2 : CANDIDATURES TOTAL =====
        with col_stat2:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                        padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 10px;'>
                <h4 style='margin:0; color: white; font-size: 0.9rem; opacity: 0.9;'>📊 Candidatures</h4>
                <h1 style='margin:10px 0; color: white; font-size: 2.5rem;'>{total_candidatures_global}</h1>
                <p style='margin:0; opacity: 0.8; font-size: 0.85rem;'>📊 Vue globale</p>
            </div>
            """, unsafe_allow_html=True)
            
            if filtres_actifs:
                delta_pct = (total_candidatures_filtre / total_candidatures_global * 100) if total_candidatures_global > 0 else 0
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #8e9eab 0%, #eef2f3 100%); 
                            padding: 15px; border-radius: 12px; color: #1F2937; text-align: center; border: 2px solid #f093fb;'>
                    <h4 style='margin:0; color: #f5576c; font-size: 0.85rem; font-weight: bold;'>🔍 Vue filtrée</h4>
                    <h2 style='margin:10px 0; color: #1F2937; font-size: 1.8rem;'>{total_candidatures_filtre}</h2>
                    <p style='margin:0; color: #6B7280; font-size: 0.8rem;'>{delta_pct:.1f}% du total</p>
                </div>
                """, unsafe_allow_html=True)
        
        # ===== CARTE 3 : MOYENNE =====
        with col_stat3:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); 
                        padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 10px;'>
                <h4 style='margin:0; color: white; font-size: 0.9rem; opacity: 0.9;'>📈 Moyenne</h4>
                <h1 style='margin:10px 0; color: white; font-size: 2.5rem;'>{avg_cand_global:.1f}</h1>
                <p style='margin:0; opacity: 0.8; font-size: 0.85rem;'>📊 Vue globale</p>
            </div>
            """, unsafe_allow_html=True)
            
            if filtres_actifs:
                delta_avg = avg_cand_filtre - avg_cand_global
                delta_sign = "+" if delta_avg > 0 else ""
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #8e9eab 0%, #eef2f3 100%); 
                            padding: 15px; border-radius: 12px; color: #1F2937; text-align: center; border: 2px solid #4facfe;'>
                    <h4 style='margin:0; color: #00f2fe; font-size: 0.85rem; font-weight: bold;'>🔍 Vue filtrée</h4>
                    <h2 style='margin:10px 0; color: #1F2937; font-size: 1.8rem;'>{avg_cand_filtre:.1f}</h2>
                    <p style='margin:0; color: #6B7280; font-size: 0.8rem;'>{delta_sign}{delta_avg:.1f} vs global</p>
                </div>
                """, unsafe_allow_html=True)
        
        # ===== CARTE 4 : SANS CANDIDAT =====
        with col_stat4:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); 
                        padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 10px;'>
                <h4 style='margin:0; color: white; font-size: 0.9rem; opacity: 0.9;'>⚠️ Sans Candidat</h4>
                <h1 style='margin:10px 0; color: white; font-size: 2.5rem;'>{postes_sans_candidat_global}</h1>
                <p style='margin:0; opacity: 0.8; font-size: 0.85rem;'>📊 Vue globale</p>
            </div>
            """, unsafe_allow_html=True)
            
            if filtres_actifs:
                delta_pct = (postes_sans_candidat_filtre / postes_sans_candidat_global * 100) if postes_sans_candidat_global > 0 else 0
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #8e9eab 0%, #eef2f3 100%); 
                            padding: 15px; border-radius: 12px; color: #1F2937; text-align: center; border: 2px solid #fa709a;'>
                    <h4 style='margin:0; color: #fa709a; font-size: 0.85rem; font-weight: bold;'>🔍 Vue filtrée</h4>
                    <h2 style='margin:10px 0; color: #1F2937; font-size: 1.8rem;'>{postes_sans_candidat_filtre}</h2>
                    <p style='margin:0; color: #6B7280; font-size: 0.8rem;'>{delta_pct:.1f}% du total</p>
                </div>
                """, unsafe_allow_html=True)
        
        st.divider()
        
        # ===== AFFICHAGE DU TABLEAU =====
        st.subheader(f"📊 {len(df_filtered_agg)} poste(s) affiché(s)")
        
        st.dataframe(
            df_filtered_agg,
            width=None, # Remplacement de "stretch" par None ou use_container_width=True pour compatibilité
            use_container_width=True,
            hide_index=True,
            column_config={
                "POSTE PROJETE": st.column_config.TextColumn("Poste Projeté", width="large"),
                "DIRECTION": st.column_config.TextColumn("Direction", width="medium"),
                "POSTES OUVERTS": st.column_config.NumberColumn("Postes Ouverts", width="small", format="%d"),
                "CANDIDATURES TOTAL": st.column_config.NumberColumn("Candidatures Total", width="small", format="%d"),
                "CANDIDATURES VŒUX 1": st.column_config.NumberColumn("Vœux 1", width="small", format="%d"),
                "PROFILS DE METIER / CANDIDAT (Vœux 1)": st.column_config.TextColumn("Détail Vœux 1", width="large"),
                "CANDIDATURES VŒUX 2": st.column_config.NumberColumn("Vœux 2", width="small", format="%d"),
                "PROFILS DE METIER / CANDIDAT (Vœux 2)": st.column_config.TextColumn("Détail Vœux 2", width="large"),
                # ... vous pouvez continuer la config pour 3 et 4 si besoin
            }
        )
        
        st.divider()
        
        
        # ===== EXPORT EXCEL =====
        st.subheader("📥 Export Excel")

        col_export1, col_export2 = st.columns([3, 1])

        with col_export1:
            # ✅ AFFICHAGE CONDITIONNEL DU MESSAGE
            if filtres_actifs:
                st.info("💡 Le fichier exporté contiendra les données **filtrées** affichées dans le tableau ci-dessus.")

        with col_export2:
            paris_tz = pytz.timezone('Europe/Paris')
            export_time = datetime.now(paris_tz)
            filename = f"EDL voeux CAP25 - {export_time.strftime('%d-%m-%Y %Hh%M')}.xlsx"
    
            excel_data = to_excel(df_filtered_agg)
    
            st.download_button(
                label="📥 Télécharger en Excel",
                data=excel_data,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
            
# ========================================
# PAGE 5 : ANALYSE PAR POSTE
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
            nom_collab = get_safe_value(collab.get('NOM', ''))
            prenom_collab = get_safe_value(collab.get('Prénom', ''))
            poste_actuel_collab = get_safe_value(collab.get('Poste libellé', ''))  # Bien noter le double espace
            
            voeu_match = None  # Variable pour capter quel vœu correspond
            
            if collab.get("Vœux 1") == poste:
                voeu_match = "V1"
            elif collab.get("Vœux 2") == poste:
                voeu_match = "V2"
            elif collab.get("Voeux 3") == poste:
                voeu_match = "V3"
            
            if voeu_match:
                # Format enrichi : NOM Prénom (Vx) - Actuellement : 'Poste libellé'
                if poste_actuel_collab:
                    candidat_label = f"{nom_collab} {prenom_collab} ({voeu_match}) - Actuellement : \"{poste_actuel_collab}\""
                else:
                    candidat_label = f"{nom_collab} {prenom_collab} ({voeu_match}) - Actuellement : \"N/A\""
                
                candidats.append(candidat_label)
                candidats_data.append({
                    "nom": f"{nom_collab} {prenom_collab}",
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
            "Postes totaux": nb_postes_total,  # ✅ NOUVELLE COLONNE
            "Ouverts mobilité": nb_postes_disponibles,  # ✅ RENOMMÉ
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
                "Poste": st.column_config.TextColumn("Poste", width="large"),
                "Direction": st.column_config.TextColumn("Direction", width="medium"),
                "Postes totaux": st.column_config.NumberColumn(
                    "Postes totaux",
                    format="%d",
                    width="small",
                    help="Nombre total de postes du référentiel"
                ),
                "Ouverts mobilité": st.column_config.NumberColumn(
                    "Ouverts mobilité",
                    format="%d",
                    width="small",
                    help="Postes disponibles (Total - Attribués)"
                ),
                "Postes attribués": st.column_config.NumberColumn(
                    "Attribués",
                    format="%d",
                    width="small"
                ),
                "Nb_Candidats": st.column_config.NumberColumn(
                    "Candidats",
                    format="%d",
                    width="small"
                ),
                "Candidats": st.column_config.TextColumn("Détail candidats", width="large"),
                "Statut": st.column_config.TextColumn("Statut", width="medium")
            }
        )

        # ✅ CSS POUR COULEURS DE FOND
        st.markdown("""
        <style>
        /* Colonne "Ouverts mobilité" en rose */
        [data-testid="stDataFrame"] tbody tr td:nth-child(4) {
            background-color: rgba(234, 43, 94, 0.15) !important;
            font-weight: 600;
        }
        /* Colonne "Postes attribués" en vert */
        [data-testid="stDataFrame"] tbody tr td:nth-child(5) {
            background-color: rgba(0, 175, 152, 0.15) !important;
            font-weight: 600;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # ✅ MODULE EXPORT EXCEL
        st.subheader("📥 Export du tableau")
        
        filtres_actifs_analyse = show_zero or bool(filtre_direction_analyse) or bool(filtre_statut)
        
        col_export_a1, col_export_a2 = st.columns([3, 1])
        
        with col_export_a1:
            if filtres_actifs_analyse:
                st.info("💡 Le fichier exporté contiendra les données **filtrées** affichées dans le tableau ci-dessus.")
        
        with col_export_a2:
            excel_analyse = to_excel(df_filtered_analysis.drop(columns=["Candidats_Data"]))
            
            st.download_button(
                label="📥 Télécharger en Excel",
                data=excel_analyse,
                file_name=f"Analyse_Viviers_Postes_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
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
                                
                                st.markdown(f"**Matricule** : {matricule if matricule else '/'}")
                                st.markdown(f"**Nom** : {nom} {prenom}")
                                st.markdown(f"**Mail** : {mail if mail else '/'}")
                            
                            with col_info2:
                                poste_actuel = get_safe_value(collab.get('Poste libellé', ''))
                                direction = get_safe_value(collab.get('Direction libellé', ''))
                                date_entree = get_safe_value(collab.get("Date entrée groupe", ""))
                                anciennete_display = calculate_anciennete(date_entree)
    
                                st.markdown(f"**Poste actuel** : {poste_actuel if poste_actuel else '/'}")
                                st.markdown(f"**Direction** : {direction if direction else '/'}")
                                st.markdown(f"**Ancienneté** : {anciennete_display}")

                            with col_info3:
                                rrh = get_safe_value(collab.get('Référente RH', ''))
                                date_rdv = get_safe_value(collab.get('Date de rdv', ''))
                                priorite = get_safe_value(collab.get('Priorité', ''))
    
                                st.markdown(f"**RRH** : {rrh if rrh else '/'}")
                                st.markdown(f"**Date RDV** : {date_rdv if date_rdv else '/'}")
                                st.markdown(f"**Priorité** : {priorite if priorite else '/'}")
                        
                        # Afficher les vœux du candidat
                        st.markdown("##### 🎯 Vœux du candidat")
                        voeux_col1, voeux_col2, voeux_col3 = st.columns(3)
                        
                        voeu1_cand = get_safe_value(collab.get('Vœux 1', ''))
                        voeu2_cand = get_safe_value(collab.get('Vœux 2', ''))
                        voeu3_cand = get_safe_value(collab.get('Voeux 3', ''))
                        
                        with voeux_col1:
                            st.markdown(f"**Vœu 1** : {voeu1_cand if voeu1_cand else '/'}")
                        with voeux_col2:
                            st.markdown(f"**Vœu 2** : {voeu2_cand if voeu2_cand and voeu2_cand != 'Positionnement manquant' else '/'}")
                        with voeux_col3:
                            st.markdown(f"**Vœu 3** : {voeu3_cand if voeu3_cand and voeu3_cand != 'Positionnement manquant' else '/'}")
                        
                        st.divider()
                        
                        if st.button("➡️ Accéder à l'entretien RH complet", type="secondary"):
                            st.session_state['selected_collaborateur'] = candidat_selected
                            st.session_state['navigate_to_entretien'] = True
                            st.rerun()
            else:
                st.info("Aucun candidat pour ce poste")
    else:
        st.info("Aucun poste ne correspond aux filtres sélectionnés")

# ========================================
# PAGE 6 : RÉFÉRENTIEL POSTES
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
        width="stretch",
        hide_index=True
    )

# ========================================
# PAGE 7 : ORGANIGRAMME CAP 2025 
# ========================================


elif page == "🏛️ Organigramme Cap25":
    st.title("🏛️ Organigramme CAP 2025 - Transition Organisationnelle")
    
    st.markdown("""
    Cette page présente la transition entre l'organisation actuelle et la nouvelle organisation CAP 2025.
    Vous pouvez visualiser les structures, comparer les effectifs et analyser les flux de mobilité.
    """)
    
    # Onglets pour différentes vues
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Vue d'ensemble",
        "🔄 Flux de mobilité",
        "📈 Comparaison détaillée",
        "👥 Mouvements individuels"
    ])
    
    # ========================================
    # TAB 1 : VUE D'ENSEMBLE
    # ========================================
    
    with tab1:
        st.subheader("📊 Vue d'ensemble de la transition")
        
        # KPIs de transition
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        
        # Calculer les statistiques
        total_collab = len(collaborateurs_df)
        avec_voeu = collaborateurs_df[
            collaborateurs_df['Vœux Retenu'].notna() & 
            (collaborateurs_df['Vœux Retenu'] != '')
        ].shape[0]
        
        # Créer le mapping Poste → Direction
        poste_to_direction = {}
        if not postes_df.empty:
            for _, poste_row in postes_df.iterrows():
                poste_name = get_safe_value(poste_row.get('Poste', ''))
                direction_name = get_safe_value(poste_row.get('Direction', ''))
                if poste_name:
                    poste_to_direction[poste_name] = direction_name
        
        # Collaborateurs changeant de direction
        df_with_voeu = collaborateurs_df[
            collaborateurs_df['Vœux Retenu'].notna() & 
            (collaborateurs_df['Vœux Retenu'] != '')
        ].copy()
        
        df_with_voeu['Direction_Cible'] = df_with_voeu['Vœux Retenu'].map(poste_to_direction)
        changement_direction = (df_with_voeu['Direction libellé'] != df_with_voeu['Direction_Cible']).sum()
        
        # Postes concernés
        postes_actuels = set(collaborateurs_df['Poste libellé'].dropna().unique())
        postes_cibles = set(df_with_voeu['Vœux Retenu'].dropna().unique())
        nb_postes_impactes = len(postes_actuels | postes_cibles)
        
        with col_kpi1:
            st.metric(
                "👥 Collaborateurs en transition",
                f"{avec_voeu}",
                f"{(avec_voeu/total_collab*100):.1f}% du total"
            )
        
        with col_kpi2:
            st.metric(
                "🔄 Changements de direction",
                f"{changement_direction}",
                f"{(changement_direction/avec_voeu*100 if avec_voeu > 0 else 0):.1f}%"
            )
        
        with col_kpi3:
            nb_directions_actuelles = collaborateurs_df['Direction libellé'].nunique()
            nb_directions_cibles = df_with_voeu['Direction_Cible'].nunique() if len(df_with_voeu) > 0 else 0
            st.metric(
                "🏢 Directions",
                f"{nb_directions_actuelles} → {nb_directions_cibles}",
                f"{nb_directions_cibles - nb_directions_actuelles:+d}"
            )
        
        with col_kpi4:
            st.metric(
                "🎯 Postes impactés",
                f"{nb_postes_impactes}",
                "dans la transition"
            )
        
        st.divider()
        
        # Treemaps côte à côte
        col_tree1, col_tree2 = st.columns(2)
        
        with col_tree1:
            st.subheader("🏢 Organisation Actuelle")
            org_actuelle = create_org_structure(collaborateurs_df, postes_df, mode="actuel")
            fig_actuelle = create_treemap(org_actuelle, "Structure Actuelle")
            st.plotly_chart(fig_actuelle, use_container_width=True)
        
        with col_tree2:
            st.subheader("🎯 Organisation CAP 2025")
            org_cap2025 = create_org_structure(collaborateurs_df, postes_df, mode="cap2025")
            fig_cap2025 = create_treemap(org_cap2025, "Structure CAP 2025")
            st.plotly_chart(fig_cap2025, use_container_width=True)
    
    # ========================================
    # TAB 2 : FLUX DE MOBILITÉ
    # ========================================
    
    with tab2:
        st.subheader("🔄 Visualisation des flux de mobilité")
        
        st.info("💡 Ce diagramme Sankey montre les mouvements des collaborateurs de leur poste actuel vers leur poste CAP 2025 (Vœux Retenu)")
        
        # Filtres pour le Sankey
        col_s1, col_s2 = st.columns(2)
        
        with col_s1:
            direction_filter_sankey = st.multiselect(
                "Filtrer par Direction actuelle",
                options=sorted(collaborateurs_df['Direction libellé'].dropna().unique()),
                default=[]
            )
        
        with col_s2:
            min_flux = st.slider(
                "Afficher uniquement les flux d'au moins X personnes",
                min_value=1,
                max_value=10,
                value=1
            )
        
        # Appliquer les filtres
        df_sankey = collaborateurs_df.copy()
        if direction_filter_sankey:
            df_sankey = df_sankey[df_sankey['Direction libellé'].isin(direction_filter_sankey)]
        
        # Créer et afficher le Sankey
        fig_sankey = create_sankey_diagram(df_sankey, postes_df)
        st.plotly_chart(fig_sankey, use_container_width=True)
        
        st.divider()
        
        # Analyse des flux principaux
        st.subheader("📊 Top 10 des flux de mobilité")
        
        flux_analysis = []
        df_flux_temp = df_sankey[df_sankey['Vœux Retenu'].notna() & (df_sankey['Vœux Retenu'] != '')].copy()
        
        for _, row in df_flux_temp.iterrows():
            poste_actuel = get_safe_value(row.get('Poste libellé', ''))
            voeu_retenu = get_safe_value(row.get('Vœux Retenu', ''))
            
            if voeu_retenu:
                flux_analysis.append({
                    'Poste Actuel': poste_actuel,
                    'Poste CAP 2025': voeu_retenu,
                    'Collaborateur': f"{get_safe_value(row.get('NOM', ''))} {get_safe_value(row.get('Prénom', ''))}"
                })
        
        df_flux = pd.DataFrame(flux_analysis)
        if not df_flux.empty:
            flux_counts = df_flux.groupby(['Poste Actuel', 'Poste CAP 2025']).size().reset_index(name='Nombre')
            flux_counts = flux_counts[flux_counts['Nombre'] >= min_flux]
            flux_counts = flux_counts.sort_values('Nombre', ascending=False).head(10)
            
            st.dataframe(
                flux_counts,
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Aucun flux de mobilité avec les filtres sélectionnés")
    
    # ========================================
    # TAB 3 : COMPARAISON DÉTAILLÉE
    # ========================================
    
    with tab3:
        st.subheader("📈 Comparaison détaillée par Direction")
        
        # Sélection de la direction à analyser
        directions_list = sorted(collaborateurs_df['Direction libellé'].dropna().unique())
        direction_selected = st.selectbox(
            "Sélectionner une Direction",
            options=directions_list
        )
        
        if direction_selected:
            # Créer le mapping Poste → Direction
            poste_to_direction = {}
            if not postes_df.empty:
                for _, poste_row in postes_df.iterrows():
                    poste_name = get_safe_value(poste_row.get('Poste', ''))
                    direction_name = get_safe_value(poste_row.get('Direction', ''))
                    if poste_name:
                        poste_to_direction[poste_name] = direction_name
            
            # Effectifs actuels
            effectif_actuel = collaborateurs_df[collaborateurs_df['Direction libellé'] == direction_selected].shape[0]
            
            # Effectifs cibles (personnes voulant venir dans cette direction)
            df_with_voeu_comp = collaborateurs_df[
                collaborateurs_df['Vœux Retenu'].notna() & 
                (collaborateurs_df['Vœux Retenu'] != '')
            ].copy()
            df_with_voeu_comp['Direction_Cible'] = df_with_voeu_comp['Vœux Retenu'].map(poste_to_direction)
            effectif_cible = df_with_voeu_comp[df_with_voeu_comp['Direction_Cible'] == direction_selected].shape[0]
            
            # Flux sortants (personnes partant de cette direction)
            effectif_sortant = df_with_voeu_comp[
                (df_with_voeu_comp['Direction libellé'] == direction_selected) &
                (df_with_voeu_comp['Direction_Cible'] != direction_selected)
            ].shape[0]
            
            # Flux entrants (personnes venant d'autres directions)
            effectif_entrant = df_with_voeu_comp[
                (df_with_voeu_comp['Direction libellé'] != direction_selected) &
                (df_with_voeu_comp['Direction_Cible'] == direction_selected)
            ].shape[0]
            
            # Affichage des métriques
            col_comp1, col_comp2, col_comp3, col_comp4 = st.columns(4)
            
            with col_comp1:
                st.metric(
                    "👥 Effectif Actuel",
                    f"{effectif_actuel}",
                    help="Nombre de collaborateurs actuellement dans cette direction"
                )
            
            with col_comp2:
                st.metric(
                    "🎯 Effectif CAP 2025",
                    f"{effectif_cible}",
                    f"{effectif_cible - effectif_actuel:+d}",
                    help="Nombre de collaborateurs ciblant cette direction (Vœux Retenu)"
                )
            
            with col_comp3:
                st.metric(
                    "📤 Flux Sortants",
                    f"{effectif_sortant}",
                    help="Collaborateurs quittant cette direction"
                )
            
            with col_comp4:
                st.metric(
                    "📥 Flux Entrants",
                    f"{effectif_entrant}",
                    help="Collaborateurs rejoignant cette direction"
                )
            
            st.divider()
            
            # Détail des mouvements
            col_det1, col_det2 = st.columns(2)
            
            with col_det1:
                st.markdown("##### 📤 Collaborateurs sortants")
                df_sortants = df_with_voeu_comp[
                    (df_with_voeu_comp['Direction libellé'] == direction_selected) &
                    (df_with_voeu_comp['Direction_Cible'] != direction_selected)
                ][['NOM', 'Prénom', 'Poste libellé', 'Vœux Retenu', 'Direction_Cible']]
                
                if not df_sortants.empty:
                    st.dataframe(
                        df_sortants.rename(columns={
                            'NOM': 'Nom',
                            'Poste libellé': 'Poste actuel',
                            'Vœux Retenu': 'Poste cible',
                            'Direction_Cible': 'Direction cible'
                        }),
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("Aucun flux sortant")
            
            with col_det2:
                st.markdown("##### 📥 Collaborateurs entrants")
                df_entrants = df_with_voeu_comp[
                    (df_with_voeu_comp['Direction libellé'] != direction_selected) &
                    (df_with_voeu_comp['Direction_Cible'] == direction_selected)
                ][['NOM', 'Prénom', 'Direction libellé', 'Poste libellé', 'Vœux Retenu']]
                
                if not df_entrants.empty:
                    st.dataframe(
                        df_entrants.rename(columns={
                            'NOM': 'Nom',
                            'Direction libellé': 'Direction actuelle',
                            'Poste libellé': 'Poste actuel',
                            'Vœux Retenu': 'Poste cible'
                        }),
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("Aucun flux entrant")
            
            st.divider()
            
            # Analyse de la capacité des postes
            st.markdown("##### 📊 Analyse de la capacité des postes cibles")
            
            # Récupérer tous les postes ciblés dans cette direction
            postes_cibles_direction = df_with_voeu_comp[
                df_with_voeu_comp['Direction_Cible'] == direction_selected
            ]['Vœux Retenu'].value_counts()
            
            if not postes_cibles_direction.empty:
                capacity_data = []
                for poste, demande in postes_cibles_direction.items():
                    capacite = get_poste_capacity(postes_df, poste)
                    
                    if capacite is not None:
                        taux_remplissage = (demande / capacite * 100) if capacite > 0 else 0
                        status = "✅ OK" if demande <= capacite else "⚠️ Surdemande"
                    else:
                        taux_remplissage = None
                        status = "❓ Capacité non définie"
                    
                    capacity_data.append({
                        'Poste': poste,
                        'Demande': demande,
                        'Capacité': capacite if capacite is not None else "Non définie",
                        'Taux': f"{taux_remplissage:.0f}%" if taux_remplissage is not None else "N/A",
                        'Statut': status
                    })
                
                df_capacity = pd.DataFrame(capacity_data)
                df_capacity = df_capacity.sort_values('Demande', ascending=False)
                
                st.dataframe(
                    df_capacity,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Demande": st.column_config.NumberColumn(format="%d"),
                        "Statut": st.column_config.TextColumn(width="medium")
                    }
                )
            else:
                st.info("Aucun poste ciblé dans cette direction")
    
    # ========================================
    # TAB 4 : MOUVEMENTS INDIVIDUELS
    # ========================================
    
    with tab4:
        st.subheader("👥 Analyse des mouvements individuels")
        
        # Filtres
        col_mv1, col_mv2, col_mv3, col_mv4 = st.columns(4)
        
        # Créer le mapping Poste → Direction pour les filtres
        poste_to_direction = {}
        if not postes_df.empty:
            for _, poste_row in postes_df.iterrows():
                poste_name = get_safe_value(poste_row.get('Poste', ''))
                direction_name = get_safe_value(poste_row.get('Direction', ''))
                if poste_name:
                    poste_to_direction[poste_name] = direction_name
        
        with col_mv1:
            type_mouvement = st.selectbox(
                "Type de mouvement",
                ["Tous", "Changement de direction", "Même direction", "Sans positionnement"]
            )
        
        with col_mv2:
            search_nom = st.text_input("🔍 Rechercher par nom")
        
        with col_mv3:
            filtre_priorite = st.selectbox(
                "Filtrer par priorité",
                ["Toutes", "Priorité 1", "Priorité 2", "Priorité 3", "Priorité 4"]
            )
        
        # Préparer les données
        df_mouvements = collaborateurs_df.copy()
        
        # Ajouter la colonne de direction cible
        df_mouvements['Direction_Cible'] = df_mouvements['Vœux Retenu'].map(poste_to_direction)
        
        # Ajouter le type de mouvement
        def get_type_mouvement(row):
            if pd.isna(row['Vœux Retenu']) or row['Vœux Retenu'] == '':
                return "Sans positionnement"
            elif row['Direction libellé'] != row['Direction_Cible']:
                return "Changement de direction"
            else:
                return "Même direction"
        
        df_mouvements['Type_Mouvement'] = df_mouvements.apply(get_type_mouvement, axis=1)
        
        # Appliquer les filtres
        if type_mouvement != "Tous":
            df_mouvements = df_mouvements[df_mouvements['Type_Mouvement'] == type_mouvement]
        
        if search_nom:
            df_mouvements = df_mouvements[
                df_mouvements['NOM'].str.contains(search_nom, case=False, na=False) |
                df_mouvements['Prénom'].str.contains(search_nom, case=False, na=False)
            ]
        
        if filtre_priorite != "Toutes":
            df_mouvements = df_mouvements[df_mouvements['Priorité'] == filtre_priorite]
        
        # Affichage
        st.markdown(f"**{len(df_mouvements)} collaborateurs** correspondent aux filtres")
        
        # Tableau détaillé
        df_display = df_mouvements[[
            'Matricule', 'NOM', 'Prénom', 
            'Direction libellé', 'Service libellé', 'Poste libellé',
            'Vœux Retenu', 'Direction_Cible', 'Type_Mouvement', 'Priorité', 'Date de rdv'
        ]].copy()
        
        df_display = df_display.rename(columns={
            'NOM': 'Nom',
            'Direction libellé': 'Direction actuelle',
            'Service libellé': 'Service actuel',
            'Poste libellé': 'Poste actuel',
            'Vœux Retenu': 'Poste cible',
            'Direction_Cible': 'Direction cible',
            'Type_Mouvement': 'Type de mouvement',
            'Date de rdv': 'Date RDV'
        })
        
        st.dataframe(
            df_display,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Type de mouvement": st.column_config.TextColumn(
                    width="medium",
                ),
                "Priorité": st.column_config.TextColumn(
                    width="small",
                )
            }
        )
        
        # Export
        st.divider()
        
        col_exp1, col_exp2 = st.columns([3, 1])
        
        with col_exp1:
            st.info("💡 Exportez la liste filtrée pour un suivi détaillé de la transition")
        
        with col_exp2:
            excel_mouvements = to_excel(df_display)
            st.download_button(
                label="📥 Télécharger en Excel",
                data=excel_mouvements,
                file_name=f"Mouvements_CAP2025_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )


# ========================================
# PAGE : COMMISSION RH
# ========================================
elif page == "🚀✨ Commission RH":
    st.title("🎯 Commission RH - Vue Consolidée pour Décisions")
    st.markdown("""
    Cette page offre une vue complète pour les décisions de la commission RH :
    - **Analyse par poste** : quota, retenus, candidats en attente
    - **Gestion des quotas** : identification des postes saturés
    - **Repositionnement** : candidats à rediriger vers d'autres vœux
    """)

    st.divider()

    # --- PRÉPARATION DES DONNÉES (FIABILISATION) ---
    v1_clean = collaborateurs_df['Vœux 1'].fillna('').astype(str).str.strip()
    v2_clean = collaborateurs_df['Vœux 2'].fillna('').astype(str).str.strip()
    v3_clean = collaborateurs_df['Voeux 3'].fillna('').astype(str).str.strip()
    v4_clean = collaborateurs_df['Voeux 4'].fillna('').astype(str).str.strip()

    # Calcul des KPIs globaux pour la transformation
    total_postes_ouverts = int(postes_df[postes_df["Mobilité interne"].str.lower() == "oui"]["Nombre total de postes"].sum())
    nb_collaborateurs_retenus = len(collaborateurs_df[collaborateurs_df['Vœux Retenu'].notna() & (collaborateurs_df['Vœux Retenu'] != '')])
    taux_postes_pourvus = (nb_collaborateurs_retenus / total_postes_ouverts * 100) if total_postes_ouverts > 0 else 0

    # --- AFFICHAGE DES CARTES KPI (TRANSFORMATION) ---
    st.subheader("📊 Indicateurs de Performance de la Transformation")
    
    st.markdown("""
    <style>
    .kpi-card { background-color: white; padding: 24px; border-radius: 12px; border-left: 5px solid #4F46E5; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); margin-bottom: 20px; }
    .kpi-title { color: #6B7280; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
    .kpi-value { color: #111827; font-size: 2.2rem; font-weight: 800; line-height: 1; }
    .kpi-subtitle { color: #9CA3AF; font-size: 0.85rem; margin-top: 8px; font-weight: 500; }
    </style>
    """, unsafe_allow_html=True)

    def render_kpi(title, value, subtitle, color="#4F46E5"):
        return f"""
        <div class="kpi-card" style="border-left-color: {color};">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-subtitle">{subtitle}</div>
        </div>
        """

    col_k1, col_k2, col_k3 = st.columns(3)
    with col_k1:
        st.markdown(render_kpi("Taux Postes Pourvus", f"{taux_postes_pourvus:.1f}%", f"{nb_collaborateurs_retenus} affectations / {total_postes_ouverts}", "#4F46E5"), unsafe_allow_html=True)
    with col_k2:
        postes_vacants = total_postes_ouverts - nb_collaborateurs_retenus
        st.markdown(render_kpi("Postes Restants", f"{postes_vacants}", "Postes sans affectation validée", "#10B981"), unsafe_allow_html=True)
    with col_k3:
        nb_candidats_actifs = len(collaborateurs_df[collaborateurs_df['Vœux Retenu'].isna() | (collaborateurs_df['Vœux Retenu'] == '')])
        st.markdown(render_kpi("Collaborateurs à placer", f"{nb_candidats_actifs}", "Candidats en attente de décision", "#F59E0B"), unsafe_allow_html=True)

    st.divider()

    # --- SECTION TABLEAU DE COMMISSION ---
    st.subheader("📋 Tableau de Commission - Vue par Poste")

    # --- ZONE DES FILTRES ---
    st.markdown("##### 🔍 Filtres")
    col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)

    with col_f1:
        directions_list = sorted(postes_df["Direction"].unique())
        filtre_direction_commission = st.multiselect("Direction", options=directions_list, key="dir_comm")

    with col_f2:
        postes_ouverts_df = postes_df[postes_df["Mobilité interne"].str.lower() == "oui"]
        postes_filtres_liste = sorted(postes_ouverts_df[postes_ouverts_df["Direction"].isin(filtre_direction_commission)]["Poste"].unique()) if filtre_direction_commission else sorted(postes_ouverts_df["Poste"].unique())
        filtre_poste_commission = st.multiselect("Poste", options=postes_filtres_liste, key="poste_comm")

    with col_f3:
        filtre_priorite_commission = st.multiselect("Priorité", options=["Priorité 1", "Priorité 2", "Priorité 3", "Priorité 4"], key="prio_comm")

    with col_f4:
        filtre_voeu_commission = st.multiselect("N° de Vœu", options=["Vœu 1", "Vœu 2", "Vœu 3", "Vœu 4"], key="voeu_comm")

    with col_f5:
        filtre_statut_commission = st.multiselect("Statut Poste", options=["🟢 POURVU 💯", "⚠️ Poste totalement vacant", "🟠 Presque pourvu", "🔴 Disponible"], key="statut_comm")

    # --- CONSTRUCTION DES DONNÉES DU TABLEAU ---
    commission_data = []

    for _, poste_row in postes_df[postes_df["Mobilité interne"].str.lower() == "oui"].iterrows():
        poste_name = poste_row["Poste"]
        direction = poste_row["Direction"]
        quota = int(poste_row.get("Nombre total de postes", 0))

        if filtre_direction_commission and direction not in filtre_direction_commission: continue
        if filtre_poste_commission and poste_name not in filtre_poste_commission: continue

        retenus_df = collaborateurs_df[collaborateurs_df['Vœux Retenu'] == poste_name]
        nb_retenus = len(retenus_df)
        liste_retenus = [f"{get_safe_value(ret.get('Prénom', ''))} {get_safe_value(ret.get('NOM', ''))}" for _, ret in retenus_df.iterrows()]

        candidats_v1, candidats_v2, candidats_v3, candidats_v4 = [], [], [], []
        
        for _, collab in collaborateurs_df.iterrows():
            if get_safe_value(collab.get('Vœux Retenu', '')): continue 
            
            nom_complet = f"{get_safe_value(collab.get('Prénom', ''))} {get_safe_value(collab.get('NOM', ''))}"
            prio = get_safe_value(collab.get('Priorité', ''))
            mat = get_safe_value(collab.get('Matricule', ''))

            if filtre_priorite_commission and prio not in filtre_priorite_commission: continue

            c_info = {'nom': nom_complet, 'priorite': prio, 'matricule': mat}
            
            if get_safe_value(collab.get('Vœux 1', '')) == poste_name: candidats_v1.append(c_info)
            if get_safe_value(collab.get('Vœux 2', '')) == poste_name: candidats_v2.append(c_info)
            if get_safe_value(collab.get('Voeux 3', '')) == poste_name: candidats_v3.append(c_info)
            if get_safe_value(collab.get('Voeux 4', '')) == poste_name: candidats_v4.append(c_info)

        # Détermination du Statut
        places_restantes = quota - nb_retenus
        if nb_retenus >= quota: statut = "🟢 POURVU 💯"
        elif nb_retenus == 0: statut = "⚠️ Poste totalement vacant"
        elif places_restantes <= 2: statut = "🟠 Presque pourvu"
        else: statut = "🔴 Disponible"

        format_names = lambda l: "; ".join([c['nom'] for c in l])

        commission_data.append({
            "Statut": statut,
            "Poste": poste_name,
            "Direction": direction,
            "Quota": quota,
            "Retenus": nb_retenus,
            "Places": places_restantes,
            "Liste des retenus": "; ".join(liste_retenus),
            "V1": len(candidats_v1),
            "Candidats V1": format_names(candidats_v1),
            "V2": len(candidats_v2),
            "Candidats V2": format_names(candidats_v2),
            "V3": len(candidats_v3),
            "Candidats V3": format_names(candidats_v3),
            "V4": len(candidats_v4),
            "Candidats V4": format_names(candidats_v4),
            "Candidats_V1_Data": candidats_v1,
            "Candidats_V2_Data": candidats_v2,
            "Candidats_V3_Data": candidats_v3,
            "Candidats_V4_Data": candidats_v4
        })

    df_commission = pd.DataFrame(commission_data)

    if not df_commission.empty:
        if filtre_statut_commission:
            df_commission = df_commission[df_commission['Statut'].isin(filtre_statut_commission)]

        if not df_commission.empty:
            ordre_statut = {"🟢 POURVU 💯": 1, "🟠 Presque pourvu": 2, "🔴 Disponible": 3, "⚠️ Poste totalement vacant": 4}
            df_commission['_ordre'] = df_commission['Statut'].map(ordre_statut)
            df_commission = df_commission.sort_values(['_ordre', 'Direction', 'Poste']).drop(columns=['_ordre'])

            st.dataframe(
                df_commission.drop(columns=['Candidats_V1_Data', 'Candidats_V2_Data', 'Candidats_V3_Data', 'Candidats_V4_Data']),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Statut": st.column_config.TextColumn("Statut", width="small"),
                    "Poste": st.column_config.TextColumn("Poste", width="medium"),
                    "Liste des retenus": st.column_config.TextColumn("Collaborateurs retenus", width="medium"),
                    "V1": st.column_config.NumberColumn("Nb V1", width="micro"),
                    "Candidats V1": st.column_config.TextColumn("Détail V1", width="medium"),
                    "V2": st.column_config.NumberColumn("Nb V2", width="micro"),
                    "Candidats V2": st.column_config.TextColumn("Détail V2", width="medium"),
                    "V3": st.column_config.NumberColumn("Nb V3", width="micro"),
                    "Candidats V3": st.column_config.TextColumn("Détail V3", width="medium"),
                    "V4": st.column_config.NumberColumn("Nb V4", width="micro"),
                    "Candidats V4": st.column_config.TextColumn("Détail V4", width="medium"),
                }
            )

            # --- SECTION 3 : REPOSITIONNER ---
            st.divider()
            st.subheader("🔄 Candidats à Repositionner (Postes saturés)")
            
            candidats_a_repositionner = []
            for _, row_comm in df_commission.iterrows():
                if row_comm['Statut'] == "🟢 POURVU 💯":
                    p_sature = row_comm['Poste']
                    for label, key in [("Vœu 1", 'Candidats_V1_Data'), ("Vœu 2", 'Candidats_V2_Data'), ("Vœu 3", 'Candidats_V3_Data'), ("Vœu 4", 'Candidats_V4_Data')]:
                        for cand in row_comm[key]:
                            candidats_a_repositionner.append({
                                'Nom': cand['nom'],
                                'Poste saturé': p_sature,
                                'Vœu bloqué': label,
                                'Priorité': cand['priorite'],
                                'Matricule': cand['matricule']
                            })

            if candidats_a_repositionner:
                df_repo = pd.DataFrame(candidats_a_repositionner)
                df_repo['Vœux alternatifs'] = df_repo.apply(lambda r: get_voeux_alternatifs(collaborateurs_df, r['Matricule'], r['Vœu bloqué']), axis=1)
                st.warning(f"⚠️ **{len(df_repo)} candidat(s)** à repositionner car leur vœu cible un poste saturé")
                st.dataframe(df_repo.drop(columns=['Matricule']), use_container_width=True, hide_index=True)
            else:
                st.success("✅ Aucun candidat à repositionner")
        else:
            st.info("Aucun poste ne correspond aux filtres de statut.")
    else:
        st.info("Aucun poste ne correspond aux filtres sélectionnés.")
    
# ========================================
    # SECTION 4 : SUIVI DES ENTRETIENS (AVEC KPIs)
    # ========================================

    st.markdown("---")
    st.subheader("🗓️ Suivi des Entretiens RH")

    # --- Filtres ---
    col_ent1, col_ent2 = st.columns([2, 1])

    with col_ent1:
        filtre_direction_entretien = st.multiselect(
            "📍 Filtrer par Direction",
            options=sorted(collaborateurs_df['Direction libellé'].dropna().unique()),
            default=[],
            key="filtre_dir_entretien"
        )

    with col_ent2:
        statut_entretien = st.selectbox(
            "🚥 Statut de l'entretien",
            options=["Tous", "À venir", "Réalisés", "Aujourd'hui"],
            key="statut_entretien"
        )

    # --- Préparation des données ---
    df_entretiens_all = collaborateurs_df.copy()

    # Appliquer le filtre de direction pour les KPIs
    if filtre_direction_entretien:
        df_entretiens_kpi = df_entretiens_all[df_entretiens_all['Direction libellé'].isin(filtre_direction_entretien)]
    else:
        df_entretiens_kpi = df_entretiens_all.copy()

    today = datetime.now().date()

    # Calcul des indicateurs
    total_entretiens = 0
    entretiens_a_venir = 0
    entretiens_realises = 0
    entretiens_aujourd_hui = 0

    for _, row in df_entretiens_kpi.iterrows():
        date_rdv = parse_date(get_safe_value(row.get('Date de rdv', '')))
        if date_rdv:
            total_entretiens += 1
            if date_rdv > today:
                entretiens_a_venir += 1
            elif date_rdv < today:
                entretiens_realises += 1
            elif date_rdv == today:
                entretiens_aujourd_hui += 1

    taux_realises = (entretiens_realises / total_entretiens * 100) if total_entretiens > 0 else 0

    # --- Affichage des KPIs Harmonisés ---
    st.markdown(f"##### 📊 Tableau de bord des entretiens {' - ' + ', '.join(filtre_direction_entretien) if filtre_direction_entretien else ''}")

    col_k1, col_k2, col_k3, col_k4 = st.columns(4)

    # KPI 1 : Total
    with col_k1:
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); 
                    padding: 20px; border-radius: 12px; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.1);'>
            <h4 style='margin:0; font-size: 0.85rem; opacity: 0.9; font-weight: 400;'>📅 TOTAL</h4>
            <h2 style='margin:10px 0; font-size: 2.2rem; font-weight: 700;'>{total_entretiens}</h2>
            <div style='font-size: 0.8rem; background: rgba(255,255,255,0.2); display: inline-block; padding: 2px 8px; border-radius: 10px;'>Programmé(s)</div>
        </div>
        """, unsafe_allow_html=True)

    # KPI 2 : À Venir
    with col_k2:
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #0ea5e9 0%, #38bdf8 100%); 
                    padding: 20px; border-radius: 12px; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.1);'>
            <h4 style='margin:0; font-size: 0.85rem; opacity: 0.9; font-weight: 400;'>⏳ À VENIR</h4>
            <h2 style='margin:10px 0; font-size: 2.2rem; font-weight: 700;'>{entretiens_a_venir}</h2>
            <div style='font-size: 0.8rem; background: rgba(255,255,255,0.2); display: inline-block; padding: 2px 8px; border-radius: 10px;'>Restant(s)</div>
        </div>
        """, unsafe_allow_html=True)

    # KPI 3 : Réalisés
    with col_k3:
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #10b981 0%, #34d399 100%); 
                    padding: 20px; border-radius: 12px; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.1);'>
            <h4 style='margin:0; font-size: 0.85rem; opacity: 0.9; font-weight: 400;'>✅ RÉALISÉS</h4>
            <h2 style='margin:10px 0; font-size: 2.2rem; font-weight: 700;'>{entretiens_realises}</h2>
            <div style='font-size: 0.8rem; background: rgba(255,255,255,0.2); display: inline-block; padding: 2px 8px; border-radius: 10px;'>Taux : {taux_realises:.0f}%</div>
        </div>
        """, unsafe_allow_html=True)

    # KPI 4 : Aujourd'hui (Urgence)
    bg_today = "linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%)" if entretiens_aujourd_hui > 0 else "linear-gradient(135deg, #94a3b8 0%, #cbd5e1 100%)"
    with col_k4:
        st.markdown(f"""
        <div style='background: {bg_today}; 
                    padding: 20px; border-radius: 12px; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.1);'>
            <h4 style='margin:0; font-size: 0.85rem; opacity: 0.9; font-weight: 400;'>⏰ AUJOURD'HUI</h4>
            <h2 style='margin:10px 0; font-size: 2.2rem; font-weight: 700;'>{entretiens_aujourd_hui}</h2>
            <div style='font-size: 0.8rem; background: rgba(255,255,255,0.2); display: inline-block; padding: 2px 8px; border-radius: 10px;'>Rendez-vous</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Filtrage du tableau de données ---
    df_table = df_entretiens_kpi.copy()

    # Filtrer par statut sélectionné
    if statut_entretien == "À venir":
        df_table = df_table[df_table['Date de rdv'].apply(lambda x: parse_date(x) > today if parse_date(x) else False)]
    elif statut_entretien == "Réalisés":
        df_table = df_table[df_table['Date de rdv'].apply(lambda x: parse_date(x) < today if parse_date(x) else False)]
    elif statut_entretien == "Aujourd'hui":
        df_table = df_table[df_table['Date de rdv'].apply(lambda x: parse_date(x) == today if parse_date(x) else False)]

    # Préparation finale pour affichage
    entretiens_display = []
    for _, row in df_table.iterrows():
        date_val = get_safe_value(row.get('Date de rdv', ''))
        if date_val and date_val.strip() != '':
            entretiens_display.append({
                'Date': date_val,
                'Heure': get_safe_value(row.get('Heure de rdv', '')),
                'Collaborateur': f"{get_safe_value(row.get('Prénom', ''))} {get_safe_value(row.get('NOM', ''))}".upper(),
                'Direction': get_safe_value(row.get('Direction libellé', '')),
                'RRH': get_safe_value(row.get('Référente RH', '')),
                'Vœu Retenu': get_safe_value(row.get('Vœux Retenu', '')),
                'Mail': get_safe_value(row.get('Mail', '')),
                'Priorité': get_safe_value(row.get('Priorité', ''))
            })

    if entretiens_display:
        df_final = pd.DataFrame(entretiens_display).sort_values(by=['Date', 'Heure'])
        
        st.write(f"🔍 **{len(df_final)}** entretien(s) trouvé(s)")
        st.dataframe(
            df_final,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Date": st.column_config.TextColumn("📅 Date"),
                "Heure": st.column_config.TextColumn("🕒 Heure"),
                "Collaborateur": st.column_config.TextColumn("👤 Collaborateur"),
                "Vœu Retenu": st.column_config.TextColumn("🎯 Décision/Vœu"),
                "Priorité": st.column_config.TextColumn("⚡ Prio")
            }
        )
        
        # Export harmonisé
        col_exp1, col_exp2 = st.columns([4, 1])
        with col_exp2:
            excel_data = to_excel(df_final)
            st.download_button(
                label="📥 Exporter la liste (.xlsx)",
                data=excel_data,
                file_name=f"Sherlock_Entretiens_{datetime.now().strftime('%d%m%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    else:
        st.info("ℹ️ Aucun entretien ne correspond à vos critères de recherche.")

# --- FOOTER ---
st.divider()

# 1. Le texte centré en haut
st.markdown("""
<div style='text-align: center; color: #999; font-size: 0.85em; margin-bottom: 20px;'>
    <p>CAP25 - Pilotage de la Mobilité Interne | Synchronisé avec Google Sheets</p>
</div>
""", unsafe_allow_html=True)

# 2. Le saut de ligne (déjà géré par le margin-bottom au-dessus, mais on peut forcer si besoin)
# st.write("") 

# 3. Le logo centré en bas
col_f_left, col_f_logo, col_f_right = st.columns([2, 1, 2])
with col_f_logo:
    st.image("Logo- in'li.png", width=120)














