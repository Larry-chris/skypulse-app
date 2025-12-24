import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from atproto import Client

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="SkyPulse by L", 
    page_icon="⚡",
    layout="centered"
)

# --- 2. FONCTIONS (LE CERVEAU) ---

def connect_user(handle, password):
    """Tente de connecter l'utilisateur à l'API BlueSky."""
    try:
        client = Client()
        client.login(handle, password)
        return client
    except Exception as e:
        return None

def run_ghost_buster(client):
    """
    Algorithme principal : Analyse les followers et détecte les inactifs.
    """
    st.subheader("👻 Ghost Buster (Détection d'inactifs)")
    
    # Barre de progression
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # A. Récupérer mon DID et mes followers
        my_did = client.me.did
        
        # On limite à 20 pour la démo (sinon c'est long)
        response = client.app.bsky.graph.get_followers(params={'actor': my_did, 'limit': 20})
        followers = response.followers
        
        if not followers:
            st.warning("Vous n'avez pas encore de followers à analyser.")
            return

        ghost_data = []
        now = datetime.now(timezone.utc)
        total_followers = len(followers)

        # B. Boucle d'analyse
        for i, follower in enumerate(followers):
            handle = follower.handle
            status_text.text(f"Scan du profil : @{handle} ({i+1}/{total_followers})")
            
            days_inactive = 0
            status_label = "Actif"
            formatted_date = "Aucun post"
            is_ghost = False

            try:
                # Récupérer le dernier post
                feed_response = client.app.bsky.feed.get_author_feed(
                    params={'actor': follower.did, 'limit': 1}
                )
                
                if feed_response.feed:
                    post = feed_response.feed[0].post
                    raw_date = post.record.created_at
                    
                    # Gestion des formats de date bizarres
                    if raw_date.endswith('Z'):
                        raw_date = raw_date.replace('Z', '+00:00')
                    
                    post_dt = datetime.fromisoformat(raw_date)
                    
                    # Calcul du temps écoulé
                    diff = now - post_dt
                    days_inactive = diff.days
                    formatted_date = post_dt.strftime("%d/%m/%Y")
                    
                    # VERDICT
                    if days_inactive > 90:
                        status_label = "👻 Inactif"
                        is_ghost = True
                    else:
                        status_label = "✅ Actif"
                else:
                    days_inactive = 9999
                    status_label = "👻 Inactif (Jamais posté)"
                    is_ghost = True

            except Exception:
                formatted_date = "Inconnu"
                status_label = "❓ Privé/Erreur"
                days_inactive = -1

            ghost_data.append({
                "Pseudo": f"@{handle}",
                "Dernier Post": formatted_date,
                "Jours Inactif": days_inactive if days_inactive != 9999 else "Jamais",
                "Statut": status_label,
                "is_ghost": is_ghost
            })
            
            # Avancer la barre
            progress_bar.progress((i + 1) / total_followers)

        # C. Affichage des résultats
        status_text.empty()
        progress_bar.empty()

        df = pd.DataFrame(ghost_data)
        
        if not df.empty:
            # Calculs KPI
            nb_analyzed = len(df)
            nb_ghosts = len(df[df['is_ghost'] == True])
            inactivity_rate = (nb_ghosts / nb_analyzed) * 100 if nb_analyzed > 0 else 0

            # Affichage des gros chiffres
            st.divider()
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Abonnés Scannés", nb_analyzed)
            kpi2.metric("Fantômes", f"{nb_ghosts} 👻")
            
            # Couleur dynamique pour le taux
            delta_msg = "- Sain" if inactivity_rate < 30 else "+ Critique"
            kpi3.metric("Taux Inactivité", f"{inactivity_rate:.1f} %", delta=delta_msg, delta_color="inverse")
            st.divider()

            # Affichage du Tableau Coloré
            st.write("### 📋 Détail de l'analyse")

            def highlight_ghosts(row):
                if 'Inactif' in str(row['Statut']):
                    return ['background-color: #ffe6e6; color: #b30000'] * len(row)
                return [''] * len(row)

            # On cache la colonne technique 'is_ghost'
            display_df = df.drop(columns=['is_ghost'])
            
            st.dataframe(
                display_df.style.apply(highlight_ghosts, axis=1),
                use_container_width=True
            )
            
            st.success("Analyse terminée avec succès !")

    except Exception as e:
        st.error(f"Erreur durant l'analyse : {e}")


# --- 3. INTERFACE UTILISATEUR (UI) ---

# Initialisation de la session (mémoire)
if 'client_connected' not in st.session_state:
    st.session_state.client_connected = False
if 'my_client' not in st.session_state:
    st.session_state.my_client = None

# A. BARRE LATÉRALE (LOGIN)
with st.sidebar:
    st.header("🔐 Espace Membre")
    
    if not st.session_state.client_connected:
        st.info("Vos identifiants ne sont PAS stockés.")
        user_handle = st.text_input("Pseudo BlueSky", placeholder="ex: pseudo.bsky.social")
        user_password = st.text_input("App Password", type="password", help="Settings > Privacy > App Passwords")
        
        if st.button("Se connecter"):
            if user_handle and user_password:
                with st.spinner("Connexion..."):
                    client = connect_user(user_handle, user_password)
                    if client:
                        st.session_state.client_connected = True
                        st.session_state.my_client = client
                        st.rerun() # Recharge la page pour afficher le dashboard
                    else:
                        st.error("Mot de passe incorrect.")
            else:
                st.warning("Remplissez les deux champs.")
    else:
        st.success("✅ Connecté")
        if st.button("Se déconnecter"):
            st.session_state.client_connected = False
            st.session_state.my_client = None
            st.rerun()

# B. PAGE PRINCIPALE
st.title("⚡ SkyPulse by L")

if st.session_state.client_connected:
    # L'utilisateur est connecté
    client = st.session_state.my_client
    
    # Récupérer les infos de base
    try:
        me = client.get_profile(client.me.did)
        st.write(f"Bienvenue, **{me.handle}** 👋")
        
        # Dashboard rapide
        col1, col2 = st.columns(2)
        col1.info(f"Abonnés : {me.followers_count}")
        col2.info(f"Abonnements : {me.follows_count}")
        
        st.markdown("---")
        
        # BOUTON D'ACTION
        st.write("Cliquez ci-dessous pour lancer l'algorithme de détection.")
        if st.button("Lancer le Ghost Buster 👻", type="primary"):
            run_ghost_buster(client)
            
    except Exception as e:
        st.error("Session expirée. Veuillez vous reconnecter.")
        st.session_state.client_connected = False

else:
    # L'utilisateur n'est PAS connecté (Page d'accueil)
    st.markdown("### L'outil d'analytics pour les créateurs BlueSky.")
    st.write("Détectez les comptes inactifs et nettoyez votre audience.")
    
    st.image("https://media.giphy.com/media/l0HlHFRbmaZtBRhXG/giphy.gif")
    
    st.info("👈 Connectez-vous dans le menu à gauche pour commencer.")
