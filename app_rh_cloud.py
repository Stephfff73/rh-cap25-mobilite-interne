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


def badge_priorite(p):
    colors = {
        "Priorité 1": "🔴",
        "Priorité 2": "🟠",
        "Priorité 3": "🟡",
        "Priorité 4": "🟢"
    }
    return f"{colors.get(p, '⚪')} {p}"


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

# ✅ VÉRIFICATION ET CRÉATION DE LA COLONNE "Vœux Retenu" SI MANQUANTE
if not collaborateurs_df.empty:
    collaborateurs_df.columns = collaborateurs_df.columns.str.strip()
    
    if "Vœux Retenu" not in collaborateurs_df.columns:
        st.sidebar.warning("⚠️ Colonne 'Vœux Retenu' créée automatiquement")
        collaborateurs_df["Vœux Retenu"] = ""

if collaborateurs_df.empty or postes_df.empty:
    st.error("Impossible de charger les données. Vérifiez la structure du Google Sheet.")
    st.stop()

# --- SIDEBAR : NAVIGATION AVEC LOGO ---
st.sidebar.image("Logo- in'li.png", width=250)
st.sidebar.markdown("### 🏢 CAP25 - Mobilité Interne")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigation",
    [
        "📊 Tableau de Bord", 
        "👥 Gestion des Candidatures", 
        "📝 Entretien RH", 
        "💻🔍 Candidatures/Poste",  # NOUVEAU
        "🎯 Analyse par Poste", 
        "🗒️🔁 Tableau agrégé AM",  # ← NOUVEA
        "🌳 Référentiel Postes"
    ],
    label_visibility="collapsed"
)

# Bouton de rafraîchissement
st.sidebar.divider()
if st.sidebar.button("🔄 Rafraîchir les données", width="stretch"):
    st.sidebar.caption("ℹ️ Les données sont mises en cache pendant 1 minute")
    st.sidebar.warning("⚠️ Rafraîchissement en cours...")
    time.sleep(1)
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()
paris_tz = pytz.timezone('Europe/Paris')
paris_time = datetime.now(paris_tz)
st.sidebar.caption(f"Dernière mise à jour : {paris_time.strftime('%H:%M:%S')}")

if st.session_state.last_save_time:
    st.sidebar.caption(f"💾 Dernière sauvegarde : {st.session_state.last_save_time.strftime('%H:%M:%S')}")


# ========================================
# PAGE 1 : TABLEAU DE BORD AMÉLIORÉ
# ========================================

