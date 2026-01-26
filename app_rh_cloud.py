import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="🚀 CAP25 - Pilotage Mobilité", layout="wide", page_icon="🏢")

# --- 1. RÉFÉRENTIEL DES POSTES ---
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
        ["Direction de l'Exploitation et du Territoire", "Directeur(ice) Pôle Territorial", "Oui"],
        ["Direction de l'Exploitation et du Territoire", "Responsable d’Actifs Immobiliers", "Oui"],
        ["Direction de l'Exploitation et du Territoire", "Responsable Exploitation et Maintenance", "Oui"],
        ["Direction de l'Exploitation et du Territoire", "Responsable Pôle Technique Territorial", "Oui"],
        ["Direction des Opérations Clients", "Chargé(e) d’Affaires Immobilières", "Oui"],
        ["Direction des Opérations Clients", "Chargé(e) de Facturation", "Oui"],
        ["Direction des Opérations Clients", "Chargé(e) de Recouvrement Amiable", "Oui"],
        ["Direction des Opérations Clients", "Directeur(ice) des Opérations Clients", "Oui"],
        ["Direction des Opérations Clients", "Gestionnaire de Charges Locatives", "Oui"],
        ["Direction des Opérations Clients", "Gestionnaire Recouvrement Contentieux", "Oui"],
        ["Direction des Opérations Clients", "Responsable d’Equipe Recouvrement et Action Sociale", "Oui"],
        ["Direction des Opérations Clients", "Responsable Pôle Affaires Immobilières", "Oui"],
        ["Direction des Opérations Clients", "Responsable Pôle Charges Locatives", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Chargé(e) d’Opérations", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Chargé(e) de mission Contrats de Services", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Chef(fe) de projet Programmation et CSP", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Chef(fe) de Projets Immobiliers", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Directeur(ice) de Projets", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Directeur(ice) Opérationnel(le) Contrats", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Directeur(ice) Opérationnel(le) Réhabilitation", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Gestionnaire Financier(e) Marchés et Contrats", "Oui"],
        ["Direction Technique du Patrimoine Immobilier", "Responsable Stratégie Patrimoniale et Programmation", "Oui"],
        ["Direction Ventes et Copropriété", "Chargé(e) de Gestion Documentaire", "Oui"],
        ["Direction Ventes et Copropriété", "Chargé(e) de Montage Juridique", "Oui"],
        ["Direction Ventes et Copropriété", "Chargé(e) de Montage Technique et Administratif", "Oui"],
        ["Direction Ventes et Copropriété", "Chargé(e) des Ventes (interne)", "Oui"],
        ["Direction Ventes et Copropriété", "Gestionnaire Administration des Ventes", "Oui"],
        ["Gestion de Portefeuille", "Responsable de Portefeuille", "Oui"],
        ["Pôle Professionnel", "Chargé(e) d’Affaires Résidences Gérées", "Oui"],
    ]
    df = pd.DataFrame(data, columns=["Direction", "Titre", "Ouvert_Initialement"])
    df["Statut_Actuel"] = df["Ouvert_Initialement"].apply(lambda x: "Ouvert" if x == "Oui" else "Occupé")
    return df

# --- 2. GÉNÉRATION DES DONNÉES FICTIVES ---
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
        nb_voeux = 3 if i < 15 else random.randint(1, 2)
        voeux = random.sample(postes_ouverts, nb_voeux)
        while len(voeux) < 3: voeux.append("")
        date_rdv = start_date + timedelta(days=random.randint(0, 17))
        candidates.append({
            "Nom": nom, "Poste_Actuel": random.choice(postes_occupes),
            "Voeu_1": voeux[0], "Voeu_2": voeux[1], "Voeu_3": voeux[2],
            "Date_RDV": date_rdv.strftime("%d/%m/%Y"), "Statut_RDV": "Planifié",
            "Commentaires": "", "Validation": "En attente"
        })
    return pd.DataFrame(candidates)

# --- INITIALISATION ---
if 'ref_df' not in st.session_state: st.session_state.ref_df = get_referentiel()
if 'candidats_df' not in st.session_state: st.session_state.candidats_df = get_mock_candidates(st.session_state.ref_df)

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 Tableau de Bord", "👥 Suivi Individuel", "🎯 Analyse par Poste", "🌳 Organigramme"])

# --- TAB 1 : DASHBOARD ---
with tab1:
    st.subheader("Pilotage Stratégique")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Candidatures", len(st.session_state.candidats_df))
    c2.metric("Postes à pourvoir", len(st.session_state.ref_df[st.session_state.ref_df["Statut_Actuel"]=="Ouvert"]))
    c3.metric("Entretiens", "20")
    c4.metric("Mobilités Validées", len(st.session_state.candidats_df[st.session_state.candidats_df["Validation"]=="Validé"]))

    st.divider()
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("**🔥 Top 10 des Postes les plus demandés **")
        all_v = pd.concat([st.session_state.candidats_df["Voeu_1"], st.session_state.candidats_df["Voeu_2"], st.session_state.candidats_df["Voeu_3"]])
        tension = all_v[all_v != ""].value_counts().head(10)
        st.bar_chart(tension, color="#FF4B4B")

    with col_chart2:
        st.markdown("**🏢 Pression de mobilité par Direction**")
        # On calcule le nombre de voeux total par direction
        temp_df = st.session_state.ref_df.copy()
        temp_df['Demandes'] = temp_df['Titre'].apply(lambda x: (all_v == x).sum())
        dir_tension = temp_df.groupby('Direction')['Demandes'].sum().sort_values(ascending=False)
        st.bar_chart(dir_tension, color="#2E86C1")

