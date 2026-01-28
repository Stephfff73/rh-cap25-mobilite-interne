import streamlit as st
import pandas as pd
from datetime import datetime, date
import time
from google.oauth2 import service_account
import gspread

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
            worksheet = spreadsheet.add_worksheet(title="Entretien RH", rows="1000", cols="50")
            
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
        
        all_records = worksheet.get_all_records()
        existing_row = None
        
        for idx, record in enumerate(all_records):
            if str(record.get("Matricule", "")) == str(entretien_data["Matricule"]):
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
            entretien_data.get("Avis_RH_Synthese", "")
        ]
        
        if existing_row:
            worksheet.update(f'A{existing_row}:AX{existing_row}', [row_data])
        else:
            worksheet.append_row(row_data)
        
        return True
        
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde : {str(e)}")
        return False

def calculate_anciennete(date_str):
    """Calcule l'ancienneté en années à partir d'une date"""
    if not date_str or date_str.strip() == "":
        return "N/A"
    
    try:
        # Essayer différents formats de date
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
        
        return date_str  # Si aucun format ne correspond, retourner la valeur originale
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
    # Vérifier d'abord si c'est une Series pandas
    if isinstance(value, pd.Series):
        if len(value) > 0:
            val = value.iloc[0]
            return str(val) if pd.notna(val) and val != "" else ""
        return ""
    # Ensuite vérifier si c'est NaN
    try:
        if pd.isna(value):
            return ""
    except (ValueError, TypeError):
        pass
    # Retourner la valeur convertie en string
    return str(value) if value else ""

# --- URL DU GOOGLE SHEET ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1BXez24VFNhb470PrCjwNIFx6GdJFqLnVh8nFf3gGGvw/edit?usp=sharing"

# --- INITIALISATION ---
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
st.sidebar.caption(f"Dernière mise à jour : {datetime.now().strftime('%H:%M:%S')}")

# ========================================
# PAGE 1 : TABLEAU DE BORD
# ========================================

if page == "📊 Tableau de Bord":
    st.title("📊 Tableau de Bord - Vue d'ensemble")
    
    # Première ligne de métriques
    col1, col2, col3, col4 = st.columns(4)
    
    # Nombre de collaborateurs = nombre de matricules non vides
    nb_collaborateurs = len(collaborateurs_df[collaborateurs_df["Matricule"].notna() & (collaborateurs_df["Matricule"] != "")])
    
    # Calcul du nombre de postes ouverts (somme de "Nombre total de postes" où "Mobilité interne" = "Oui")
    postes_ouverts_df = postes_df[postes_df["Mobilité interne"].str.lower() == "oui"]
    nb_postes_ouverts = int(postes_ouverts_df["Nombre total de postes"].sum()) if "Nombre total de postes" in postes_df.columns else len(postes_ouverts_df)
    
    # Entretiens planifiés (Date de rdv non vide et postérieure à aujourd'hui)
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
    
    col1.metric("👥 Collaborateurs", nb_collaborateurs)
    col2.metric("📍 Postes ouverts", nb_postes_ouverts)
    col3.metric("📅 Entretiens planifiés", entretiens_planifies)
    col4.metric("⌛ Entretiens prévus aujourd'hui", entretiens_aujourd_hui)
    
    # Deuxième ligne de métriques
    col5, col6, col7, col8 = st.columns(4)
    
    nb_priorite_1 = len(collaborateurs_df[collaborateurs_df["Priorité"] == "Priorité 1"])
    nb_priorite_2 = len(collaborateurs_df[collaborateurs_df["Priorité"] == "Priorité 2"])
    nb_priorite_3 = len(collaborateurs_df[collaborateurs_df["Priorité"] == "Priorité 3"])
    
    col5.metric("⭐ Priorité 1", nb_priorite_1)
    col6.metric("⭐ Priorité 2", nb_priorite_2)
    col7.metric("⭐ Priorité 3", nb_priorite_3)
    col8.metric("✅ Entretiens réalisés", entretiens_realises)
    
    st.divider()
    
    # Graphiques
    col_chart1, col_chart2 = st.columns(2)
    