if page == "📊 Tableau de Bord":
    # Titre avec date et heure actuelles
    paris_tz = pytz.timezone('Europe/Paris')
    now = datetime.now(paris_tz)
    
    st.title("📊 Tableau de Bord - Vue d'ensemble")
    st.markdown(f"**📌 Avancement global de la mobilité au {now.strftime('%d/%m/%Y')} à {now.strftime('%H:%M')}**")
    st.divider()
    
    # ===== PREMIÈRE LIGNE : MÉTRIQUES PRINCIPALES =====
    st.subheader("🎯 Indicateurs clés")
    
    # Calculs
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
        
        # Barre de progression améliorée
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
    
    # ===== DEUXIÈME LIGNE : PRIORITÉS =====
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
    
    # ===== TROISIÈME LIGNE : ENTRETIENS =====
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
        st.metric("📅 Entretiens planifiés", entretiens_planifies)
        st.markdown(f"<p style='color: #10b981; font-weight: bold; margin-top: -10px;'>{int(pct_planifies)}% du total</p>", unsafe_allow_html=True)
    
    with col10:
        st.metric("✅ Entretiens réalisés", entretiens_realises)
        st.markdown(f"<p style='color: #10b981; font-weight: bold; margin-top: -10px;'>{int(pct_realises)}% du total</p>", unsafe_allow_html=True)
    
    with col11:
        st.metric("⌛ Aujourd'hui", entretiens_aujourd_hui)
        st.markdown(f"<p style='color: #10b981; font-weight: bold; margin-top: -10px;'>{int(pct_aujourd_hui)}% du total</p>", unsafe_allow_html=True)
    
    st.divider()
    
    # ===== GRAPHIQUES =====
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
                width="stretch",
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
        st.subheader("⚠️ Postes en tension d'attractivité")
        
        if len(all_voeux) > 0:
            flop_postes = all_voeux.value_counts().sort_values(ascending=True).head(10)
            
            flop_df = pd.DataFrame({
                "Classement": range(1, len(flop_postes) + 1),
                "Poste": flop_postes.index,
                "Nombre de vœux": flop_postes.values
            })
            
            st.dataframe(
                flop_df,
                width="stretch",
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
            width="stretch",
            hide_index=True
        )
        
        st.divider()

        st.subheader("📤 Exporter les données")

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
                            st.session_state.entretien_data = {}
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
                    st.markdown(f"**Poste actuel** : {get_safe_value(collab.get('Poste  libellé', 'N/A'))}")
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
                                if st.button("🟢 Oui, vœu retenu", key="btn_retenu", type="primary", width="stretch"):
                                    success = update_voeu_retenu(gsheet_client, SHEET_URL, st.session_state.current_matricule, poste_final)
                                    
                                    if success:
                                        st.session_state.entretien_data["Decision_RH_Poste"] = f"Retenu: {poste_final}"
                                        save_entretien_to_gsheet(gsheet_client, SHEET_URL, st.session_state.entretien_data, show_success=False)
                                        
                                        st.success("✅ Vœu retenu enregistré avec succès !")
                                        time.sleep(2)
                                        st.rerun()
                        
                        st.divider()
                        if st.button("💾 Sauvegarder l'entretien complet", type="primary", width="stretch"):
                            save_entretien_to_gsheet(gsheet_client, SHEET_URL, st.session_state.entretien_data, show_success=True)

# ========================================
# NOUVELLE PAGE : COMPARATIF DES CANDIDATURES PAR POSTE
# ========================================

elif page == "💻 Comparatif des candidatures par Poste":
    st.title("💻 Comparatif des Candidatures par Poste")
    
    st.markdown("""
    Cette page vous permet de comparer côte à côte tous les entretiens RH des candidats pour un poste donné.
    Les candidats sont classés par ordre de vœu (V1 > V2 > V3) puis par ordre alphabétique.
    """)
    
    st.divider()
    
    # Sélection du poste
    postes_list = sorted(postes_df["Poste"].unique())
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
                
                if voeu1 == poste_compare:
                    voeu_match = "Vœu 1"
                    ordre_voeu = 1
                elif voeu2 == poste_compare:
                    voeu_match = "Vœu 2"
                    ordre_voeu = 2
                elif voeu3 == poste_compare:
                    voeu_match = "Vœu 3"
                    ordre_voeu = 3
                
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
                        'poste_actuel': get_safe_value(collab.get('Poste  libellé', '')),
                        'anciennete': calculate_anciennete(get_safe_value(collab.get("Date entrée groupe", ""))),
                        'priorite': get_safe_value(collab.get('Priorité', ''))
                    })
            
            # Trier : d'abord par ordre de vœu, puis par nom
            candidats_data.sort(key=lambda x: (x['ordre_voeu'], x['nom'], x['prenom']))
            
            if len(candidats_data) == 0:
                st.info(f"Aucun candidat n'a émis de vœu pour le poste « {poste_compare} »")
            else:
                st.success(f"**{len(candidats_data)} candidat(s)** trouvé(s) pour ce poste")
                
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
                
                # Bouton d'export CSV
                csv_buffer = io.StringIO()
                df_comparatif.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                excel_data = to_excel(df_comparatif)

                st.download_button(
                    label="📥 Télécharger le comparatif en Excel (.xlsx)",
                    data=excel_data,
                    file_name=f"comparatif_candidatures_{poste_compare.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary", 
                    width="stretch" # Rend le bouton plus imposant et moderne
                )

        
        except Exception as e:
            st.error(f"Erreur lors du chargement des entretiens : {str(e)}")


