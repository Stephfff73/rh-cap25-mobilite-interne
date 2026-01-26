import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="🚀 CAP25 - Mobilité Interne - Back-Office RH", layout="wide", page_icon="🏢")

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
        # 3 voeux pour la majorité
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

# --- INITIALISATION SESSION ---
if 'ref_df' not in st.session_state:
    st.session_state.ref_df = get_referentiel()

if 'candidats_df' not in st.session_state:
    st.session_state.candidats_df = get_mock_candidates(st.session_state.ref_df)

# --- INTERFACE ---
st.title("🚀 Back-Office Mobilité RH | Projet CAP25")

# --- SIDEBAR (CARTE BLANCHE: EXPORT) ---
with st.sidebar:
    st.header("Outils RH")
    st.info("Données synchronisées (Mode Simulation)")
    # Fonction Export CSV
    csv_data = st.session_state.candidats_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Exporter les données (Excel/CSV)",
        data=csv_data,
        file_name='suivi_mobilite_cap25.csv',
        mime='text/csv',
    )
    st.markdown("---")
    st.caption("Version Beta 1.2")

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 Tableau de Bord", "🗓️ Gestion Candidats", "📋 Analyse par Poste", "🌳 Organigramme"])

# --- TAB 1 : DASHBOARD ---
with tab1:
    st.subheader("Indicateurs Clés")
    c1, c2, c3, c4 = st.columns(4)
    nb_candidats = len(st.session_state.candidats_df)
    postes_ouverts = len(st.session_state.ref_df[st.session_state.ref_df["Statut_Actuel"]=="Ouvert"])
    
    c1.metric("Candidatures reçues", nb_candidats)
    c2.metric("Postes Ouverts", postes_ouverts)
    c3.metric("Entretiens Planifiés", nb_candidats)
    c4.metric("Validations", len(st.session_state.candidats_df[st.session_state.candidats_df["Validation"]=="Validé"]))

    st.divider()
    st.subheader("Top 10 des Postes les plus demandés")
    all_voeux = pd.concat([st.session_state.candidats_df["Voeu_1"], st.session_state.candidats_df["Voeu_2"], st.session_state.candidats_df["Voeu_3"]])
    all_voeux = all_voeux[all_voeux != ""]
    tension = all_voeux.value_counts().head(10).reset_index()
    tension.columns = ["Poste", "Nombre de demandes"]
    st.bar_chart(tension, x="Poste", y="Nombre de demandes", color="#2E86C1")

# --- TAB 2 : GESTION CANDIDATS ---
with tab2:
    st.subheader("Suivi individuel")
    
    selected_name = st.selectbox("Rechercher un collaborateur :", st.session_state.candidats_df["Nom"].tolist())
    idx = st.session_state.candidats_df[st.session_state.candidats_df["Nom"] == selected_name].index[0]
    cand = st.session_state.candidats_df.loc[idx]

    with st.container(border=True):
        col_info, col_action = st.columns([1, 1])
        with col_info:
            st.markdown(f"### 👤 {cand['Nom']}")
            st.write(f"**Poste actuel :** {cand['Poste_Actuel']}")
            st.write(f"**Date RDV :** {cand['Date_RDV']}")
            st.info(f"1️⃣ {cand['Voeu_1']}\n\n2️⃣ {cand['Voeu_2']}\n\n3️⃣ {cand['Voeu_3']}")

        with col_action:
            new_status = st.selectbox("Statut RDV", ["Planifié", "Réalisé", "Annulé"], index=["Planifié", "Réalisé", "Annulé"].index(cand.get("Statut_RDV", "Planifié")))
            new_val = st.selectbox("Décision", ["En attente", "Validé", "Refusé"], index=["En attente", "Validé", "Refusé"].index(cand["Validation"]))
            new_comm = st.text_area("Notes", value=cand["Commentaires"])
            
            if st.button("Enregistrer modification"):
                st.session_state.candidats_df.at[idx, "Statut_RDV"] = new_status
                st.session_state.candidats_df.at[idx, "Validation"] = new_val
                st.session_state.candidats_df.at[idx, "Commentaires"] = new_comm
                
                # Mise à jour organigramme si validé
                if new_val == "Validé":
                    poste_a_liberer = cand["Poste_Actuel"]
                    ref_idx = st.session_state.ref_df[st.session_state.ref_df["Titre"] == poste_a_liberer].index
                    if not ref_idx.empty:
                        st.session_state.ref_df.at[ref_idx[0], "Statut_Actuel"] = "Ouvert"
                st.success("Mise à jour effectuée !")
                st.rerun()

# --- TAB 3 : ANALYSE PAR POSTE (NOUVEAU) ---
with tab3:
    st.subheader("🎯 Vivier par Poste")
    
    # Préparation des données pivotées
    # On crée un dictionnaire : Poste -> Liste des candidats
    job_map = {}
    
    # On initialise avec tous les postes ouverts
    for poste in st.session_state.ref_df[st.session_state.ref_df["Statut_Actuel"] == "Ouvert"]["Titre"]:
        job_map[poste] = []

    # On remplit avec les candidats
    for idx, row in st.session_state.candidats_df.iterrows():
        for i, col_voeu in enumerate(["Voeu_1", "Voeu_2", "Voeu_3"], 1):
            poste_vise = row[col_voeu]
            if poste_vise and poste_vise in job_map:
                job_map[poste_vise].append(f"{row['Nom']} (Vœu {i})")

    # Conversion en DataFrame pour affichage
    display_data = []
    for poste, candidats in job_map.items():
        nb = len(candidats)
        alert = "⚠️ Zéro Candidat" if nb == 0 else "✅ Vivier actif"
        display_data.append({
            "Poste": poste,
            "Nb Candidatures": nb,
            "Alerte": alert,
            "Détails Candidats": ", ".join(candidats) if nb > 0 else "-"
        })
    
    df_jobs = pd.DataFrame(display_data)

    # Filtres
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        show_zeros = st.checkbox("Afficher uniquement les postes sans candidat", value=False)
    
    if show_zeros:
        df_jobs = df_jobs[df_jobs["Nb Candidatures"] == 0]
    
    # Affichage avec mise en forme
    # On trie pour mettre les postes les plus demandés en haut
    df_jobs = df_jobs.sort_values(by="Nb Candidatures", ascending=False)

    st.dataframe(
        df_jobs,
        column_config={
            "Alerte": st.column_config.TextColumn(
                "Statut",
                help="Alerte si aucun candidat positionné",
                validate="^✅"
            ),
            "Nb Candidatures": st.column_config.ProgressColumn(
                "Volume",
                format="%d",
                min_value=0,
                max_value=max(df_jobs["Nb Candidatures"]) if not df_jobs.empty else 1,
            ),
        },
        use_container_width=True,
        hide_index=True
    )

# --- TAB 4 : ORGANIGRAMME ---
with tab4:
    st.subheader("Vue d'ensemble des Postes")
    f_statut = st.radio("Afficher :", ["Tous", "Ouverts uniquement"], horizontal=True)
    
    view_df = st.session_state.ref_df.copy()
    if f_statut == "Ouverts uniquement":
        view_df = view_df[view_df["Statut_Actuel"] == "Ouvert"]
        
    st.dataframe(view_df, use_container_width=True)
