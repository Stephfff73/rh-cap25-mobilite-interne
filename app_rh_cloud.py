import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="CAP 2025 - Mobilité RH (Live)", layout="wide", page_icon="🎯")

# --- CONNEXION GOOGLE SHEETS ---
# L'URL de votre document
url = "https://docs.google.com/spreadsheets/d/1BXez24VFNhb470PrCjwNIFx6GdJFqLnVh8nFf3gGGvw/edit?usp=sharing"

conn = st.connection("gsheets", type=GSheetsConnection)

def load_gsheet_data():
    # Lecture : On saute la ligne 1, les en-têtes sont en ligne 2 (header=1)
    df = conn.read(spreadsheet=url, header=1)
    
    # Nettoyage selon vos instructions (Word)
    # 1. Supprimer si la colonne A (index 0) est vide
    df = df.dropna(subset=[df.columns[0]])
    
    # 2. Limiter aux 323 premières lignes (données utiles)
    if len(df) > 322:
        df = df.iloc[:322]
        
    return df

# --- FONCTIONS DE CALCUL ---
def calculate_anciennete(date_entree):
    if pd.isnull(date_entree): return "N/A"
    try:
        delta = (datetime.now() - pd.to_datetime(date_entree)).days / 365.25
        return f"{int(delta)} ans"
    except: return "N/A"

# --- RÉFÉRENTIEL DES POSTES (Extrait du Word) ---
@st.cache_data
def get_ref():
    # ... (Le référentiel que j'ai inclus dans le script précédent reste identique)
    # Je le simplifie ici pour la lisibilité du code
    return pd.DataFrame([["Centre Relation Client", "Conseiller(e) Clientèle", "Oui", 26]], 
                        columns=["Direction", "Titre", "Mobilité_Interne", "Nombre_Total"])

# --- ÉTAT DE LA SESSION ---
if "df_gsheet" not in st.session_state:
    st.session_state.df_gsheet = load_gsheet_data()

# --- LOGIQUE DE SAUVEGARDE VERS GOOGLE SHEETS ---
def save_to_gsheet(updated_df):
    try:
        conn.update(spreadsheet=url, data=updated_df)
        st.session_state.df_gsheet = updated_df
        st.success("✅ Données synchronisées sur Google Sheets !")
        time.sleep(1)
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde : {e}")

# --- INTERFACE PRINCIPALE ---
st.title("🚀 Pilotage Mobilité CAP 2025 (Mode Collaboratif)")

tab1, tab2, tab3 = st.tabs(["👥 Suivi & Entretiens", "📊 Dashboard RH", "🎯 Analyse par Poste"])

# --- TAB 1 : SUIVI & ENTRETIENS ---
with tab1:
    df = st.session_state.df_gsheet
    
    # Filtres de recherche
    search_col = st.selectbox("Rechercher un collaborateur", df.index, 
                             format_func=lambda x: f"{df.loc[x, 'Nom']} {df.loc[x, 'Prénom']}")
    
    cand = df.loc[search_col]
    
    with st.expander("👤 Fiche Identité & Vœux", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.write(f"**Ancienneté :** {calculate_anciennete(cand.get('Date entrée groupe'))}")
        c1.write(f"**Priorité :** {cand.get('Priorité', '-')}")
        
        c2.write(f"**Poste actuel :** {cand.get('Poste libellé', '-')}")
        c2.write(f"**Manager :** {cand.get('Nom Manager', '-')}")
        
        c3.success(f"**Vœu 1 :** {cand.get('Vœux 1', '-')}")
        c3.info(f"**Vœu 2 :** {cand.get('Vœux 2', '-')}")

    # --- SECTION ÉCRITURE (CONDUITE D'ENTRETIEN) ---
    st.subheader("📝 Conduite d'entretien RH")
    with st.form("form_entretien"):
        # On crée des champs pour les colonnes demandées dans le Word
        new_comm = st.text_area("Commentaires RH (Synthèse)", value=str(cand.get("Commentaires RH", "")))
        new_retenu = st.selectbox("Vœu Retenu final", [cand.get('Vœux 1'), cand.get('Vœux 2'), "Autre"])
        
        # Exemple de champs spécifiques pour l'entretien
        motivations = st.text_area("Motivations du collaborateur", key="motiv")
        
        if st.form_submit_button("Enregistrer et Partager avec l'équipe"):
            # Mise à jour du DataFrame local
            df.at[search_col, "Commentaires RH"] = new_comm
            df.at[search_col, "Vœux Retenu"] = new_retenu
            
            # Sauvegarde RÉELLE sur Google Sheets
            save_to_gsheet(df)
            st.rerun()

# --- TAB 2 : DASHBOARD ---
with tab2:
    st.subheader("Indicateurs en temps réel")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Candidatures", len(df))
    col2.metric("RDV réalisés", len(df[df["Commentaires RH"].notna()]))
    
    # Graphique de tension
    st.bar_chart(df["Direction libellé"].value_counts())

# --- TAB 3 : ANALYSE PAR POSTE ---
with tab3:
    st.write("Cet onglet permet de voir combien de personnes ont postulé sur un même poste")
    # Logique identique au script précédent mais branchée sur 'df'
