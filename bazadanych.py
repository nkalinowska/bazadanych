import streamlit as st
from supabase import create_client
import pandas as pd

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="SmartStock | Magazyn Inteligentny", 
    page_icon="📦", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Stylizacja CSS dla lepszego interfejsu
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="metric-container"] {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #eee;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. POŁĄCZENIE Z BAZĄ ---
@st.cache_resource
def init_connection():
    try:
        # Pobieranie danych z Secrets
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"Błąd połączenia: {e}")
        return None

supabase = init_connection()

# --- 3. LOGIKA DANYCH (CACHE) ---
@st.cache_data(ttl=60)
def get_categories():
    return supabase.table("kategorie").select("*").order("nazwa").execute().data

@st.cache_data(ttl=60)
def get_products():
    return supabase.table("produkty").select("*, kategorie(nazwa)").order("nazwa").execute().data

@st.cache_data(ttl=60)
def get_orders():
    return supabase.table("zamowienia").select("*, produkty(nazwa)").order("created_at", desc=True).execute().data

def refresh_data():
    st.cache_data.clear()

# --- 4. SIDEBAR (PODSUMOWANIE FINANSOWE) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2271/2271062.png", width=80)
    st.title("SmartStock")
    st.divider()
    
    produkty_raw = get_products()
    if produkty_raw:
        # Obliczenia finansowe
        calkowita_wartosc = sum(p['liczba'] * p['cena'] for p in produkty_raw)
        liczba_sztuk = sum(p['liczba'] for p in produkty_raw)
        niski_stan = sum(1 for p in produkty_raw if p['liczba'] < 10)
        
        st.metric("Wartość magazynu", f"{calkowita_wartosc:,.2f} zł")
        st.metric("Suma towarów", f"{liczba_sztuk} szt.")
        st.metric("Alerty (niski stan)", niski_stan, delta=-niski_stan if niski_stan > 0 else 0, delta_color="inverse")
    
    st.divider()
    if st.button("🔄 Odśwież bazę danych", use_container_width=True):
        refresh_data()
        st.rerun()

# --- 5. GŁÓWNY PANEL UI ---
st.title("📦 Zarządzanie Magazynem")

tab1, tab2, tab3, tab4 = st.tabs([
    "🛒 Stan i Inwentaryzacja", 
    "➕ Wydanie Towaru", 
    "📂 Kategorie", 
    "📜 Historia"
])

# --- TAB 1: MAGAZYN ---
with tab1:
    col_search, col_add = st.columns([2, 1])
    
    with col_search:
        szukaj = st.text_input("🔍 Wyszukaj produkt...", placeholder="Wpisz nazwę...")
        
    with col_add:
        with st.expander("➕ Dodaj / Aktualizuj"):
            kats = get_categories()
            if kats:
                kat_map = {k['nazwa']: k['id'] for k in kats}
                with st.form("add_form", clear_on_submit=True):
                    n_nazwa = st.text_input("Nazwa")
                    n_kat = st.selectbox("Kategoria", list(kat_map.keys()))
                    n_cena = st.number_input("Cena jedn. (zł)", min_value=0.0, format="%.2f")
                    n_ilosc = st.number_input("Ilość do dodania", min_value=1)
                    
                    if st.form_submit_button("Zatwierdź"):
                        # Sprawdzanie czy istnieje
                        istnieje = supabase.table("produkty").select("*").ilike("nazwa", n_nazwa).execute().data
                        if istnieje:
                            nowa_ilosc = istnieje[0]['liczba'] + n_ilosc
                            supabase.table("produkty").update({"liczba": nowa_ilosc, "cena": n_cena}).eq("id", istnieje[0]['id']).execute()
                            st.info(f"Zaktualizowano: {n_nazwa}")
                        else:
                            supabase.table("produkty").insert({
                                "nazwa": n_nazwa, "kategoria_id": kat_map[n_kat], "cena": n_cena, "liczba": n_ilosc
                            }).execute()
                            st.success("Dodano nowy produkt!")
                        refresh_data(); st.rerun()

    # Tabela z produktami
    if produkty_raw:
        df_p = pd.DataFrame([
            {
                "Produkt": p['nazwa'],
                "Kategoria": p['kategorie']['nazwa'] if p['kategorie'] else "-",
                "Cena": f"{p['cena']:.2f} zł",
                "Ilość": p['liczba'],
                "Wartość": f"{p['liczba'] * p['cena']:.2f} zł",
                "Status": "🔴 MAŁO" if p['liczba'] < 10 else "🟢 OK"
            } for p in produkty_raw if szukaj.lower() in p['nazwa'].lower()
        ])
        
        st.dataframe(df_p, use_container_width=True, hide_index=True)

# --- TAB 2: WYDANIE ---
with tab2:
    st.subheader("Nowa operacja wydania")
    if produkty_raw:
        p_dict = {p['nazwa']: p for p in produkty_raw}
        with st.form("wydanie_form"):
            wybrany = st.selectbox("Wybierz towar", list(p_dict.keys()))
            ile_w = st.number_input("Ilość wydawana", min_value=1)
            
            if st.form_submit_button("Potwierdź Wydanie", use_container_width=True):
                p_obj = p_dict[wybrany]
                if p_obj['liczba'] >= ile_w:
                    # 1. Historia
                    supabase.table("zamowienia").insert({
                        "produkt_id": p_obj['id'], "ilosc": ile_w, "cena_calkowita": p_obj['cena'] * ile_w
                    }).execute()
                    # 2. Update stanu
                    supabase.table("produkty").update({"liczba": p_obj['liczba'] - ile_w}).eq("id", p_obj['id']).execute()
                    st.success("Wydano towar!")
                    refresh_data(); st.rerun()
                else:
                    st.error(f"Brak towaru! Na stanie tylko: {p_obj['liczba']}")

# --- TAB 3: KATEGORIE ---
with tab3:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Nowa kategoria")
        k_nowa = st.text_input("Nazwa")
        if st.button("Dodaj"):
            if k_nowa:
                supabase.table("kategorie").insert({"nazwa": k_nowa}).execute()
                refresh_data(); st.rerun()
    
    with c2:
        st.subheader("Lista kategorii")
        all_k = get_categories()
        for k in all_k:
            k_col1, k_col2 = st.columns([4, 1])
            k_col1.write(f"📁 {k['nazwa']}")
            if k_col2.button("Usuń", key=f"del_{k['id']}"):
                try:
                    supabase.table("kategorie").delete().eq("id", k['id']).execute()
                    refresh_data(); st.rerun()
                except:
                    st.error("Kategoria jest używana!")

# --- TAB 4: HISTORIA ---
with tab4:
    st.subheader("Historia wydań")
    zam = get_orders()
    if zam:
        df_z = pd.DataFrame([{
            "Data": z['created_at'][:16].replace("T", " "),
            "Produkt": z['produkty']['nazwa'] if z['produkty'] else "Usunięty",
            "Ilość": z['ilosc'],
            "Suma": f"{z['cena_calkowita']:.2f} zł"
        } for z in zam])
        st.dataframe(df_z, use_container_width=True, hide_index=True)
