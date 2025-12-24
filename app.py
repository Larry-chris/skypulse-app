import streamlit as st
import pandas as pd
from datetime import datetime, timezone
# Assurez-vous que 'client' est importé ou accessible ici
from atproto import Client

# Configuration de la page
st.set_page_config(page_title="SkyPulse by L", page_icon="⚡")

# Titre
st.title("⚡ SkyPulse - Module de Connexion")
st.markdown("---")

# Fonction de connexion (mise en cache pour ne pas se reconnecter à chaque clic)
@st.cache_resource
def connect_to_bluesky():
    try:
        client = Client()
        # On récupère les infos depuis le fichier secrets.toml
        client.login(st.secrets["bluesky"]["handle"], st.secrets["bluesky"]["password"])
        return client
    except Exception as e:
        return None

# Le Cerveau de l'App
st.write("Tentative de connexion au réseau BlueSky...")

client = connect_to_bluesky()

if client:
    # Si la connexion réussit
    st.success("✅ CONNEXION ÉTABLIE : Accès autorisé.")
    
    # On récupère tes infos de profil
    me = client.get_profile(st.secrets["bluesky"]["handle"])
    
    # On affiche les stats (Dashboard)
    col1, col2, col3 = st.columns(3)
    col1.metric("Mon Pseudo", me.handle)
    col2.metric("Abonnés (Followers)", me.followers_count)
    col3.metric("Abonnements (Follows)", me.follows_count)
    
    st.write(f"Description du profil : *{me.description}*")
    
else:
    # Si ça échoue
    st.error("❌ ÉCHEC DE CONNEXION. Vérifie ton fichier secrets.toml")


import streamlit as st
import pandas as pd
from datetime import datetime, timezone

def run_ghost_buster(client):
    """
    Analyse les 20 premiers followers, calcule les métriques d'inactivité 
    et affiche les résultats avec un code couleur.
    """
    st.subheader("👻 Ghost Buster (Détection d'inactifs)")

    try:
        # 1. Récupérer mon DID
        my_did = client.me.did
        
        # 2. Récupérer les 20 premiers followers
        with st.spinner("Récupération de la liste des followers..."):
            response = client.app.bsky.graph.get_followers(params={'actor': my_did, 'limit': 20})
            followers = response.followers
        
        if not followers:
            st.warning("Vous n'avez pas encore de followers à analyser.")
            return

        ghost_data = []
        now = datetime.now(timezone.utc)
        
        # Initialisation de la barre de progression
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_followers = len(followers)

        # 3. Boucle d'analyse sur chaque follower
        for i, follower in enumerate(followers):
            handle = follower.handle
            status_text.text(f"Scan du profil : @{handle} ({i+1}/{total_followers})")
            
            last_post_date = None
            days_inactive = 0
            status_label = "Actif"
            formatted_date = "Aucun post"
            is_ghost = False

            try:
                # Récupérer le dernier post du feed (limit=1)
                feed_response = client.app.bsky.feed.get_author_feed(
                    params={'actor': follower.did, 'limit': 1}
                )
                
                if feed_response.feed:
                    post = feed_response.feed[0].post
                    raw_date = post.record.created_at
                    
                    # Nettoyage de la date ISO
                    if raw_date.endswith('Z'):
                        raw_date = raw_date.replace('Z', '+00:00')
                    
                    post_dt = datetime.fromisoformat(raw_date)
                    
                    # Calcul
                    diff = now - post_dt
                    days_inactive = diff.days
                    formatted_date = post_dt.strftime("%d/%m/%Y")
                    
                    # Vérification du seuil de 90 jours
                    if days_inactive > 90:
                        status_label = "👻 Inactif"
                        is_ghost = True
                    else:
                        status_label = "✅ Actif"
                else:
                    # Jamais posté
                    days_inactive = 9999
                    status_label = "👻 Inactif (Jamais posté)"
                    is_ghost = True

            except Exception:
                formatted_date = "Erreur accès"
                status_label = "❓ Inconnu"
                days_inactive = -1

            ghost_data.append({
                "Pseudo": f"@{handle}",
                "Dernier Post": formatted_date,
                "Jours Inactif": days_inactive if days_inactive != 9999 else "N/A",
                "Statut": status_label,
                "is_ghost": is_ghost  # Colonne cachée utile pour le calcul
            })
            
            # Mise à jour progression
            progress_bar.progress((i + 1) / total_followers)

        # Nettoyage UI
        status_text.empty()
        progress_bar.empty()

        # 4. Calculs des Métriques
        df = pd.DataFrame(ghost_data)
        
        if not df.empty:
            nb_analyzed = len(df)
            nb_ghosts = len(df[df['is_ghost'] == True])
            
            if nb_analyzed > 0:
                inactivity_rate = (nb_ghosts / nb_analyzed) * 100
            else:
                inactivity_rate = 0

            # --- AFFICHAGE DES MÉTRIQUES (Haut de page) ---
            st.divider()
            kpi1, kpi2, kpi3 = st.columns(3)

            # Métrique 1 : Total analysé
            kpi1.metric(
                label="Abonnés Analysés",
                value=nb_analyzed
            )

            # Métrique 2 : Nombre de fantômes
            kpi2.metric(
                label="Fantômes Détectés",
                value=f"{nb_ghosts} 👻"
            )

            # Métrique 3 : Taux d'inactivité (Vert si bas, Rouge si haut)
            # Astuce : delta_color="inverse" rend le delta positif ROUGE et négatif VERT.
            rate_formatted = f"{inactivity_rate:.1f} %"
            
            if inactivity_rate < 30:
                # Taux faible = Bien = Vert -> On utilise un delta négatif en mode inverse
                delta_val = "- Faible (Sain)"
            else:
                # Taux élevé = Pas bien = Rouge -> On utilise un delta positif en mode inverse
                delta_val = "+ Élevé (Critique)"

            kpi3.metric(
                label="Taux d'inactivité",
                value=rate_formatted,
                delta=delta_val,
                delta_color="inverse"
            )
            st.divider()

            # --- AFFICHAGE DU TABLEAU ---
            st.write("### Détail par abonné")

            # Fonction de style pour le tableau
            def highlight_row(row):
                # Si le statut contient Inactif, on colore la ligne en rouge clair
                if 'Inactif' in str(row['Statut']):
                    return ['background-color: #ffe6e6; color: #9c0000'] * len(row)
                return [''] * len(row)

            # On masque la colonne technique 'is_ghost' pour l'affichage
            display_df = df.drop(columns=['is_ghost'])

            st.dataframe(
                display_df.style.apply(highlight_row, axis=1),
                use_container_width=True,
                height=500
            )

        else:
            st.write("Aucune donnée récupérée.")

    except Exception as e:
        st.error(f"Une erreur est survenue : {e}")

# --- Bloc d'exécution dans l'interface ---
# Ce bloc vérifie si le client existe et lance la fonction au clic
if st.button("Lancer le Ghost Buster 👻", type="primary"):
    if 'client' in st.session_state:
        run_ghost_buster(st.session_state.client)
    elif 'client' in locals():
        run_ghost_buster(client)
    else:
        st.error("Erreur : Veuillez d'abord vous connecter à Bluesky.")