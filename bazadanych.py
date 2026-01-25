import streamlit as st
from supabase import create_client
import pandas as pd

# --- KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="SmartStock | Magazyn", 
    page_icon="📦", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Stylizacja CSS dla lepszego wyglądu
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_stdio=True)

# --- POŁĄCZENIE ---
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"Problem z połączeniem z bazą danych: {e}")
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
    return supabase.table("zamowienia").select("*, produkty(nazwa)").order("created_at", desc=True).execute().data

def refresh_data():
    st.cache_data.clear()

# --- UI: SIDEBAR (STATYSTYKI) ---
with st.sidebar:
    st.title("📊 Podsumowanie")
    produkty_raw = get_products()
    
    if produkty_raw:
        total_items = sum(p['liczba'] for p in produkty_raw)
        # Obliczanie całkowitej wartości magazynu
        total_value = sum(p['liczba'] * p['cena'] for p in produkty_raw)
        low_stock = sum(1 for p in produkty_raw if p['liczba'] < 10)

        st.metric("Wartość magazynu", f"{total_value:,.2f} zł")
        st.metric("Liczba produktów", f"{total_items} szt.")
        st.metric("Niski stan (alert)", low_stock, delta=-low_stock, delta_color="inverse")
    
    st.divider()
    if st.button("🔄 Odśwież dane", use_container_width=True):
        refresh_data()
        st.rerun()

# --- UI: GŁÓWNA TREŚĆ ---
st.title("📦 System Zarządzania Magazynem")

tab1, tab2, tab3, tab4 = st.tabs([
    "🛒 Inwentaryzacja", 
    "➕ Wydanie Towaru", 
    "📂 Kategorie", 
    "📜 Historia Operacji"
])

# --- 1. MAGAZYN ---
with tab1:
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        search_query = st.text_input("🔍 Szukaj produktu...", placeholder="Wpisz nazwę produktu")
    
    with col_b:
        with st.expander("➕ Dodaj / Aktualizuj produkt"):
            kat_lista = get_categories()
            if not kat_lista:
                st.warning("Dodaj najpierw kategorię!")
            else:
                kat_opcje = {k['nazwa']: k['id'] for k in kat_lista}
                with st.form("form_add_product", clear_on_submit=True):
                    p_nazwa = st.text_input("Nazwa produktu")
                    p_kat = st.selectbox("Kategoria", options=list(kat_opcje.keys()))
                    p_cena = st.number_input("Cena (zł)", min_value=0.0, step=0.01)
                    p_ilosc = st.number_input("Ilość", min_value=1)
                    
                    if st.form_submit_button("Zapisz w bazie", use_container_width=True):
                        if p_nazwa:
                            istniejacy = supabase.table("produkty").select("*").ilike("nazwa", p_nazwa).execute().data
                            if istniejacy:
                                new_qty = istniejacy[0]['liczba'] + p_ilosc
                                supabase.table("produkty").update({"liczba": new_qty, "cena": p_cena}).eq("id", istniejacy[0]['id']).execute()
                                st.info(f"Zaktualizowano stan: {p_nazwa}")
                            else:
                                supabase.table("produkty").insert({
                                    "nazwa": p_nazwa, "kategoria_id": kat_opcje[p_kat], "cena": p_cena, "liczba": p_ilosc
                                }).execute()
                                st.success("Dodano nowy produkt")
                            refresh_data(); st.rerun()

    # Wyświetlanie tabeli
    if produkty_raw:
        data_filtered = [
            {
                "ID": p['id'],
                "Produkt": p['nazwa'],
                "Kategoria": p['kategorie']['nazwa'] if p['kategorie'] else "Brak",
                "Cena jedn.": f"{p['cena']:.2f} zł",
                "Ilość": p['liczba'],
                "Wartość": f"{p['liczba'] * p['cena']:.2f} zł",
                "Status": "🔴 MAŁO" if p['liczba'] < 10 else "🟢 OK"
            } for p in produkty_raw if search_query.lower() in p['nazwa'].lower()
        ]
        
        if data_filtered:
            st.dataframe(
                data_filtered, 
                use_container_width=True, 
                hide_index=True,
                column_config={"Status": st.column_config.TextColumn("Alert")}
            )
        else:
            st.info("Nie znaleziono produktów o tej nazwie.")

# --- 2. WYDANIE TOWARU ---
with tab2:
    st.subheader("Nowe wydanie (Sprzedaż/Rozchód)")
    if produkty_raw:
        prod_dict = {p['nazwa']: p for p in produkty_raw}
        col1, col2 = st.columns(2)
        
        with st.form("form_order"):
            wybor = st.selectbox("Wybierz produkt", options=list(prod_dict.keys()))
            ilosc_w = st.number_input("Ilość do wydania", min_value=1, step=1)
            
            if st.form_submit_button("Potwierdź wydanie", use_container_width=True):
                p = prod_dict[wybor]
                if p['liczba'] >= ilosc_w:
                    # Dodanie do historii
                    supabase.table("zamowienia").insert({
                        "produkt_id": p['id'], 
                        "ilosc": ilosc_w, 
                        "cena_calkowita": p['cena'] * ilosc_w
                    }).execute()
                    # Zdjęcie ze stanu
                    supabase.table("produkty").update({"liczba": p['liczba'] - ilosc_w}).eq("id", p['id']).execute()
                    st.success(f"Wydano {ilosc_w} szt. produktu {wybor}")
                    refresh_data(); st.rerun()
                else:
                    st.error(f"Niewystarczająca ilość! (Dostępne: {p['liczba']})")

# --- 3. KATEGORIE ---
with tab3:
    st.subheader("Zarządzanie kategoriami")
    c1, c2 = st.columns([2, 1])
    with c1:
        new_cat = st.text_input("Nazwa nowej kategorii")
        if st.button("Dodaj kategorię", use_container_width=True):
            if new_cat:
                supabase.table("kategorie").insert({"nazwa": new_cat}).execute()
                refresh_data(); st.rerun()
    
    st.divider()
    kats = get_categories()
    for k in kats:
        cols = st.columns([4, 1])
        cols[0].write(f"📁 {k['nazwa']}")
        if cols[1].button("Usuń", key=f"del_{k['id']}", type="secondary"):
            try:
                supabase.table("kategorie").delete().eq("id", k['id']).execute()
                refresh_data(); st.rerun()
            except:
                st.error("Nie można usunąć – kategoria zawiera produkty.")

# --- 4. HISTORIA ---
with tab4:
    st.subheader("Ostatnie operacje")
    zamowienia_raw = get_orders()
    if zamowienia_raw:
        df_hist = pd.DataFrame([{
            "Data": z['created_at'][:16].replace("T", " "),
            "Produkt": z['produkty']['nazwa'] if z['produkty'] else "⚠️ Usunięty",
            "Ilość": z['ilosc'],
            "Wartość operacji": f"{z['cena_calkowita']:.2f} zł"
        } for z in zamowienia_raw])
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
