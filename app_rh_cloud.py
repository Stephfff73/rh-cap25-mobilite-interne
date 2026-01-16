import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="CAP25 - Mobilité Interne", layout="wide", page_icon="🏢")

# --- 1. RÉFÉRENTIEL COMPLET DES POSTES ---
@st.cache_data
def get_referentiel():
    data = [
        ["Centre Relation Client", "Chargé(e) de l'Expérience Client", "Oui"],
        ["Centre Relation Client", "Chef(fe) de projet Service Relation Clients", "Non"],
        ["Centre Relation Client", "Conseiller(e) Clientèle", "Oui"],
        ["Centre Relation Client", "Manager CRC", "Oui"],
        ["Centre Relation Client", "Responsable Centre Relation Clients", "Oui"],
        ["Direction Commerciale", "Assistant(e) Spécialisé(e)", "Non"],
        ["Direction Commerciale", "Conseiller(e) Commercial", "Non"],
        ["Direction Commerciale", "Conseiller(e) Social(e)", "Non"],
        ["Direction Commerciale", "Développeur Commercial", "Non"],
        ["Direction Commerciale", "Directeur(ice) Commercial", "Non"],
        ["Direction Commerciale", "Directeur(ice) Développement Commercial", "Non"],
        ["Direction Commerciale", "Gestionnaire Entrées et sorties locataires", "Oui"],
        ["Direction Commerciale", "Responsable Commercial", "Non"],
        ["Direction Commerciale", "Responsable Pôle Entrées et sorties locataires", "Oui"],
        ["Direction Commerciale", "Responsable Service Social Mobilité", "Non"],
        ["Direction de l'Exploitation et du Territoire", "Assistant(e) de Direction DET", "Oui"],
        ["Direction de l'Exploitation et du Territoire", "Assistant(e) de Gestion Territorial", "Oui"],
        ["Direction de l'Exploitation et du Territoire", "Cadre Technique Territorial", "Oui"],
        ["Direction de l'Exploitation et du Territoire", "Chargé(e) de mission Exploitation et Services", "Oui"],
        ["Direction de l'Exploitation et du Territoire", "Chargé(e) de mission Sécurité / Sûreté", "Oui"],
        ["Direction de l'Exploitation et du Territoire", "Coordinateur(ice) MAH", "Oui"],
        ["Direction de l'Exploitation et du Territoire", "Coordinateur(ice) Territorial", "Oui"],
        ["Direction de l'Exploitation et du Territoire", "Directeur(ice) Exploitation et Territoire", "Non"],
        ["Direction de l'Exploitation et du Territoire", "Directeur(ice) Pôle Territorial", "Oui"],
        ["Direction de l'Exploitation et du Territoire", "Employé(e) d’immeuble", "Non"],
        ["Direction de l'Exploitation et du Territoire", "Gardien(ne) d’immeuble", "Non"],
        ["Direction de l'Exploitation et du Territoire", "Responsable d’Actifs Immobiliers", "Oui"],
        ["Direction de l'Exploitation et du Territoire", "Responsable Exploitation et Maintenance", "Oui"],
        ["Direction de l'Exploitation et du Territoire", "Responsable Pôle Technique Territorial", "Oui"],
        ["Direction des Opérations Clients", "Chargé(e) d’Affaires Immobilières", "Oui"],
        ["Direction des Opérations Clients", "Chargé(e) de Facturation", "Oui"],
        ["Direction des Opérations Clients", "Chargé(e) de mission Renouvellement des Baux", "Non"],
        ["Direction des Opérations Clients", "Chargé(e) de Recouvrement Amiable", "Oui"],
        ["Direction des Opérations Clients", "Chef(fe) de projet GL", "Non"],
        ["Direction des Opérations Clients", "Conseiller(e) Social(e)", "Non"],
        ["Direction des Opérations Clients", "Directeur(ice) des Opérations Clients", "Oui"],
        ["Direction des Opérations Clients", "Expert(e) Charges", "Non"],
        ["Direction des Opérations Clients", "Gestionnaire Base Patrimoine et Quittancement", "Non"],
        ["Direction des Opérations Clients", "Gestionnaire de Charges Locatives", "Oui"],
        ["Direction des Opérations Clients", "Gestionnaire Recouvrement Contentieux", "Oui"],
        ["Direction des Opérations Clients", "Responsable Adjoint(e) Pôle Base Patrimoine et Quittancement", "Non"],
        ["Direction des Opérations Clients", "Responsable d’Equipe Charges Locatives", "Non"],
        ["Direction des Opérations Clients", "Responsable d’Equipe Recouvrement et Action Sociale", "Oui"],
        ["Direction des Opérations Clients", "Responsable Pôle Affaires Immobilières", "Oui"],
        ["Direction des Opérations Clients", "Responsable Pôle Base Patrimoine et Quittancement", "Non"],
        ["Direction des Opérations Clients", "Responsable Pôle Charges Locatives", "Oui"],
        ["Direction des Opérations Clients", "Responsable Pôle Recouvrement et Action Sociale", "Non"],
        ["Direction Performance Immobilère et Engagements Clients", "Directeur(ice) Adjoint(e) Performance Immobilière et Engagement Clients", "Non"],
        ["Direction Technique du Patrimoine Immobilier", "Analyste DATA", "Non"],
        ["Direction Technique du Patrimoine Immobilier", "Assistant(e) Technique", "Non"],
        ["Direction Technique du Patrimoine Immobilier", "Assistant(e) Technique – Contrats", "Non"],
        ["Direction Technique du Patrimoine Immobilier", "Assistant(e) Technique – Equipements Techniques", "Non"],
        ["Direction Technique du Patrimoine Immobilier", "Assistant(e) Technique – Réhabilitation", "Non"],
        ["Direction Technique du Patrimoine Immobilier", "Chargé(e) d’Opérations", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Chargé(e) de mission Accompagnement Social des Chantiers", "Non"],
        ["Direction Technique du Patrimoine Immobilier", "Chargé(e) de mission Contrats de Services", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Chargé(e) de mission Equipements Techniques", "Non"],
        ["Direction Technique du Patrimoine Immobilier", "Chef(fe) de projet Métier Outils Base Patrimoine", "Non"],
        ["Direction Technique du Patrimoine Immobilier", "Chef(fe) de projet Programmation et CSP", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Chef(fe) de projet Valorisation", "Non"],
        ["Direction Technique du Patrimoine Immobilier", "Chef(fe) de Projets Immobiliers", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Directeur(ice) de Projets", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Directeur(ice) Opérationnel(le) Contrats", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Directeur(ice) Opérationnel(le) Réhabilitation", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Directeur(ice) Technique du Patrimoine Immobilier", "Non"],
        ["Direction Technique du Patrimoine Immobilier", "Gestionnaire Financier(e) Marchés et Contrats", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Responsable Contrats Services", "Non"],
        ["Direction Technique du Patrimoine Immobilier", "Responsable Equipements Techniques", "Non"],
        ["Direction Technique du Patrimoine Immobilier", "Responsable Opérations Patrimoine", "Non"],
        ["Direction Technique du Patrimoine Immobilier", "Responsable Stratégie Patrimoniale et Programmation", "Oui"],
        ["Direction Ventes et Copropriété", "Analyste Valorisation", "Non"],
        ["Direction Ventes et Copropriété", "Chargé(e) de Gestion Documentaire", "Oui"],
        ["Direction Ventes et Copropriété", "Chargé(e) de Montage Juridique", "Oui"],
        ["Direction Ventes et Copropriété", "Chargé(e) de Montage Technique et Administratif", "Oui"],
        ["Direction Ventes et Copropriété", "Directeur(ice) Ventes", "Non"],
        ["Direction Ventes et Copropriété", "Responsable Administration des Ventes", "Non"],
        ["Direction Ventes et Copropriété", "Responsable Projet Ventes en bloc", "Non"],
        ["Direction Ventes et Copropriété", "Assistant(e) de Direction", "Non"],
        ["Direction Ventes et Copropriété", "Chargé(e) des Ventes (interne)", "Oui"],
        ["Direction Ventes et Copropriété", "Directeur(ice) Adjoint(e) Ventes", "Non"],
        ["Direction Ventes et Copropriété", "Gestionnaire Administration des Ventes", "Oui"],
        ["Direction Ventes et Copropriété", "Référent(e) Commercialisateurs", "Non"],
        ["Direction Ventes et Copropriété", "Responsable Force de Vente", "Non"],
        ["Gestion de Portefeuille", "Business Analyst Senior", "Non"],
        ["Gestion de Portefeuille", "Référent(e) Copropriété", "Non"],
        ["Gestion de Portefeuille", "Responsable Administratif et Budgétaire Copropriété", "Non"],
        ["Gestion de Portefeuille", "Responsable de Portefeuille", "Oui"],
        ["Pôle Professionnel", "Chargé(e) d’Affaires Commerces et Professionnels", "Non"],
        ["Pôle Professionnel", "Chargé(e) d’Affaires Résidences Gérées", "Oui"],
    ]
    df = pd.DataFrame(data, columns=["Direction", "Titre", "Ouvert_Initialement"])
    df["Statut_Actuel"] = df["Ouvert_Initialement"].apply(lambda x: "Ouvert" if x == "Oui" else "Occupé")
    return df

# --- 2. GÉNÉRATION DES 20 PROFILS FICTIFS ---
def get_mock_candidates(ref_df):
    noms = [
        "Alice Bernard", "Benoît Petit", "Cécile Roux", "David Morel", "Elena Garcia",
        "Fabien Dumas", "Géraldine Lopez", "Hugo Fourny", "Isabelle Blanc", "Julien Guerin",
        "Karine Boyer", "Ludovic Vincent", "Mélanie Joly", "Nicolas Masson", "Olivia Roger",
        "Pierre Roche", "Quentin Brun", "Rosa Martinez", "Sébastien Vidal", "Thomas Renard"
    ]
    
    postes_occupes = ref_df[ref_df["Ouvert_Initialement"] == "Non"]["Titre"].tolist()
    postes_ouverts = ref_df[ref_df["Ouvert_Initialement"] == "Oui"]["Titre"].tolist()
    
    candidates = []
    start_date = datetime(2026, 1, 19)
    
    for i, nom in enumerate(noms):
        # 3 voeux pour la majorité (75% des cas)
        nb_voeux = 3 if i < 15 else random.randint(1, 2)
        voeux = random.sample(postes_ouverts, nb_voeux)
        while len(voeux) < 3: voeux.append("")
        
        # Date de RDV entre le 19/01 et le 05/02
        date_rdv = start_date + timedelta(days=random.randint(0, 17))
        
        candidates.append({
            "Nom": nom,
            "Poste_Actuel": random.choice(postes_occupes),
            "Voeu_1": voeux[0],
            "Voeu_2": voeux[1],
            "Voeu_3": voeux[2],
            "Date_RDV": date_rdv.strftime("%d/%m/%Y"),
            "Statut_RDV": "Planifié",
            "Commentaires": "",
            "Validation": "En attente"
        })
    return pd.DataFrame(candidates)

# --- INITIALISATION ---
if 'ref_df' not in st.session_state:
    st.session_state.ref_df = get_referentiel()

if 'candidats_df' not in st.session_state:
    st.session_state.candidats_df = get_mock_candidates(st.session_state.ref_df)

# --- TABS ---
st.title("🚀 Back-Office Mobilité RH | Projet CAP25")
tab1, tab2, tab3 = st.tabs(["📊 Tableau de Bord", "🗓️ Gestion Candidats & RDV", "🌳 Organigramme Dynamique"])

# --- TAB 1 : TABLEAU DE BORD ---
with tab1:
    st.subheader("Indicateurs Clés")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Candidatures reçues", len(st.session_state.candidats_df))
    c2.metric("Postes Ouverts (Total)", len(st.session_state.ref_df[st.session_state.ref_df["Statut_Actuel"]=="Ouvert"]))
    c3.metric("Entretiens Planifiés", len(st.session_state.candidats_df))
    c4.metric("Mobilités Validées", len(st.session_state.candidats_df[st.session_state.candidats_df["Validation"]=="Validé"]))

    st.divider()
    st.subheader("Analyse des Vœux (Tension)")
    all_voeux = pd.concat([st.session_state.candidats_df["Voeu_1"], st.session_state.candidats_df["Voeu_2"], st.session_state.candidats_df["Voeu_3"]])
    all_voeux = all_voeux[all_voeux != ""]
    tension = all_voeux.value_counts().head(10).reset_index()
    tension.columns = ["Poste", "Nombre de demandes"]
    st.bar_chart(tension, x="Poste", y="Nombre de demandes", color="#2E86C1")

# --- TAB 2 : GESTION CANDIDATS & RDV ---
with tab2:
    st.subheader("Planning et Suivi des Entretiens")
    
    # Sélecteur de candidat
    selected_name = st.selectbox("Rechercher un collaborateur :", st.session_state.candidats_df["Nom"].tolist())
    idx = st.session_state.candidats_df[st.session_state.candidats_df["Nom"] == selected_name].index[0]
    cand = st.session_state.candidats_df.loc[idx]

    with st.container(border=True):
        col_info, col_action = st.columns([1, 1])
        
        with col_info:
            st.markdown(f"### {cand['Nom']}")
            st.write(f"📍 **Poste actuel :** {cand['Poste_Actuel']}")
            st.write(f"📅 **RDV Planifié :** {cand['Date_RDV']}")
            st.markdown("---")
            st.write(f"🎯 **Vœu 1 :** {cand['Voeu_1']}")
            st.write(f"🎯 **Vœu 2 :** {cand['Voeu_2'] if cand['Voeu_2'] else '-'}")
            st.write(f"🎯 **Vœu 3 :** {cand['Voeu_3'] if cand['Voeu_3'] else '-'}")

        with col_action:
            new_status = st.selectbox("Modifier Statut RDV", ["Planifié", "Réalisé", "Annulé"], index=0)
            new_val = st.selectbox("Décision Finale", ["En attente", "Validé", "Refusé"], 
                                   index=["En attente", "Validé", "Refusé"].index(cand["Validation"]))
            new_comm = st.text_area("Compte-rendu Entretien", value=cand["Commentaires"])
            
            if st.button("Sauvegarder les modifications"):
                st.session_state.candidats_df.at[idx, "Statut_RDV"] = new_status
                st.session_state.candidats_df.at[idx, "Validation"] = new_val
                st.session_state.candidats_df.at[idx, "Commentaires"] = new_comm
                
                # LOGIQUE IMPACT : Si validé, le poste actuel devient OUVERT
                if new_val == "Validé":
                    poste_a_liberer = cand["Poste_Actuel"]
                    ref_idx = st.session_state.ref_df[st.session_state.ref_df["Titre"] == poste_a_liberer].index
                    if not ref_idx.empty:
                        st.session_state.ref_df.at[ref_idx[0], "Statut_Actuel"] = "Ouvert"
                        st.toast(f"Le poste '{poste_a_liberer}' est désormais ouvert !", icon="🔓")
                
                st.success("Données mises à jour.")
                st.rerun()

# --- TAB 3 : ORGANIGRAMME DYNAMIQUE ---
with tab3:
    st.subheader("Référentiel des Postes en Temps Réel")
    st.info("Les postes en statut 'Ouvert' incluent les postes vacants initiaux ET les postes libérés par les mobilités validées.")
    
    # Filtres
    f_dir = st.multiselect("Filtrer par Direction", st.session_state.ref_df["Direction"].unique())
    f_statut = st.multiselect("Filtrer par Statut", ["Ouvert", "Occupé"], default=["Ouvert", "Occupé"])
    
    display_ref = st.session_state.ref_df.copy()
    if f_dir:
        display_ref = display_ref[display_ref["Direction"].isin(f_dir)]
    if f_statut:
        display_ref = display_ref[display_ref["Statut_Actuel"].isin(f_statut)]
        
    st.dataframe(display_ref, use_container_width=True, height=500)
