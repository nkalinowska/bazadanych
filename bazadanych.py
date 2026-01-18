import streamlit as st
from supabase import create_client, Client

# 1. Inicjalizacja połączenia z Supabase
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

st.title("📦 Zarządzanie Magazynem")

# --- FUNKCJE POMOCNICZE ---
def get_categories():
    response = supabase.table("Kategorie").select("*").execute()
    return response.data

def get_products():
    # Wykonujemy JOIN, aby pobrać nazwę kategorii zamiast samego ID
    response = supabase.table("produkty").select("*, Kategorie(nazwa)").execute()
    return response.data

# --- ZAKŁADKI ---
tab1, tab2 = st.tabs(["Produkty", "Kategorie"])

# --- SEKCJA: KATEGORIE ---
with tab2:
    st.header("Zarządzaj Kategoriami")
    
    # Dodawanie kategorii
    with st.expander("Dodaj nową kategorię"):
        with st.form("add_category"):
            kat_nazwa = st.text_input("Nazwa kategorii")
            kat_opis = st.text_area("Opis")
            if st.form_submit_button("Zapisz kategorię"):
                supabase.table("Kategorie").insert({"nazwa": kat_nazwa, "opis": kat_opis}).execute()
                st.success("Dodano kategorię!")
                st.rerun()

    # Wyświetlanie i usuwanie
    kategorie = get_categories()
    for k in kategorie:
        col1, col2 = st.columns([4, 1])
        col1.write(f"**{k['nazwa']}** (ID: {k['id']})")
        if col2.button("Usuń", key=f"del_kat_{k['id']}"):
            supabase.table("Kategorie").delete().eq("id", k['id']).execute()
            st.rerun()

# --- SEKCJA: PRODUKTY ---
with tab1:
    st.header("Zarządzaj Produktami")

    # Dodawanie produktu
    with st.expander("Dodaj nowy produkt"):
        kategorie_opcje = {k['nazwa']: k['id'] for k in get_categories()}
        
        with st.form("add_product"):
            p_nazwa = st.text_input("Nazwa produktu")
            p_liczba = st.number_input("Liczba", min_value=0, step=1)
            p_cena = st.number_input("Cena", min_value=0.0, format="%.2f")
            p_kat_id = st.selectbox("Kategoria", options=list(kategorie_opcje.keys()))
            
            if st.form_submit_button("Dodaj produkt"):
                new_prod = {
                    "nazwa": p_nazwa,
                    "liczba": p_liczba,
                    "cena": p_cena,
                    "kategoria_id": kategorie_opcje[p_kat_id]
                }
                supabase.table("produkty").insert(new_prod).execute()
                st.success("Produkt dodany!")
                st.rerun()

    # Lista produktów
    produkty = get_products()
    if produkty:
        for p in produkty:
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.write(f"**{p['nazwa']}**")
            col2.write(f"{p['cena']} zł | Sztuk: {p['liczba']}")
            if col3.button("Usuń", key=f"del_prod_{p['id']}"):
                supabase.table("produkty").delete().eq("id", p['id']).execute()
                st.rerun()
    else:
        st.info("Brak produktów w bazie.")