# ========================================
# NOUVELLE PAGE : TABLEAU AGRÉGÉ POUR ALICE
# ========================================

elif page == "🗒️🔁 Tableau agrégé AM":
    st.title("🗒️🔁 Tableau Agrégé des Vœux - Vue Direction")
    
    st.markdown("""
    Ce tableau synthétise tous les vœux émis par poste avec le détail des profils métiers actuels des candidats.
    Les postes ouverts correspondent au nombre de postes disponibles (total - attribués).
    """)
    
    st.divider()
    
    # ===== CONSTRUCTION DU TABLEAU AGRÉGÉ =====
    aggregated_data = []
    
    for _, poste_row in postes_df.iterrows():
        poste = poste_row.get("Poste", "")
        direction = poste_row.get("Direction", "")
        
        # ✅ CALCUL CORRECT DES POSTES OUVERTS (aligné sur Analyse par Poste)
        nb_postes_total = int(poste_row.get("Nombre total de postes", 1))
        
        # Compter les postes attribués
        nb_postes_attribues = len(collaborateurs_df[
            (collaborateurs_df["Vœux Retenu"] == poste)
        ])
        
        # Calculer les postes disponibles
        postes_ouverts = nb_postes_total - nb_postes_attribues
        
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
            poste_actuel = get_safe_value(collab.get("Poste  libellé", "N/A"))
            
            # Vœu 1
            if get_safe_value(collab.get("Vœux 1", "")) == poste:
                candidatures_v1 += 1
                if poste_actuel in profils_v1:
                    profils_v1[poste_actuel] += 1
                else:
                    profils_v1[poste_actuel] = 1
            
            # Vœu 2
            if get_safe_value(collab.get("Vœux 2", "")) == poste:
                candidatures_v2 += 1
                if poste_actuel in profils_v2:
                    profils_v2[poste_actuel] += 1
                else:
                    profils_v2[poste_actuel] = 1
            
            # Vœu 3
            if get_safe_value(collab.get("Voeux 3", "")) == poste:
                candidatures_v3 += 1
                if poste_actuel in profils_v3:
                    profils_v3[poste_actuel] += 1
                else:
                    profils_v3[poste_actuel] = 1
            
            # Vœu 4
            if get_safe_value(collab.get("Voeux 4", "")) == poste:
                candidatures_v4 += 1
                if poste_actuel in profils_v4:
                    profils_v4[poste_actuel] += 1
                else:
                    profils_v4[poste_actuel] = 1
        
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
        # Carte globale
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 10px;'>
            <h4 style='margin:0; color: white; font-size: 0.9rem; opacity: 0.9;'>📍 Postes Ouverts</h4>
            <h1 style='margin:10px 0; color: white; font-size: 2.5rem;'>{}</h1>
            <p style='margin:0; opacity: 0.8; font-size: 0.85rem;'>📊 Vue globale</p>
        </div>
        """.format(total_postes_ouverts_global), unsafe_allow_html=True)
        
        # Carte filtrée (si filtres actifs)
        if filtres_actifs:
            delta = total_postes_ouverts_filtre - total_postes_ouverts_global
            delta_pct = (total_postes_ouverts_filtre / total_postes_ouverts_global * 100) if total_postes_ouverts_global > 0 else 0
            
            st.markdown("""
            <div style='background: linear-gradient(135deg, #8e9eab 0%, #eef2f3 100%); 
                        padding: 15px; border-radius: 12px; color: #1F2937; text-align: center; border: 2px solid #667eea;'>
                <h4 style='margin:0; color: #667eea; font-size: 0.85rem; font-weight: bold;'>🔍 Vue filtrée</h4>
                <h2 style='margin:10px 0; color: #1F2937; font-size: 1.8rem;'>{}</h2>
                <p style='margin:0; color: #6B7280; font-size: 0.8rem;'>{:.1f}% du total</p>
            </div>
            """.format(total_postes_ouverts_filtre, delta_pct), unsafe_allow_html=True)
    
    # ===== CARTE 2 : CANDIDATURES TOTAL =====
    with col_stat2:
        # Carte globale
        st.markdown("""
        <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                    padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 10px;'>
            <h4 style='margin:0; color: white; font-size: 0.9rem; opacity: 0.9;'>📊 Candidatures</h4>
            <h1 style='margin:10px 0; color: white; font-size: 2.5rem;'>{}</h1>
            <p style='margin:0; opacity: 0.8; font-size: 0.85rem;'>📊 Vue globale</p>
        </div>
        """.format(total_candidatures_global), unsafe_allow_html=True)
        
        # Carte filtrée
        if filtres_actifs:
            delta_pct = (total_candidatures_filtre / total_candidatures_global * 100) if total_candidatures_global > 0 else 0
            
            st.markdown("""
            <div style='background: linear-gradient(135deg, #8e9eab 0%, #eef2f3 100%); 
                        padding: 15px; border-radius: 12px; color: #1F2937; text-align: center; border: 2px solid #f093fb;'>
                <h4 style='margin:0; color: #f5576c; font-size: 0.85rem; font-weight: bold;'>🔍 Vue filtrée</h4>
                <h2 style='margin:10px 0; color: #1F2937; font-size: 1.8rem;'>{}</h2>
                <p style='margin:0; color: #6B7280; font-size: 0.8rem;'>{:.1f}% du total</p>
            </div>
            """.format(total_candidatures_filtre, delta_pct), unsafe_allow_html=True)
    
    # ===== CARTE 3 : MOYENNE CANDIDATURES/POSTE =====
    with col_stat3:
        # Carte globale
        st.markdown("""
        <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); 
                    padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 10px;'>
            <h4 style='margin:0; color: white; font-size: 0.9rem; opacity: 0.9;'>📈 Moyenne</h4>
            <h1 style='margin:10px 0; color: white; font-size: 2.5rem;'>{:.1f}</h1>
            <p style='margin:0; opacity: 0.8; font-size: 0.85rem;'>📊 Vue globale</p>
        </div>
        """.format(avg_cand_global), unsafe_allow_html=True)
        
        # Carte filtrée
        if filtres_actifs:
            delta_avg = avg_cand_filtre - avg_cand_global
            delta_sign = "+" if delta_avg > 0 else ""
            
            st.markdown("""
            <div style='background: linear-gradient(135deg, #8e9eab 0%, #eef2f3 100%); 
                        padding: 15px; border-radius: 12px; color: #1F2937; text-align: center; border: 2px solid #4facfe;'>
                <h4 style='margin:0; color: #00f2fe; font-size: 0.85rem; font-weight: bold;'>🔍 Vue filtrée</h4>
                <h2 style='margin:10px 0; color: #1F2937; font-size: 1.8rem;'>{:.1f}</h2>
                <p style='margin:0; color: #6B7280; font-size: 0.8rem;'>{}{:.1f} vs global</p>
            </div>
            """.format(avg_cand_filtre, delta_sign, delta_avg), unsafe_allow_html=True)
    
    # ===== CARTE 4 : POSTES SANS CANDIDAT =====
    with col_stat4:
        # Carte globale
        st.markdown("""
        <div style='background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); 
                    padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 10px;'>
            <h4 style='margin:0; color: white; font-size: 0.9rem; opacity: 0.9;'>⚠️ Sans Candidat</h4>
            <h1 style='margin:10px 0; color: white; font-size: 2.5rem;'>{}</h1>
            <p style='margin:0; opacity: 0.8; font-size: 0.85rem;'>📊 Vue globale</p>
        </div>
        """.format(postes_sans_candidat_global), unsafe_allow_html=True)
        
        # Carte filtrée
        if filtres_actifs:
            delta_pct = (postes_sans_candidat_filtre / postes_sans_candidat_global * 100) if postes_sans_candidat_global > 0 else 0
            
            st.markdown("""
            <div style='background: linear-gradient(135deg, #8e9eab 0%, #eef2f3 100%); 
                        padding: 15px; border-radius: 12px; color: #1F2937; text-align: center; border: 2px solid #fa709a;'>
                <h4 style='margin:0; color: #fa709a; font-size: 0.85rem; font-weight: bold;'>🔍 Vue filtrée</h4>
                <h2 style='margin:10px 0; color: #1F2937; font-size: 1.8rem;'>{}</h2>
                <p style='margin:0; color: #6B7280; font-size: 0.8rem;'>{:.1f}% du total</p>
            </div>
            """.format(postes_sans_candidat_filtre, delta_pct), unsafe_allow_html=True)
    
    st.divider()
    
    # ===== AFFICHAGE DU TABLEAU =====
    st.subheader(f"📊 {len(df_filtered_agg)} poste(s) affiché(s)")
    
    st.dataframe(
        df_filtered_agg,
        width="stretch",
        hide_index=True,
        column_config={
            "POSTE PROJETE": st.column_config.TextColumn(width="large"),
            "DIRECTION": st.column_config.TextColumn(width="medium"),
            "POSTES OUVERTS": st.column_config.NumberColumn(width="small", format="%d"),
            "CANDIDATURES TOTAL": st.column_config.NumberColumn(width="small", format="%d"),
            "CANDIDATURES VŒUX 1": st.column_config.NumberColumn(width="small", format="%d"),
            "PROFILS DE METIER / CANDIDAT (Vœux 1)": st.column_config.TextColumn(width="large"),
            "CANDIDATURES VŒUX 2": st.column_config.NumberColumn(width="small", format="%d"),
            "PROFILS DE METIER / CANDIDAT (Vœux 2)": st.column_config.TextColumn(width="large"),
            "CANDIDATURES VŒUX 3": st.column_config.NumberColumn(width="small", format="%d"),
            "PROFILS DE METIER / CANDIDAT (Vœux 3)": st.column_config.TextColumn(width="large"),
            "CANDIDATURES VŒUX 4": st.column_config.NumberColumn(width="small", format="%d"),
            "PROFILS DE METIER / CANDIDAT (Vœux 4)": st.column_config.TextColumn(width="large")
        }
    )
    
    st.divider()
    
    # ===== EXPORT EXCEL =====
    st.subheader("📥 Export Excel")
    
    col_export1, col_export2 = st.columns([3, 1])
    
    with col_export1:
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
            width="stretch"
        )

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
            nom_collab = get_safe_value(collab.get('NOM', ''))
            prenom_collab = get_safe_value(collab.get('Prénom', ''))
            poste_actuel_collab = get_safe_value(collab.get('Poste  libellé', ''))  # Bien noter le double espace
            
            voeu_match = None  # Variable pour capter quel vœu correspond
            
            if collab.get("Vœux 1") == poste:
                voeu_match = "V1"
            elif collab.get("Vœux 2") == poste:
                voeu_match = "V2"
            elif collab.get("Voeux 3") == poste:
                voeu_match = "V3"
            
            if voeu_match:
                # Format enrichi : NOM Prénom (Vx) - Actuellement : "Poste libellé"
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
            width="stretch",
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
                ),
                "Candidats": st.column_config.TextColumn(
                    "Candidats",
                    width="large"
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
                                
                                st.markdown(f"**Matricule** : {matricule if matricule else '/'}")
                                st.markdown(f"**Nom** : {nom} {prenom}")
                                st.markdown(f"**Mail** : {mail if mail else '/'}")
                            
                            with col_info2:
                                poste_actuel = get_safe_value(collab.get('Poste  libellé', ''))
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
        width="stretch",
        hide_index=True
    )

# --- FOOTER ---
st.divider()
st.markdown("""
<div style='text-align: center; color: #999; font-size: 0.9em;'>
    <p>CAP25 - Pilotage de la Mobilité Interne | Synchronisé avec Google Sheets</p>
</div>
""", unsafe_allow_html=True)



























