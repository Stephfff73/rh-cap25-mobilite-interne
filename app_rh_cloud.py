%%writefile app_rh_cloud.py
import streamlit as st
import pandas as pd

# 1. Tentative d'import de la connexion Google Sheets
try:
    from streamlit_gsheets import GSheetsConnection
    HAS_GSHEETS = True
except ImportError:
    HAS_GSHEETS = False

st.set_page_config(page_title="Pilotage RH - CAP25", layout="wide", page_icon="🏢")

# --- FONCTION : DONNÉES DE TEST (BETA) ---
def get_mock_data():
    df_form = pd.DataFrame([
        {"Nom": "Martin Durand", "Poste_Actuel": "Chef(fe) de projet GL", "Voeu_1": "Directeur(ice) Opérationnel(le) Contrats", "Voeu_2": "Responsable de Portefeuille", "Voeu_3": ""},
        {"Nom": "Sophie Lemoine", "Poste_Actuel": "Assistant(e) Spécialisé(e)", "Voeu_1": "Chargé(e) d’Affaires Résidences Gérées", "Voeu_2": "", "Voeu_3": ""},
        {"Nom": "Jean Dupont", "Poste_Actuel": "Conseiller(e) Clientèle", "Voeu_1": "Manager CRC", "Voeu_2": "Chargé(e) de l'Expérience Client", "Voeu_3": ""},
    ])
    df_suivi = pd.DataFrame(columns=["Nom", "Statut_RDV", "Commentaires", "Validation"])
    df_suivi["Nom"] = df_form["Nom"]
    df_suivi["Statut_RDV"] = "À planifier"
    df_suivi["Validation"] = "En attente"
    df_suivi["Commentaires"] = ""
    return df_form, df_suivi

# --- GESTION DES SECRETS ---
URL_SHEETS = None
try:
    if "connections" in st.secrets:
        URL_SHEETS = st.secrets["connections"]["gsheets"]["spreadsheet"]
except Exception:
    URL_SHEETS = None

# --- CHARGEMENT DES DONNÉES ---
@st.cache_data(ttl=60)
def load_all_data():
    if HAS_GSHEETS and URL_SHEETS and URL_SHEETS != "VOTRE_URL_ICI":
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            f = conn.read(worksheet="Réponses")
            s = conn.read(worksheet="Suivi_RH")
            return f, s, "Cloud"
        except Exception as e:
            f, s = get_mock_data()
            return f, s, f"Erreur Connexion"
    else:
        f, s = get_mock_data()
        return f, s, "Démo (Local)"

df_form, df_suivi, mode = load_all_data()

# --- INTERFACE ---
st.title("🧩 Back-Office RH : Mobilité Interne CAP25")
st.sidebar.info(f"Mode actuel : **{mode}**")

if mode != "Cloud":
    st.warning("⚠️ L'application tourne sur des données de démonstration.")

# Fusion pour l'affichage
df_display = pd.merge(df_form, df_suivi, on="Nom", how="left")

# --- LISTE DES CANDIDATS ---
st.subheader("Suivi des candidatures")
selected_nom = st.selectbox("Sélectionner un collaborateur :", df_display["Nom"].tolist())
candidate_info = df_display[df_display["Nom"] == selected_nom].iloc[0]

with st.expander(f"Dossier de {selected_nom}", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**Vœu 1 :** {candidate_info['Voeu_1']}")
    with col2:
        st.selectbox("Statut", ["À planifier", "Planifié", "Réalisé"], key="s_v", 
                     index=["À planifier", "Planifié", "Réalisé"].index(candidate_info["Statut_RDV"]))
    
    st.text_area("Notes RH", value=candidate_info["Commentaires"])
    if st.button("Enregistrer (Simulation)"):
        st.success("Modifications prises en compte !")
# --- VISUALISATION DE L'IMPACT ---
st.divider()
st.subheader("Analyse de l'Organigramme Cible")
# Ici, vous pouvez remettre la logique de bar chart de tension et de libération de postes

