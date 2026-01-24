import streamlit as st
from supabase import create_client, Client

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Magazyn Pro", page_icon="📦", layout="centered")

# --- 1. INICJALIZACJA POŁĄCZENIA ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Błąd połączenia z Supabase: {e}")
        return None

supabase = init_connection()

# --- 2. LOGIKA POBIERANIA DANYCH (Z CACHE) ---
@st.cache_data(ttl=600)
def get_categories():
    response = supabase.table("kategorie").select("*").order("nazwa").execute()
    return response.data

@st.cache_data(ttl=600)
def get_products():
    # JOIN z tabelą kategorie, aby mieć nazwy kategorii
    response = supabase.table("produkty").select("*, kategorie(nazwa)").order("nazwa").execute()
    return response.data

def refresh_data():
    """Czyści cache po dodaniu lub usunięciu danych"""
    st.cache_data.clear()

# --- 3. SYSTEM ALERTÓW ---
def display_alerts(produkty, limit=10):
    low_stock = [p for p in produkty if p['liczba'] < limit]
    if low_stock:
        with st.container():
            st.error(f"🚨 **ALERTY MAGAZYNOWE (Poniżej {limit} sztuk):**")
            cols = st.columns(len(low_stock) if len(low_stock) < 3 else 3)
            for idx, p in enumerate(low_stock):
                with cols[idx % 3]:
                    st.warning(f"**{p['nazwa']}**\n\nZostało: {p['liczba']} szt.")
        st.divider()

# --- 4. INTERFEJS UŻYTKOWNIKA ---
st.title("📦 Zarządzanie Magazynem")

# Zakładki
tab1, tab2 = st.tabs(["🛒 Produkty", "📂 Kategorie"])

# --- SEKCJA: PRODUKTY ---
with tab1:
    produkty = get_products()
    
    # Wyświetl alerty jeśli są produkty
    if produkty:
        display_alerts(produkty, limit=10)

    st.header("Lista Produktów")
    
    # Dodawanie produktu
    with st.expander("➕ Dodaj nowy produkt"):
        kat_dane = get_categories()
        kat_opcje = {k['nazwa']: k['id'] for k in kat_dane}
        
        if not kat_opcje:
            st.warning("Najpierw dodaj przynajmniej jedną kategorię w zakładce 'Kategorie'!")
        else:
            with st.form("add_product", clear_on_submit=True):
                p_nazwa = st.text_input("Nazwa produktu")
                col_a, col_b = st.columns(2)
                p_liczba = col_a.number_input("Ilość", min_value=0, step=1)
                p_cena = col_b.number_input("Cena (zł)", min_value=0.0, format="%.2f")
                p_kat_id = st.selectbox("Kategoria", options=list(kat_opcje.keys()))
                
                if st.form_submit_button("Dodaj produkt"):
                    if p_nazwa:
                        new_prod = {
                            "nazwa": p_nazwa,
                            "liczba": p_liczba,
                            "cena": p_cena,
                            "kategoria_id": kat_opcje[p_kat_id]
                        }
                        supabase.table("produkty").insert(new_prod).execute()
                        st.success(f"Dodano: {p_nazwa}")
                        refresh_data()
                        st.rerun()
                    else:
                        st.error("Nazwa produktu nie może być pusta!")

    # Wyświetlanie listy produktów
    if produkty:
        for p in produkty:
            is_low = p['liczba'] < 10
            with st.container():
                c1, c2, c3 = st.columns([3, 2, 1])
                
                # Nazwa i kategoria
                kat_nazwa = p['kategorie']['nazwa'] if p.get('kategorie') else "Brak"
                c1.write(f"**{p['nazwa']}** \n:grey[{kat_nazwa}]")
                
                # Stan i cena (na czerwono jeśli mało)
                if is_low:
                    c2.write(f"{p['cena']:.2f} zł | :red[**Sztuk: {p['liczba']}**] ⚠️")
                else:
                    c2.write(f"{p['cena']:.2f} zł | Sztuk: {p['liczba']}")
                
                # Usuwanie
                if c3.button("Usuń", key=f"del_p_{p['id']}"):
                    supabase.table("produkty").delete().eq("id", p['id']).execute()
                    refresh_data()
                    st.rerun()
    else:
        st.info("Baza produktów jest pusta.")

# --- SEKCJA: KATEGORIE ---
with tab2:
    st.header("Zarządzaj Kategoriami")
    
    with st.expander("➕ Dodaj nową kategorię"):
        with st.form("add_category", clear_on_submit=True):
            k_nazwa = st.text_input("Nazwa kategorii")
            k_opis = st.text_area("Opis")
            if st.form_submit_button("Zapisz"):
                if k_nazwa:
                    supabase.table("kategorie").insert({"nazwa": k_nazwa, "opis": k_opis}).execute()
                    refresh_data()
                    st.rerun()
                else:
                    st.warning("Podaj nazwę kategorii!")

    kategorie = get_categories()
    if kategorie:
        for k in kategorie:
            col1, col2 = st.columns([4, 1])
            col1.write(f"📂 **{k['nazwa']}**")
            if col2.button("Usuń", key=f"del_k_{k['id']}"):
                try:
                    supabase.table("kategorie").delete().eq("id", k['id']).execute()
                    refresh_data()
                    st.rerun()
                except:
                    st.error("Nie można usunąć kategorii, która zawiera produkty!")
