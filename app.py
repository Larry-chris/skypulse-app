import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from atproto import Client

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="SkyPulse by L", 
    page_icon="⚡",
    layout="centered"
)

# --- 2. CORE FUNCTIONS ---

def connect_user(handle, password):
    """Attempt to connect user to BlueSky API."""
    try:
        client = Client()
        client.login(handle, password)
        return client
    except Exception as e:
        return None

def run_ghost_buster(client):
    """
    Main Algorithm: Demo Mode (Hides results to create desire).
    """
    st.subheader("👻 Ghost Buster (Inactive Detector)")
    
    # Mode selection
    scan_type = st.radio(
        "Who do you want to scan?",
        ["My Following (People I follow)", "My Followers (People following me)"],
        horizontal=True
    )
    
    if "Following" in scan_type:
        st.info("ℹ️ Useful to clean your feed from inactive users.")
        api_method = "get_follows"
    else:
        st.info("ℹ️ Useful to remove 'dead weight' hurting your engagement rate.")
        api_method = "get_followers"

    # ACTION BUTTON
    if st.button("Start Scan 🔎", type="primary"):
        
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            # A. Get User DID
            my_did = client.me.did
            
            with st.spinner("Fetching profiles..."):
                if api_method == "get_followers":
                    # Limit set to 50 for the demo to be fast but meaningful
                    response = client.app.bsky.graph.get_followers(params={'actor': my_did, 'limit': 50})
                    profiles = response.followers
                else:
                    response = client.app.bsky.graph.get_follows(params={'actor': my_did, 'limit': 50})
                    profiles = response.follows
            
            if not profiles:
                st.warning("No profiles found in this list.")
                return

            ghost_data = []
            now = datetime.now(timezone.utc)
            total_profiles = len(profiles)

            # B. Analysis Loop
            for i, profile in enumerate(profiles):
                handle = profile.handle
                status_text.text(f"Scanning: @{handle} ({i+1}/{total_profiles})")
                
                days_inactive = 0
                status_label = "Active"
                formatted_date = "No posts"
                is_ghost = False

                try:
                    # Fetch latest post
                    feed_response = client.app.bsky.feed.get_author_feed(
                        params={'actor': profile.did, 'limit': 1}
                    )
                    
                    if feed_response.feed:
                        post = feed_response.feed[0].post
                        raw_date = post.record.created_at
                        
                        # Date cleaning
                        if raw_date.endswith('Z'):
                            raw_date = raw_date.replace('Z', '+00:00')
                        
                        post_dt = datetime.fromisoformat(raw_date)
                        
                        # Calculation
                        diff = now - post_dt
                        days_inactive = diff.days
                        formatted_date = post_dt.strftime("%Y-%m-%d")
                        
                        # VERDICT (Threshold: 90 days)
                        if days_inactive > 90:
                            status_label = "👻 Inactive"
                            is_ghost = True
                        else:
                            status_label = "✅ Active"
                    else:
                        days_inactive = 9999
                        status_label = "👻 Inactive (Never)"
                        is_ghost = True

                except Exception:
                    formatted_date = "Unknown"
                    status_label = "❓ Private/Error"
                    days_inactive = -1

                # --- STORE FULL URL ---
                full_url = f"https://bsky.app/profile/{handle}"

                ghost_data.append({
                    "Handle": full_url, 
                    "Last Post": formatted_date,
                    "Days Inactive": days_inactive if days_inactive != 9999 else "Never",
                    "Status": status_label,
                    "is_ghost": is_ghost
                })
                
                progress_bar.progress((i + 1) / total_profiles)

            # C. Results Processing
            status_text.empty()
            progress_bar.empty()

            df = pd.DataFrame(ghost_data)
            
            if not df.empty:
                # KPIs Calculation
                nb_analyzed = len(df)
                nb_ghosts = len(df[df['is_ghost'] == True])
                inactivity_rate = (nb_ghosts / nb_analyzed) * 100 if nb_analyzed > 0 else 0

                # Display KPIs
                st.divider()
                kpi1, kpi2, kpi3 = st.columns(3)
                kpi1.metric("Scanned", nb_analyzed)
                kpi2.metric("Ghosts Found", f"{nb_ghosts} 👻")
                
                delta_msg = "- Healthy" if inactivity_rate < 30 else "+ Critical"
                kpi3.metric("Inactivity Rate", f"{inactivity_rate:.1f} %", delta=delta_msg, delta_color="inverse")
                st.divider()

                # --- STRATEGY: DEMO MODE ---
                # Separate ghosts from active users
                df_ghosts = df[df['is_ghost'] == True]
                df_active = df[df['is_ghost'] == False]
                
                # We only show the top 3 ghosts
                preview_ghosts = df_ghosts.head(3)
                
                # Combine active users + 3 ghosts for the table display
                display_df = pd.concat([preview_ghosts, df_active]).drop(columns=['is_ghost'])
                
                # TEASER MESSAGE
                if len(df_ghosts) > 3:
                    hidden_count = len(df_ghosts) - 3
                    st.warning(f"⚠️ **Demo Mode:** Showing 3 ghosts out of {len(df_ghosts)} detected.")
                    st.info(f"🔒 **{hidden_count} other ghosts** are hidden. Full access & payments coming **Late January** after my Med School exams! 🩺💊")
                
                st.write(f"### Results ({scan_type})")
                st.caption("💡 Click on a handle to open the profile on BlueSky.")

                # Highlighting logic
                def highlight_ghosts(row):
                    if 'Inactive' in str(row['Status']):
                        return ['background-color: #ffe6e6; color: #b30000'] * len(row)
                    return [''] * len(row)

                # Display Table
                st.dataframe(
                    display_df.style.apply(highlight_ghosts, axis=1),
                    use_container_width=True,
                    column_config={
                        "Handle": st.column_config.LinkColumn(
                            "Handle (Link)",
                            display_text="https://bsky\\.app/profile/(.*)" 
                        ),
                        "Days Inactive": st.column_config.NumberColumn(
                            "Days Inactive",
                            format="%d days"
                        )
                    }
                )
                
                # LOCKED BUTTON
                if len(df_ghosts) > 3:
                    st.markdown("---")
                    st.button(f"🔓 Unlock all {len(df_ghosts)} ghosts (Coming Jan 24)", disabled=True)
                else:
                    st.success("Scan complete! No hidden ghosts found in this batch.")

        except Exception as e:
            st.error(f"Technical error: {e}")