:
        st.subheader("🔥 Top 10 des postes les plus demandés")
        
        # Concaténer tous les vœux (excluant "Positionnement manquant" et valeurs vides)
        all_voeux = pd.concat([
            collaborateurs_df["Vœux 1"],
            collaborateurs_df["Vœux 2"],
            collaborateurs_df["Voeux 3"]
        ])
        # Filtrer pour ne garder que les valeurs valides (non vides, non null, non "Positionnement manquant")
        all_voeux = all_voeux[
            all_voeux.notna() & 
            (all_voeux.astype(str).str.strip() != "") & 
            (all_voeux.astype(str).str.strip() != "Positionnement manquant")
        ]
        
        if len(all_voeux) > 0:
            top_postes = all_voeux.value_counts().head(10)
            
            # Créer le tableau avec classement
            top_df = pd.DataFrame({
                "Classement": range(1, len(top_postes) + 1),
                "Poste": top_postes.index,
                "Nombre de vœux": top_postes.values
            })
            
            st.dataframe(
                top_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Aucun vœu enregistré pour le moment")
    
    with col_chart2:
        st.subheader("⚠️ Flop 10 des postes les moins demandés")
        
        if len(all_voeux) > 0:
            # Trier par ordre croissant et prendre les 10 premiers
            flop_postes = all_voeux.value_counts().sort_values(ascending=True).head(10)
            
            # Créer le tableau avec classement
            flop_df = pd.DataFrame({
                "Classement": range(1, len(flop_postes) + 1),
                "Poste": flop_postes.index,
                "Nombre de vœux": flop_postes.values
            })
            
            st.dataframe(
                flop_df,
                use_container_width=True,
                hide_index=True
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
        # Filtre par collaborateur avec recherche
        all_collabs = sorted((collaborateurs_df["NOM"] + " " + collaborateurs_df["Prénom"]).unique())
        filtre_collaborateur = st.multiselect(
            "Filtrer par Collaborateur",
            options=all_collabs,
            default=[]
        )
    
    with col_f3:
        # Recherche par nom de collaborateur
        search_nom = st.text_input("🔍 Rechercher un collaborateur par son nom")
    
    with col_f4:
        filtre_rrh = st.multiselect(
            "Filtrer par RRH",
            options=sorted(collaborateurs_df["Référente RH"].unique()),
            default=[]
        )
    
    # Ligne de filtre supplémentaire pour la date
    filtre_date_rdv = st.date_input(
        "Filtrer par Date de rdv",
        value=None
    )
    
    # Appliquer les filtres
    df_filtered = collaborateurs_df.copy()
    
    # FILTRE PRINCIPAL : Ne garder que les lignes avec un Matricule non vide
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
        # Calculer l'ancienneté
        anciennete = calculate_anciennete(get_safe_value(row.get("Date entrée groupe", "")))
        
        # Préparer la date et heure d'entretien
        date_rdv = get_safe_value(row.get("Date de rdv", ""))
        heure_rdv = get_safe_value(row.get("Heure de rdv", ""))
        
        if date_rdv and date_rdv.strip() != "":
            entretien = f"{date_rdv} à {heure_rdv}" if heure_rdv and heure_rdv.strip() != "" else date_rdv
        else:
            entretien = ""
        
        # Assessment
        assessment = get_safe_value(row.get("Assesment à planifier O/N", "Non"))
        if not assessment or assessment.strip() == "":
            assessment = "Non"
        
        # Manager actuel - CORRECTION: traiter chaque champ séparément
        prenom_manager = get_safe_value(row.get('Prénom Manager', ''))
        nom_manager = get_safe_value(row.get('Nom Manager', ''))
        manager_actuel = f"{prenom_manager} {nom_manager}".strip()
        
        # Vœux
        voeu_1 = get_safe_value(row.get("Vœux 1", ""))
        voeu_2 = get_safe_value(row.get("Vœux 2", ""))
        voeu_3 = get_safe_value(row.get("Voeux 3", ""))
        
        # Remplacer "Positionnement manquant" par ""
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
            "Matricule": get_safe_value(row.get("Matricule", ""))  # Caché mais nécessaire pour la navigation
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
            if st.button("➡️ Aller à l'entretien", type="primary", disabled=(selected_for_entretien == "-- Sélectionner --")):
                # Stocker la sélection dans session_state et changer de page
                st.session_state['selected_collaborateur'] = selected_for_entretien
                st.session_state['navigate_to_entretien'] = True
                st.session_state['page'] = '📝 Entretien RH'
                st.rerun()
    else:
        st.info("Aucun collaborateur ne correspond aux filtres sélectionnés")

# ========================================
# PAGE 3 : ENTRETIEN RH
# ========================================

elif page == "📝 Entretien RH":
    st.title("📝 Conduite d'Entretien RH - CAP 2025")
    
    st.info("""
    Ce formulaire permet de formaliser le compte rendu de l'entretien avec le collaborateur.
    Les informations seront sauvegardées dans l'onglet "Entretien RH" du Google Sheet.
    """)
    
    # Sélection du collaborateur
    st.subheader("1️⃣ Sélection du collaborateur")
    
    # Vérifier si on vient de la page "Gestion des Candidatures" ou "Analyse par Poste"
    preselected_collab = None
    if 'navigate_to_entretien' in st.session_state and st.session_state['navigate_to_entretien']:
        preselected_collab = st.session_state.get('selected_collaborateur')
        st.session_state['navigate_to_entretien'] = False
    
    # Créer un filtre par direction
    col_dir, col_collab = st.columns([1, 2])
    
    with col_dir:
        selected_direction = st.selectbox(
            "Filtrer par Direction",
            options=["-- Toutes --"] + sorted(collaborateurs_df["Direction libellé"].unique())
        )
    
    # Filtrer les collaborateurs par direction
    if selected_direction == "-- Toutes --":
        filtered_collabs_df = collaborateurs_df
    else:
        filtered_collabs_df = collaborateurs_df[collaborateurs_df["Direction libellé"] == selected_direction]
    
    # Créer la liste des collaborateurs triée par nom
    collaborateur_list = sorted(
        (filtered_collabs_df["NOM"] + " " + filtered_collabs_df["Prénom"]).tolist()
    )
    
    with col_collab:
        # Déterminer l'index par défaut
        default_index = 0
        if preselected_collab and preselected_collab in collaborateur_list:
            default_index = collaborateur_list.index(preselected_collab) + 1
        
        selected_collab = st.selectbox(
            "Rechercher un collaborateur (saisir les premières lettres)",
            options=["-- Sélectionner --"] + collaborateur_list,
            index=default_index
        )
    
    if selected_collab != "-- Sélectionner --":
        # Récupérer les infos du collaborateur
        collab_mask = (collaborateurs_df["NOM"] + " " + collaborateurs_df["Prénom"]) == selected_collab
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
        
        # Initialiser l'entretien data
        entretien_data = {
            "Matricule": get_safe_value(collab.get('Matricule', '')),
            "Nom": get_safe_value(collab.get('NOM', '')),
            "Prénom": get_safe_value(collab.get('Prénom', '')),
            "Date_Entretien": datetime.now().strftime("%d/%m/%Y"),
            "Referente_RH": get_safe_value(collab.get('Référente RH', ''))
        }
        
        # Tabs pour les 3 vœux
        voeu1_label = get_safe_value(collab.get('Vœux 1', 'Non renseigné'))
        voeu2_label = get_safe_value(collab.get('Vœux 2', 'Non renseigné')) if collab.get('Vœux 2') else 'Non renseigné'
        voeu3_label = get_safe_value(collab.get('Voeux 3', 'Non renseigné')) if collab.get('Voeux 3') else 'Non renseigné'
        
        tab_voeu1, tab_voeu2, tab_voeu3, tab_avis = st.tabs([
            f"🎯 Vœu 1: {voeu1_label}", 
            f"🎯 Vœu 2: {voeu2_label}", 
            f"🎯 Vœu 3: {voeu3_label}",
            "💬 Avis RH"
        ])
        
        # ========== VŒEU 1 ==========
        with tab_voeu1:
            if collab.get('Vœux 1') and collab.get('Vœux 1') != "Positionnement manquant":
                st.subheader(f"Évaluation du Vœu 1 : {get_safe_value(collab.get('Vœux 1'))}")
                
                entretien_data["Voeu_1"] = get_safe_value(collab.get('Vœux 1', ''))
                
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
        
        # ========== VŒEU 2 ==========
        with tab_voeu2:
            if collab.get('Vœux 2') and collab.get('Vœux 2') != "Positionnement manquant":
                st.subheader(f"Évaluation du Vœu 2 : {get_safe_value(collab.get('Vœux 2'))}")
                
                entretien_data["Voeu_2"] = get_safe_value(collab.get('Vœux 2', ''))
                
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
            if collab.get('Voeux 3') and collab.get('Voeux 3') != "Positionnement manquant":
                st.subheader(f"Évaluation du Vœu 3 : {get_safe_value(collab.get('Voeux 3'))}")
                
                entretien_data["Voeu_3"] = get_safe_value(collab.get('Voeux 3', ''))
                
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
    
    # Liste des postes ouverts à la mobilité avec leur nombre total
    postes_ouverts_df = postes_df[postes_df["Mobilité interne"].str.lower() == "oui"].copy()
    
    # Analyse par poste
    job_analysis = []
    
    for _, poste_row in postes_ouverts_df.iterrows():
        poste = poste_row["Poste"]
        nb_postes_disponibles = int(poste_row.get("Nombre total de postes", 1))
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
        if nb_candidats == 0:
            statut = "⚠️ Aucun candidat"
        elif nb_candidats < nb_postes_disponibles:
            statut = f"⚠️ Manque {nb_postes_disponibles - nb_candidats} candidat(s)"
        elif nb_candidats == nb_postes_disponibles:
            statut = "✅ Vivier actif"
        else:
            # Calcul du ratio de tension
            ratio = nb_candidats / nb_postes_disponibles
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
        # Liste des statuts possibles
        statuts_possibles = [
            "⚠️ Aucun candidat",
            "⚠️ Manque",
            "✅ Vivier actif",
            "🔶 Tension",
            "🔴 Forte tension",
            "🔴🔴 Très forte tension"
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
        # Pour le statut "Manque", on doit vérifier si le statut commence par "⚠️ Manque"
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
                )
            }
        )
        
        st.divider()
        
        # Section pour accéder aux fiches détaillées
        st.subheader("🔍 Accès aux fiches candidats")
        
        # Sélection du poste (par ordre alphabétique)
        postes_tries = sorted(df_filtered_analysis["Poste"].tolist())
        poste_selected = st.selectbox(
            "Sélectionner un poste pour voir ses candidats",
            options=["-- Sélectionner --"] + postes_tries
        )
        
        if poste_selected != "-- Sélectionner --":
            # Récupérer les candidats du poste sélectionné
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
                        # Afficher la fiche détaillée du collaborateur
                        st.session_state['show_fiche_detail'] = True
                        st.session_state['fiche_candidat'] = candidat_selected
                
                # Afficher la fiche détaillée si demandé
                if st.session_state.get('show_fiche_detail') and st.session_state.get('fiche_candidat') == candidat_selected:
                    st.divider()
                    st.subheader(f"📋 Fiche détaillée : {candidat_selected}")
                    
                    # Récupérer les infos du collaborateur
                    collab_mask = (collaborateurs_df["NOM"] + " " + collaborateurs_df["Prénom"]) == candidat_selected
                    if collab_mask.any():
                        collab = collaborateurs_df[collab_mask].iloc[0]
                        
                        # Afficher les infos dans un container - CORRECTION: utiliser get_safe_value sur chaque champ
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
                        
                        # Bouton pour accéder à l'entretien complet
                        if st.button("➡️ Accéder à l'entretien RH complet", type="secondary"):
                            st.session_state['selected_collaborateur'] = candidat_selected
                            st.session_state['navigate_to_entretien'] = True
                            st.session_state['page'] = '📝 Entretien RH'
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
<div style='text-align: center; color: #666; font-size: 0.9em;'>
    <p>CAP25 - Pilotage de la Mobilité Interne | Synchronisé avec Google Sheets</p>
</div>
""", unsafe_allow_html=True)
