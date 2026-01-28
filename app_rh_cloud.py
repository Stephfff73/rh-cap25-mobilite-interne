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
data = [
        ["Centre Relation Client", "Chargé(e) de l'Expérience Client", "Oui", 1],
        ["Centre Relation Client", "Chef(fe) de projet Service Relation Clients", "Non", 1],
        ["Centre Relation Client", "Conseiller(e) Clientèle", "Oui", 26],
        ["Centre Relation Client", "Manager CRC", "Oui", 3],
        ["Centre Relation Client", "Responsable Centre Relation Clients", "Oui", 1],
        ["Direction Commerciale", "Assistant(e) Spécialisé(e)", "Non", 1],
        ["Direction Commerciale", "Conseiller(e) Commercial", "Non", 24],
        ["Direction Commerciale", "Conseiller(e) Social(e)", "Non", 2],
        ["Direction Commerciale", "Développeur(se) Commercial", "Non", 2],
        ["Direction Commerciale", "Directeur(ice) Commercial", "Non", 1],
        ["Direction Commerciale", "Directeur(ice) Développement Commercial", "Non", 1],
        ["Direction Commerciale", "Gestionnaire Entrées et sorties locataires", "Oui", 12],
        ["Direction Commerciale", "Responsable Commercial", "Non", 4],
        ["Direction Commerciale", "Responsable Pôle Entrées et sorties locataires", "Oui", 1],
        ["Direction Commerciale", "Responsable Service Social Mobilité", "Non", 1],
        ["Direction de l'Exploitation et du Territoire", "Assistant(e) de Direction DET", "Oui", 1],
        ["Direction de l'Exploitation et du Territoire", "Assistant(e) de Gestion Territorial", "Oui", 5],
        ["Direction de l'Exploitation et du Territoire", "Cadre Technique Territorial", "Oui", 4],
        ["Direction de l'Exploitation et du Territoire", "Chargé(e) de mission Exploitation et Services", "Oui", 3],
        ["Direction de l'Exploitation et du Territoire", "Chargé(e) de mission Sécurité / Sûreté", "Oui", 2],
        ["Direction de l'Exploitation et du Territoire", "Coordinateur(ice) MAH", "Oui", 1],
        ["Direction de l'Exploitation et du Territoire", "Coordinateur(ice) Territorial", "Oui", 1],
        ["Direction de l'Exploitation et du Territoire", "Directeur(ice) Exploitation et Territoire", "Non", 1],
        ["Direction de l'Exploitation et du Territoire", "Directeur(ice) Pôle Territorial", "Oui", 4],
        ["Direction de l'Exploitation et du Territoire", "Employé(e) d’immeuble", "Non", 20],
        ["Direction de l'Exploitation et du Territoire", "Gardien(ne) d’immeuble", "Non", 211],
        ["Direction de l'Exploitation et du Territoire", "Responsable d’Actifs Immobiliers", "Oui", 24],
        ["Direction de l'Exploitation et du Territoire", "Responsable Exploitation et Maintenance", "Oui", 48],
        ["Direction de l'Exploitation et du Territoire", "Responsable Pôle Technique Territorial", "Oui", 1],
        ["Direction des Opérations Clients", "Assistant(e) de Direction", "Non", 1],
        ["Direction des Opérations Clients", "Chargé(e) d’Affaires Immobilières", "Oui", 5],
        ["Direction des Opérations Clients", "Chargé(e) de Facturation", "Oui", 1],
        ["Direction des Opérations Clients", "Chargé(e) de mission Renouvellement des Baux", "Non", 2],
        ["Direction des Opérations Clients", "Chargé(e) de Recouvrement Amiable", "Oui", 6],
        ["Direction des Opérations Clients", "Chef(fe) de projet GL", "Non", 1],
        ["Direction des Opérations Clients", "Conseiller(e) Social(e)", "Non", 4],
        ["Direction des Opérations Clients", "Directeur(ice) des Opérations Clients", "Oui", 1],
        ["Direction des Opérations Clients", "Expert(e) Charges", "Non", 2],
        ["Direction des Opérations Clients", "Gestionnaire Base Patrimoine et Quittancement", "Oui", 3],
        ["Direction des Opérations Clients", "Gestionnaire de Charges Locatives", "Oui", 13],
        ["Direction des Opérations Clients", "Gestionnaire Recouvrement Contentieux", "Oui", 8],
        ["Direction des Opérations Clients", "Responsable Adjoint(e) Pôle Base Patrimoine et Quittancement", "Non", 1],
        ["Direction des Opérations Clients", "Responsable d’Equipe Charges Locatives", "Non", 2],
        ["Direction des Opérations Clients", "Responsable d’Equipe Recouvrement et Action Sociale", "Oui", 2],
        ["Direction des Opérations Clients", "Responsable Pôle Affaires Immobilières", "Oui", 1],
        ["Direction des Opérations Clients", "Responsable Pôle Base Patrimoine et Quittancement", "Non", 1],
        ["Direction des Opérations Clients", "Responsable Pôle Charges Locatives", "Oui", 1],
        ["Direction des Opérations Clients", "Responsable Pôle Recouvrement et Action Sociale", "Non", 1],
        ["Direction Performance Immobilère et Engagements Clients", "Directeur(ice) Adjoint(e) Performance Immobilière et Engagement Clients", "Non", 1],
        ["Direction Performance Immobilère et Engagements Clients", "Assistant(e) de Direction", "Non", 1],
        ["Direction Technique du Patrimoine Immobilier", "Analyste DATA", "Non", 2],
        ["Direction Technique du Patrimoine Immobilier", "Assistant(e) Technique", "Non", 1],
        ["Direction Technique du Patrimoine Immobilier", "Assistant(e) Technique – Contrats", "Non", 1],
        ["Direction Technique du Patrimoine Immobilier", "Assistant(e) Technique – Equipements Techniques", "Non", 2],
        ["Direction Technique du Patrimoine Immobilier", "Assistant(e) Technique – Réhabilitation", "Non", 4],
        ["Direction Technique du Patrimoine Immobilier", "Chargé(e) d’Opérations", "Non", 6],
        ["Direction Technique du Patrimoine Immobilier", "Chargé(e) de mission Accompagnement Social des Chantiers", "Non", 1],
        ["Direction Technique du Patrimoine Immobilier", "Chargé(e) de mission Contrats de Services", "Oui", 3],
        ["Direction Technique du Patrimoine Immobilier", "Chargé(e) de mission Equipements Techniques", "Non", 5],
        ["Direction Technique du Patrimoine Immobilier", "Chef(fe) de projet Métier Outils Base Patrimoine", "Non", 1],
        ["Direction Technique du Patrimoine Immobilier", "Chef(fe) de projet Programmation et CSP", "Oui", 2],
        ["Direction Technique du Patrimoine Immobilier", "Chef(fe) de projet Valorisation", "Non", 1],
        ["Direction Technique du Patrimoine Immobilier", "Chef(fe) de Projets Immobiliers", "Non", 6],
        ["Direction Technique du Patrimoine Immobilier", "Directeur(ice) de Projets", "Oui", 1],
        ["Direction Technique du Patrimoine Immobilier", "Directeur(ice) Opérationnel(le) Contrats", "Oui", 1],
        ["Direction Technique du Patrimoine Immobilier", "Directeur(ice) Opérationnel(le) Réhabilitation", "Oui", 1],
        ["Direction Technique du Patrimoine Immobilier", "Directeur(ice) Technique du Patrimoine Immobilier", "Non", 1],
        ["Direction Technique du Patrimoine Immobilier", "Gestionnaire Financier(e) Marchés et Contrats", "Oui", 1],
        ["Direction Technique du Patrimoine Immobilier", "Responsable Contrats Services", "Non", 1],
        ["Direction Technique du Patrimoine Immobilier", "Responsable Equipements Techniques", "Non", 1],
        ["Direction Technique du Patrimoine Immobilier", "Responsable Opérations Patrimoine", "Non", 1],
        ["Direction Technique du Patrimoine Immobilier", "Responsable Stratégie Patrimoniale et Programmation", "Oui", 1],
        ["Direction Ventes", "Analyste Valorisation", "Non", 1],
        ["Direction Ventes", "Chargé(e) de Gestion Documentaire", "Oui", 2],
        ["Direction Ventes", "Chargé(e) de Montage Juridique", "Oui", 3],
        ["Direction Ventes", "Chargé(e) de Montage Technique et Administratif", "Oui", 1],
        ["Direction Ventes", "Directeur(ice) Ventes", "Non", 1],
        ["Direction Ventes", "Responsable Administration des Ventes", "Non", 1],
        ["Direction Ventes", "Responsable Projet Ventes en bloc", "Non", 3],
        ["Direction Ventes", "Assistant(e) de Direction", "Non", 1],
        ["Direction Ventes", "Chargé(e) des Ventes (interne)", "Oui", 3],
        ["Direction Ventes", "Directeur(ice) Adjoint(e) Ventes", "Non", 1],
        ["Direction Ventes", "Gestionnaire Administration des Ventes", "Oui", 3],
        ["Direction Ventes", "Référent(e) Commercialisateurs", "Non", 2],
        ["Direction Ventes", "Responsable Force de Vente", "Non", 1],
        ["Gestion de Portefeuille", "Business Analyst Senior", "Non", 1],
        ["Gestion de Portefeuille", "Référent(e) Copropriété", "Non", 4],
        ["Gestion de Portefeuille", "Responsable Administratif et Budgétaire Copropriété", "Non", 1],
        ["Gestion de Portefeuille", "Responsable de Portefeuille", "Oui", 4],
        ["Pôle Professionnel", "Chargé(e) d’Affaires Commerces et Professionnels", "Non", 1],
        ["Pôle Professionnel", "Chargé(e) d’Affaires Résidences Gérées", "Oui", 1],
    ]
    df = pd.DataFrame(data, columns=["Direction", "Titre", "Mobilité_Interne", "Nombre_Total"])
    df["Statut_Actuel"] = df["Mobilité_Interne"].apply(lambda x: "Ouvert" if x == "Oui" else "Fermé")
    return df

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