# --- TAB 2 : SUIVI INDIVIDUEL ---
with tab2:
    st.subheader("Gestion des Candidatures")
    selected_name = st.selectbox("Sélectionner un collaborateur :", st.session_state.candidats_df["Nom"].tolist(), key="main_search")
    idx = st.session_state.candidats_df[st.session_state.candidats_df["Nom"] == selected_name].index[0]
    cand = st.session_state.candidats_df.loc[idx]

    with st.container(border=True):
        col_info, col_action = st.columns(2)
        with col_info:
            st.write(f"### {cand['Nom']}")
            st.write(f"**📍 Actuellement :** {cand['Poste_Actuel']}")
            st.write(f"**📅 Entretien :** {cand['Date_RDV']}")
            st.success(f"**Vœu 1 :** {cand['Voeu_1']}")
            st.info(f"**Vœu 2 :** {cand['Voeu_2'] if cand['Voeu_2'] else '-'}")
            st.info(f"**Vœu 3 :** {cand['Voeu_3'] if cand['Voeu_3'] else '-'}")
        with col_action:
            v = st.selectbox("Décision RH", ["En attente", "Validé", "Refusé"], index=["En attente", "Validé", "Refusé"].index(cand["Validation"]))
            c = st.text_area("Notes", value=cand["Commentaires"])
            if st.button("Sauvegarder"):
                st.session_state.candidats_df.at[idx, "Validation"] = v
                st.session_state.candidats_df.at[idx, "Commentaires"] = c
                st.success("Enregistré !")

# --- TAB 3 : ANALYSE PAR POSTE ---
with tab3:
    st.subheader("🎯 Analyse des Viviers")
    
    # Construction de la matrice
    job_analysis = []
    postes_cibles = st.session_state.ref_df[st.session_state.ref_df["Statut_Actuel"] == "Ouvert"]["Titre"].tolist()
    
    for p in postes_cibles:
        cands_for_p = []
        for _, row in st.session_state.candidats_df.iterrows():
            if row["Voeu_1"] == p: cands_for_p.append(f"{row['Nom']} (V1)")
            elif row["Voeu_2"] == p: cands_for_p.append(f"{row['Nom']} (V2)")
            elif row["Voeu_3"] == p: cands_for_p.append(f"{row['Nom']} (V3)")
        
        job_analysis.append({
            "Poste": p, "Nb": len(cands_for_p),
            "Candidats": cands_for_p,
            "Statut": "⚠️ Zéro" if len(cands_for_p) == 0 else "✅ Actif"
        })
    
    df_analysis = pd.DataFrame(job_analysis)
    
    # Filtre Alerte
    if st.checkbox("Afficher uniquement les postes sans candidat ⚠️"):
        df_analysis = df_analysis[df_analysis["Nb"] == 0]

    # Sécurisation du max_value pour le ProgressColumn
    max_nb = max(df_analysis["Nb"].max(), 1) if not df_analysis.empty else 1

    st.dataframe(
        df_analysis,
        column_config={
            "Nb": st.column_config.ProgressColumn("Volume", min_value=0, max_value=int(max_nb), format="%d"),
            "Candidats": st.column_config.ListColumn("Détail du Vivier"),
        },
        use_container_width=True, hide_index=True
    )
    
    st.divider()
    st.markdown("🔍 **Consultation rapide d'un candidat du vivier**")
    all_names = sorted(list(set([name.split(" (")[0] for sublist in df_analysis["Candidats"] for name in sublist])))
    name_to_check = st.selectbox("Choisir un nom pour voir son profil complet :", ["-"] + all_names)
    
    if name_to_check != "-":
        profile = st.session_state.candidats_df[st.session_state.candidats_df["Nom"] == name_to_check].iloc[0]
        st.info(f"**Profil de {name_to_check}** | Poste Actuel : {profile['Poste_Actuel']} | Vœux : {profile['Voeu_1']}, {profile['Voeu_2']}, {profile['Voeu_3']}")

# --- TAB 4 : ORGANIGRAMME ---
with tab4:
    st.subheader("Référentiel Dynamique")
    col_f1, col_f2, col_f3 = st.columns([1, 1, 1])
    with col_f1:
        search_job = st.text_input("🔍 Rechercher un poste (ex: Manager)")
    with col_f2:
        dir_f = st.multiselect("Filtrer par Direction", st.session_state.ref_df["Direction"].unique())
    with col_f3:
        stat_f = st.multiselect("Filtrer par Statut", ["Ouvert", "Occupé"], default=["Ouvert", "Occupé"])

    df_org = st.session_state.ref_df.copy()
    if search_job: df_org = df_org[df_org["Titre"].str.contains(search_job, case=False)]
    if dir_f: df_org = df_org[df_org["Direction"].isin(dir_f)]
    if stat_f: df_org = df_org[df_org["Statut_Actuel"].isin(stat_f)]

    st.dataframe(df_org, use_container_width=True, hide_index=True)
