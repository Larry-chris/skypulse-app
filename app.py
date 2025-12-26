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
    Algorithme principal : Analyse Followers OU Following avec Tableau Interactif Pro.
    """
    st.subheader("👻 Ghost Buster (Détection d'inactifs)")
    
    # Choix du mode de scan
    scan_type = st.radio(
        "Qui voulez-vous analyser ?",
        ["Mes Abonnements (Les gens que je suis)", "Mes Abonnés (Les gens qui me suivent)"],
        horizontal=True
    )
    
    if "Abonnements" in scan_type:
        st.info("ℹ️ Utile pour nettoyer votre fil d'actualité.")
        api_method = "get_follows"
    else:
        st.info("ℹ️ Utile pour supprimer les comptes inactifs qui vous suivent.")
        api_method = "get_followers"

    # BOUTON DE LANCEMENT
    if st.button("Lancer le Scan 🔎", type="primary"):
        
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            # A. Récupération des données
            my_did = client.me.did
            
            with st.spinner("Récupération de la liste..."):
                if api_method == "get_followers":
                    # Limite à 30 pour la rapidité de la démo
                    response = client.app.bsky.graph.get_followers(params={'actor': my_did, 'limit': 30})
                    profiles = response.followers
                else:
                    response = client.app.bsky.graph.get_follows(params={'actor': my_did, 'limit': 30})
                    profiles = response.follows
            
            if not profiles:
                st.warning("Aucun profil trouvé dans cette liste.")
                return

            ghost_data = []
            now = datetime.now(timezone.utc)
            total_profiles = len(profiles)

            # B. Boucle d'analyse
            for i, profile in enumerate(profiles):
                handle = profile.handle
                status_text.text(f"Scan du profil : @{handle} ({i+1}/{total_profiles})")
                
                days_inactive = 0
                status_label = "Actif"
                formatted_date = "Aucun post"
                is_ghost = False

                try:
                    # Récupérer le dernier post
                    feed_response = client.app.bsky.feed.get_author_feed(
                        params={'actor': profile.did, 'limit': 1}
                    )
                    
                    if feed_response.feed:
                        post = feed_response.feed[0].post
                        raw_date = post.record.created_at
                        
                        # Nettoyage date
                        if raw_date.endswith('Z'):
                            raw_date = raw_date.replace('Z', '+00:00')
                        
                        post_dt = datetime.fromisoformat(raw_date)
                        
                        # Calcul
                        diff = now - post_dt
                        days_inactive = diff.days
                        formatted_date = post_dt.strftime("%d/%m/%Y")
                        
                        # VERDICT (Seuil 90 jours)
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

                # --- ICI : On stocke l'URL complète, pas du HTML ---
                full_url = f"https://bsky.app/profile/{handle}"

                ghost_data.append({
                    "Pseudo": full_url, # L'URL sera transformée en lien propre par Streamlit
                    "Dernier Post": formatted_date,
                    "Jours Inactif": days_inactive if days_inactive != 9999 else "Jamais",
                    "Statut": status_label,
                    "is_ghost": is_ghost
                })
                
                progress_bar.progress((i + 1) / total_profiles)

            # C. Affichage Résultats
            status_text.empty()
            progress_bar.empty()

            df = pd.DataFrame(ghost_data)
            
            if not df.empty:
                # KPIs
                nb_analyzed = len(df)
                nb_ghosts = len(df[df['is_ghost'] == True])
                inactivity_rate = (nb_ghosts / nb_analyzed) * 100 if nb_analyzed > 0 else 0

                st.divider()
                kpi1, kpi2, kpi3 = st.columns(3)
                kpi1.metric("Profils Scannés", nb_analyzed)
                kpi2.metric("Fantômes", f"{nb_ghosts} 👻")
                
                delta_msg = "- Sain" if inactivity_rate < 30 else "+ Critique"
                kpi3.metric("Taux Inactivité", f"{inactivity_rate:.1f} %", delta=delta_msg, delta_color="inverse")
                st.divider()

                st.write(f"### Résultats pour : {scan_type}")
                st.caption("💡 Cliquez sur un pseudo pour ouvrir le profil BlueSky.")

                # Fonction de couleur (Rouge pour les inactifs)
                def highlight_ghosts(row):
                    if 'Inactif' in str(row['Statut']):
                        return ['background-color: #ffe6e6; color: #b30000'] * len(row)
                    return [''] * len(row)

                # Préparation des données (on cache la colonne technique)
                display_df = df.drop(columns=['is_ghost'])
                
                # --- AFFICHAGE TABLEAU MODERNE ---
                st.dataframe(
                    display_df.style.apply(highlight_ghosts, axis=1),
                    use_container_width=True,
                    column_config={
                        "Pseudo": st.column_config.LinkColumn(
                            "Pseudo (Lien)",
                            display_text="https://bsky\\.app/profile/(.*)" # Regex qui extrait le pseudo de l'URL
                        ),
                        "Jours Inactif": st.column_config.NumberColumn(
                            "Jours Inactif",
                            format="%d j"
                        )
                    }
                )
                
                st.success("Analyse terminée !")

        except Exception as e:
            st.error(f"Erreur technique : {e}")

# --- 3. INTERFACE UTILISATEUR (UI) ---

# Initialisation Session
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
                        st.rerun()
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
    # Mode Connecté
    client = st.session_state.my_client
    try:
        me = client.get_profile(client.me.did)
        st.write(f"Bienvenue, **{me.handle}** 👋")
        
        col1, col2 = st.columns(2)
        col1.info(f"Abonnés : {me.followers_count}")
        col2.info(f"Abonnements : {me.follows_count}")
        
        st.markdown("---")
        
        # Appel de la fonction principale
        run_ghost_buster(client)
            
    except Exception as e:
        st.error("Session expirée. Veuillez vous reconnecter.")
        st.session_state.client_connected = False

else:
    # Mode Visiteur (Accueil)
    st.markdown("### L'outil d'analytics pour les créateurs BlueSky.")
    st.write("Détectez les comptes inactifs et nettoyez votre audience.")
    st.image("https://media.giphy.com/media/l0HlHFRbmaZtBRhXG/giphy.gif")
    st.info("👈 Connectez-vous dans le menu à gauche pour commencer.")


# --- SECTION OFFRE PREMIUM (Pour validation Lemon Squeezy) ---
st.markdown("---")
st.subheader("💎 Version Premium (Bientôt disponible)")

col_p1, col_p2 = st.columns([2, 1])

with col_p1:
    st.write("**Débloquez le rapport complet :**")
    st.write("✅ Liste complète des fantômes (+ de 20)")
    st.write("✅ Liens directs pour nettoyage rapide")
    st.write("✅ Support prioritaire")

with col_p2:
    st.metric(label="Prix Unique", value="$4.99")
    st.button("Acheter la version complète", disabled=True, help="L'achat sera activé prochainement")


# --- 4. PIED DE PAGE (FOOTER) ---
st.markdown("---")
col_f1, col_f2 = st.columns(2)

with col_f1:
    st.caption("© 2025 **L • Vertical Studio**")
    st.caption("Crafted in Benin 🇧🇯")
    st.markdown("[Privacy & Terms](https://silicon-worm-596.notion.site/L-Legal-Center-2d50beede63a8070b6f5ec0bcce6e016?source=copy_link)", unsafe_allow_html=True)
with col_f2:
    st.markdown(
        """
        <div style="text-align: right;">
            <a href="https://bsky.app/profile/l-studio.bsky.social" target="_blank" style="text-decoration: none; color: grey;">
                Besoin d'aide ? Contactez le Fondateur ↗
            </a>
        </div>
        """, 
        unsafe_allow_html=True
    )
