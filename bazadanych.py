import streamlit as st
from supabase import create_client
from postgrest.exceptions import APIError

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Magazyn Pro", page_icon="📦", layout="wide")

# --- POŁĄCZENIE Z SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"Problem z połączeniem: {e}")
        return None

supabase = init_connection()

# --- LOGIKA DANYCH ---
@st.cache_data(ttl=60)
def get_categories():
    return supabase.table("kategorie").select("*").order("nazwa").execute().data

@st.cache_data(ttl=60)
def get_products():
    return supabase.table("produkty").select("*, kategorie(nazwa)").order("nazwa").execute().data

@st.cache_data(ttl=60)
def get_orders():
    try:
        # Pobieramy zamówienia wraz z nazwą produktu (relacja)
        return supabase.table("zamowienia").select("*, produkty(nazwa)").order("created_at", desc=True).execute().data
    except:
        return []

def refresh_data():
    st.cache_data.clear()

# --- INTERFEJS ---
st.title("📦 Panel Zarządzania Magazynem")

# ROZDZIELONE ZAKŁADKI
tab1, tab2, tab3, tab4 = st.tabs([
    "🛒 Stan Magazynowy", 
    "➕ Nowe Zamówienie", 
    "📂 Kategorie", 
    "📜 Historia Zamówień"
])

# --- 1. MAGAZYN ---
with tab1:
    st.header("Aktualne Produkty")
    produkty = get_products()
    
    if produkty:
        # Alerty o niskim stanie
        low_stock = [p for p in produkty if p['liczba'] < 10]
        if low_stock:
            st.error(f"⚠️ Należy uzupełnić: {', '.join([p['nazwa'] for p in low_stock])}")

        # Tabela produktów
        df_display = []
        for p in produkty:
            df_display.append({
                "Produkt": p['nazwa'],
                "Kategoria": p['kategorie']['nazwa'] if p['kategorie'] else "Brak",
                "Cena (zł)": f"{p['cena']:.2f}",
                "Ilość": p['liczba'],
                "Status": "🔴 NISKI" if p['liczba'] < 10 else "🟢 OK"
            })
        st.table(df_display)
    else:
        st.info("Magazyn jest pusty.")

# --- 2. NOWE ZAMÓWIENIE ---
with tab2:
    st.header("Realizacja Wydania/Zamówienia")
    produkty = get_products()
    
    if produkty:
        prod_dict = {p['nazwa']: p for p in produkty}
        with st.form("form_order"):
            wybor = st.selectbox("Wybierz produkt", options=list(prod_dict.keys()))
            ilosc = st.number_input("Ilość do wydania", min_value=1, step=1)
            
            if st.form_submit_button("Zatwierdź zamówienie"):
                p = prod_dict[wybor]
                if p['liczba'] >= ilosc:
                    # 1. Dodaj do historii zamówień
                    supabase.table("zamowienia").insert({
                        "produkt_id": p['id'],
                        "ilosc": ilosc,
                        "cena_calkowita": p['cena'] * ilosc
                    }).execute()
                    
                    # 2. Aktualizuj stan magazynowy
                    supabase.table("produkty").update({"liczba": p['liczba'] - ilosc}).eq("id", p['id']).execute()
                    
                    st.success(f"Wydano {ilosc} szt. produktu {wybor}")
                    refresh_data()
                    st.rerun()
                else:
                    st.error("Błąd: Niewystarczająca ilość w magazynie!")
    else:
        st.warning("Brak produktów, dla których można złożyć zamówienie.")

# --- 3. KATEGORIE ---
with tab3:
    st.header("Zarządzanie Kategoriami")
    
    # Formularz dodawania
    with st.expander("Dodaj nową kategorię"):
        new_cat = st.text_input("Nazwa kategorii")
        if st.button("Zapisz kategorię"):
            if new_cat:
                supabase.table("kategorie").insert({"nazwa": new_cat}).execute()
                st.success("Dodano!")
                refresh_data()
                st.rerun()

    # Lista kategorii
    kategorie = get_categories()
    if kategorie:
        for k in kategorie:
            col1, col2 = st.columns([4, 1])
            col1.write(f"📁 **{k['nazwa']}**")
            if col2.button("Usuń", key=f"cat_{k['id']}"):
                try:
                    supabase.table("kategorie").delete().eq("id", k['id']).execute()
                    refresh_data()
                    st.rerun()
                except:
                    st.error("Nie można usunąć kategorii, w której są produkty.")

# --- 4. HISTORIA ---
with tab4:
    st.header("Historia Transakcji")
    zamowienia = get_orders()
    
    if zamowienia:
        # Przygotowanie czytelnej tabeli historii
        historia_wyswietl = []
        for z in zamowienia:
            nazwa_p = z['produkty']['nazwa'] if z['produkty'] else "Produkt usunięty"
            historia_wyswietl.append({
                "Data": z['created_at'][:16].replace("T", " "),
                "Produkt": nazwa_p,
                "Ilość": z['ilosc'],
                "Wartość (zł)": f"{z['cena_calkowita']:.2f}"
            })
        st.dataframe(historia_wyswietl, use_container_width=True)
        
        if st.button("Wyczyść historię (tylko widok)", help="To nie usuwa danych z bazy"):
            refresh_data()
            st.rerun()
    else:
        st.info("Brak zarejestrowanych zamówień.")
