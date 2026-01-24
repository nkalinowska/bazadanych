import streamlit as st
from supabase import create_client, Client

# --- KONFIGURACJA ---
st.set_page_config(page_title="Magazyn Pro", page_icon="📦", layout="wide")

@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_connection()

# --- DANE ---
@st.cache_data(ttl=600)
def get_categories():
    return supabase.table("kategorie").select("*").order("nazwa").execute().data

@st.cache_data(ttl=600)
def get_products():
    return supabase.table("produkty").select("*, kategorie(nazwa)").order("nazwa").execute().data

@st.cache_data(ttl=600)
def get_orders():
    # Pobieramy zamówienia wraz z nazwą produktu
    return supabase.table("zamowienia").select("*, produkty(nazwa)").order("created_at", desc=True).execute().data

def refresh_data():
    st.cache_data.clear()

# --- UI ---
st.title("📦 System Magazynowo-Zamówieniowy")

tab1, tab2, tab3 = st.tabs(["🛒 Magazyn", "📝 Nowe Zamówienie", "📂 Kategorie & Historia"])

# --- TAB 1: MAGAZYN & ALERTY ---
with tab1:
    produkty = get_products()
    low_stock = [p for p in produkty if p['liczba'] < 10]
    
    if low_stock:
        st.error(f"⚠️ Niskie stany: {', '.join([p['nazwa'] for p in low_stock])}")

    st.subheader("Aktualne stany")
    if produkty:
        # Wyświetlamy jako ładną tabelę (Dataframe)
        df_data = [{
            "Produkt": p['nazwa'], 
            "Ilość": p['liczba'], 
            "Cena": f"{p['cena']} zł", 
            "Kategoria": p['kategorie']['nazwa'] if p['kategorie'] else "Brak"
        } for p in produkty]
        st.dataframe(df_data, use_container_width=True)
    else:
        st.info("Brak produktów.")

# --- TAB 2: NOWE ZAMÓWIENIE (LOGIKA) ---
with tab2:
    st.header("Złóż zamówienie")
    produkty = get_products()
    prod_options = {p['nazwa']: p for p in produkty}

    with st.form("order_form"):
        wybrany_prod_nazwa = st.selectbox("Wybierz produkt", options=list(prod_options.keys()))
        ilosc_zam = st.number_input("Ilość", min_value=1, step=1)
        submit = st.form_submit_button("Zatwierdź zamówienie")

        if submit:
            prod = prod_options[wybrany_prod_nazwa]
            
            if prod['liczba'] >= ilosc_zam:
                nowa_ilosc = prod['liczba'] - ilosc_zam
                cena_razem = prod['cena'] * ilosc_zam
                
                # 1. Zapisz zamówienie
                supabase.table("zamowienia").insert({
                    "produkt_id": prod['id'],
                    "ilosc": ilosc_zam,
                    "cena_calkowita": cena_razem
                }).execute()
                
                # 2. Zaktualizuj stan w magazynie
                supabase.table("produkty").update({"liczba": nowa_ilosc}).eq("id", prod['id']).execute()
                
                st.success(f"Zamówienie złożone! Łączny koszt: {cena_razem:.2f} zł")
                refresh_data()
                st.rerun()
            else:
                st.error(f"Nie ma tyle na stanie! Dostępne: {prod['liczba']}")

# --- TAB 3: HISTORIA I KATEGORIE ---
with tab3:
    col_hist, col_kat = st.columns(2)
    
    with col_hist:
        st.subheader("Recent Orders")
        zamowienia = get_orders()
        if zamowienia:
            for z in zamowienia:
                st.text(f"🕒 {z['created_at'][:16]} | {z['produkty']['nazwa']} | x{z['ilosc']} | {z['cena_calkowita']} zł")
        else:
            st.write("Brak zamówień.")

    with col_kat:
        st.subheader("Kategorie")
        kat_nazwa = st.text_input("Nowa kategoria")
        if st.button("Dodaj kategorię"):
            if kat_nazwa:
                supabase.table("kategorie").insert({"nazwa": kat_nazwa}).execute()
                refresh_data()
                st.rerun()
