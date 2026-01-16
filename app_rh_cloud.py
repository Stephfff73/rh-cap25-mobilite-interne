import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Pilotage RH Collaboratif", layout="wide")

# --- CONNEXION GOOGLE SHEETS ---
# Note : L'URL doit être celle de votre fichier Google Sheets
URL_SHEETS = "VOTRE_URL_GOOGLE_SHEETS_ICI"

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60) # Rafraîchir les données toutes les minutes
def load_data():
    # 1. Lire les réponses du formulaire
    df_form = conn.read(spreadsheet=URL_SHEETS, worksheet="Réponses")
    # 2. Lire le suivi RH existant
    df_suivi = conn.read(spreadsheet=URL_SHEETS, worksheet="Suivi_RH")
    return df_form, df_suivi

df_form, df_suivi = load_data()

# --- RÉFÉRENTIEL DES POSTES (Identique à précédemment) ---
# [Insérez ici la liste des postes fournie précédemment pour la logique d'impact]
# (Je simplifie ici pour la lisibilité du bloc de code)

st.title("🏢 Pilotage des Mobilités - Connexion Cloud")

# --- FUSION DES DONNÉES ---
# On croise les réponses du formulaire avec notre tableau de suivi RH sur le Nom
df_complet = pd.merge(df_form, df_suivi, on="Nom", how="left")

# --- INTERFACE RH ---
st.subheader("Suivi des candidatures et arbitrages")

if not df_complet.empty:
    # Sélection du candidat
    candidat_nom = st.selectbox("Sélectionner un collaborateur", df_complet['Nom'].unique())
    
    # Récupération des données actuelles
    current_data = df_complet[df_complet['Nom'] == candidat_nom].iloc[0]
    
    with st.form("form_rh"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Vœu 1 :** {current_data.get('Voeu_1', 'N/A')}")
            statut = st.selectbox("Statut RDV", ["À planifier", "Planifié", "Réalisé"], 
                                  index=["À planifier", "Planifié", "Réalisé"].index(current_data.get('Statut_RDV', 'À planifier')))
        
        with col2:
            st.markdown(f"**Vœu 2 :** {current_data.get('Voeu_2', 'N/A')}")
            validation = st.selectbox("Décision", ["En attente", "Validé", "Refusé"],
                                      index=["En attente", "Validé", "Refusé"].index(current_data.get('Validation', 'En attente')))
            
        commentaires = st.text_area("Notes d'entretien", value=current_data.get('Commentaires', ""))
        
        if st.form_submit_button("💾 Enregistrer dans le Google Sheets"):
            # MISE À JOUR DU GOOGLE SHEETS
            # On prépare la nouvelle ligne
            new_row = {
                "Nom": candidat_nom,
                "Statut_RDV": statut,
                "Commentaires": commentaires,
                "Validation": validation
            }
            
            # Logique pour mettre à jour df_suivi
            if candidat_nom in df_suivi['Nom'].values:
                df_suivi.loc[df_suivi['Nom'] == candidat_nom, ["Statut_RDV", "Commentaires", "Validation"]] = [statut, commentaires, validation]
            else:
                df_suivi = pd.concat([df_suivi, pd.DataFrame([new_row])], ignore_index=True)
            
            # Envoi vers Google Sheets
            conn.update(spreadsheet=URL_SHEETS, worksheet="Suivi_RH", data=df_suivi)
            st.success(f"Données de {candidat_nom} sauvegardées et partagées avec l'équipe !")
            st.cache_data.clear() # Forcer la recharge au prochain tour

# --- VISUALISATION DE L'IMPACT ---
st.divider()
st.subheader("Analyse de l'Organigramme Cible")
# Ici, vous pouvez remettre la logique de bar chart de tension et de libération de postes