# --- 3. USER INTERFACE (UI) ---

# Session Init
if 'client_connected' not in st.session_state:
    st.session_state.client_connected = False
if 'my_client' not in st.session_state:
    st.session_state.my_client = None

# A. SIDEBAR (LOGIN)
with st.sidebar:
    st.header("🔐 Member Area")
    
    if not st.session_state.client_connected:
        st.info("Your credentials are NOT stored.")
        user_handle = st.text_input("BlueSky Handle", placeholder="ex: user.bsky.social")
        user_password = st.text_input("App Password", type="password", help="Get it in Settings > Privacy > App Passwords")
        
        if st.button("Connect"):
            if user_handle and user_password:
                with st.spinner("Connecting..."):
                    client = connect_user(user_handle, user_password)
                    if client:
                        st.session_state.client_connected = True
                        st.session_state.my_client = client
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")
            else:
                st.warning("Please fill in both fields.")
    else:
        st.success("✅ Connected")
        if st.button("Logout"):
            st.session_state.client_connected = False
            st.session_state.my_client = None
            st.rerun()

# B. MAIN PAGE
st.title("⚡ SkyPulse by L")

if st.session_state.client_connected:
    # Connected Mode
    client = st.session_state.my_client
    try:
        me = client.get_profile(client.me.did)
        st.write(f"Welcome, **{me.handle}** 👋")
        
        col1, col2 = st.columns(2)
        col1.info(f"Followers: {me.followers_count}")
        col2.info(f"Following: {me.follows_count}")
        
        st.markdown("---")
        
        # Run App
        run_ghost_buster(client)
            
    except Exception as e:
        st.error("Session expired. Please reconnect.")
        st.session_state.client_connected = False

else:
    # Guest Mode (Landing)
    st.markdown("### The Analytics Tool for BlueSky Creators.")
    st.write("Detect inactive accounts and clean your audience.")
    st.image("https://media.giphy.com/media/l0HlHFRbmaZtBRhXG/giphy.gif")
    st.info("👈 Login in the sidebar to start scanning.")

# --- PREMIUM SECTION (Teasing) ---
st.markdown("---")
st.subheader("💎 Premium Version (Paused)")

col_p1, col_p2 = st.columns([2, 1])

with col_p1:
    st.write("**Full Access includes:**")
    st.write("✅ Unlimited Ghost Detection")
    st.write("✅ One-click profile access")
    st.write("✅ Priority Support")

with col_p2:
    st.metric(label="Status", value="Study Break 📚")
    st.button("Back on Jan 24", disabled=True, help="Dev is taking exams!")

# --- 4. FOOTER ---
st.markdown("---")
col_f1, col_f2 = st.columns(2)

with col_f1:
    st.caption("© 2025 **L • Vertical Studio**")
    st.caption("Crafted in Benin 🇧🇯")
    # Replace '#' with your Notion link if you have it
    st.markdown("[Privacy & Terms](#)", unsafe_allow_html=True) 

with col_f2:
    st.markdown(
        """
        <div style="text-align: right;">
            <a href="https://bsky.app/profile/l-studio.bsky.social" target="_blank" style="text-decoration: none; color: grey;">
                Need help? Contact Founder ↗
            </a>
        </div>
        """, 
        unsafe_allow_html=True
    )
