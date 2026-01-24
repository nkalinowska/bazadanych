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
        return supabase.table("zamowienia").select("*, produkty(nazwa)").order("created_at", desc=True).execute().data
    except:
        return []

def refresh_data():
    st.cache_data.clear()

# --- INTERFEJS ---
st.title("📦 System Zarządzania Magazynem")

tab1, tab2, tab3, tab4 = st.tabs([
    "🛒 Stan Magazynowy", 
    "➕ Nowe Zamówienie", 
    "📂 Kategorie", 
    "📜 Historia Zamówień"
])

# --- 1. MAGAZYN (Z DODAWANIEM PRODUKTÓW) ---
with tab1:
    st.header("Produkty w magazynie")
    
    # Formularz dodawania produktu
    with st.expander("➕ Dodaj nowy produkt do bazy"):
        kat_lista = get_categories()
        if not kat_lista:
            st.warning("Najpierw dodaj kategorię w zakładce 'Kategorie'!")
        else:
            kat_opcje = {k['nazwa']: k['id'] for k in kat_lista}
            with st.form("form_add_product", clear_on_submit=True):
                col1, col2 = st.columns(2)
                p_nazwa = col1.text_input("Nazwa produktu")
                p_kat = col2.selectbox("Kategoria", options=list(kat_opcje.keys()))
                p_cena = col1.number_input("Cena (zł)", min_value=0.0, format="%.2f")
                p_ilosc = col2.number_input("Ilość początkowa", min_value=0, step=1)
                
                if st.form_submit_button("Dodaj produkt"):
                    if p_nazwa:
                        supabase.table("produkty").insert({
                            "nazwa": p_nazwa,
                            "kategoria_id": kat_opcje[p_kat],
                            "cena": p_cena,
                            "liczba": p_ilosc
                        }).execute()
                        st.success(f"Dodano produkt: {p_nazwa}")
                        refresh_data()
                        st.rerun()
                    else:
                        st.error("Podaj nazwę produktu!")

    # Wyświetlanie tabeli
    produkty = get_products()
    if produkty:
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
        st.info("Brak produktów w bazie.")

# --- 2. NOWE ZAMÓWIENIE ---
with tab2:
    st.header("Realizacja Wydania")
    produkty = get_products()
    
    if produkty:
        prod_dict = {p['nazwa']: p for p in produkty}
        with st.form("form_order"):
            wybor = st.selectbox("Wybierz produkt", options=list(prod_dict.keys()))
            ilosc = st.number_input("Ilość", min_value=1, step=1)
            
            if st.form_submit_button("Zatwierdź wydanie"):
                p = prod_dict[wybor]
                if p['liczba'] >= ilosc:
                    supabase.table("zamowienia").insert({
                        "produkt_id": p['id'],
                        "ilosc": ilosc,
                        "cena_calkowita": p['cena'] * ilosc
                    }).execute()
                    
                    supabase.table("produkty").update({"liczba": p['liczba'] - ilosc}).eq("id", p['id']).execute()
                    
                    st.success("Zamówienie zrealizowane!")
                    refresh_data()
                    st.rerun()
                else:
                    st.error("Brak towaru!")
    else:
        st.warning("Dodaj produkty, aby móc składać zamówienia.")

# --- 3. KATEGORIE (DODAWANIE I LISTA) ---
with tab3:
    st.header("Zarządzanie Kategoriami")
    
    with st.form("form_add_category", clear_on_submit=True):
        new_cat = st.text_input("Nazwa nowej kategorii")
        if st.form_submit_button("Dodaj kategorię"):
            if new_cat:
                supabase.table("kategorie").insert({"nazwa": new_cat}).execute()
                st.success("Kategoria dodana!")
                refresh_data()
                st.rerun()
            else:
                st.warning("Wpisz nazwę!")

    st.subheader("Istniejące kategorie")
    kategorie = get_categories()
    if kategorie:
        for k in kategorie:
            c1, c2 = st.columns([5, 1])
            c1.write(f"📁 {k['nazwa']}")
            if c2.button("Usuń", key=f"del_cat_{k['id']}"):
                try:
                    supabase.table("kategorie").delete().eq("id", k['id']).execute()
                    refresh_data()
                    st.rerun()
                except:
                    st.error("Nie można usunąć kategorii, która ma przypisane produkty!")

# --- 4. HISTORIA ---
with tab4:
    st.header("Historia Transakcji")
    zamowienia = get_orders()
    if zamowienia:
        historia_wyswietl = []
        for z in zamowienia:
            nazwa_p = z['produkty']['nazwa'] if z['produkty'] else "Produkt usunięty"
            historia_wyswietl.append({
                "Data": z['created_at'][:16].replace("T", " "),
                "Produkt": nazwa_p,
                "Ilość": z['ilosc'],
                "Razem (zł)": f"{z['cena_calkowita']:.2f}"
            })
        st.dataframe(historia_wyswietl, use_container_width=True)
    else:
        st.info("Brak historii.")
