import streamlit as st
from supabase import create_client

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Magazyn Inteligentny", page_icon="📦", layout="wide")

# --- POŁĄCZENIE ---
@st.cache_resource
def init_connection():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"Problem z połączeniem: {e}")
        return None

supabase = init_connection()

# --- DANE ---
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

# --- UI ---
st.title("📦 System Zarządzania Magazynem")

tab1, tab2, tab3, tab4 = st.tabs([
    "🛒 Stan Magazynowy", 
    "➕ Nowe Zamówienie", 
    "📂 Kategorie", 
    "📜 Historia"
])

# --- 1. MAGAZYN (Z INTELIGENTNYM DODAWANIEM) ---
with tab1:
    st.header("Zarządzaj Produktami")
    
    with st.expander("➕ Dodaj lub uzupełnij produkt"):
        kat_lista = get_categories()
        if not kat_lista:
            st.warning("Najpierw dodaj kategorię!")
        else:
            kat_opcje = {k['nazwa']: k['id'] for k in kat_lista}
            with st.form("form_add_product", clear_on_submit=True):
                p_nazwa = st.text_input("Nazwa produktu (np. Chleb)").strip()
                p_kat = st.selectbox("Kategoria", options=list(kat_opcje.keys()))
                p_cena = st.number_input("Cena za szt. (zł)", min_value=0.0, format="%.2f")
                p_dodaj_ilosc = st.number_input("Ilość do dodania", min_value=1, step=1)
                
                if st.form_submit_button("Zatwierdź"):
                    if p_nazwa:
                        # Sprawdzamy czy produkt już istnieje (ignorując wielkość liter)
                        istniejacy = supabase.table("produkty").select("*").ilike("nazwa", p_nazwa).execute().data
                        
                        if istniejacy:
                            # AKTUALIZACJA: Produkt istnieje, dodajemy ilość
                            p_id = istniejacy[0]['id']
                            stara_ilosc = istniejacy[0]['liczba']
                            nowa_ilosc = stara_ilosc + p_dodaj_ilosc
                            
                            supabase.table("produkty").update({
                                "liczba": nowa_ilosc,
                                "cena": p_cena # Aktualizujemy też cenę na wypadek zmiany
                            }).eq("id", p_id).execute()
                            
                            st.info(f"Zaktualizowano stan produktu '{p_nazwa}'. Obecnie: {nowa_ilosc} szt.")
                        else:
                            # INSERT: Nowy produkt
                            supabase.table("produkty").insert({
                                "nazwa": p_nazwa,
                                "kategoria_id": kat_opcje[p_kat],
                                "cena": p_cena,
                                "liczba": p_dodaj_ilosc
                            }).execute()
                            st.success(f"Dodano nowy produkt: {p_nazwa}")
                        
                        refresh_data()
                        st.rerun()
                    else:
                        st.error("Podaj nazwę!")

    # Tabela wyświetlania
    produkty = get_products()
    if produkty:
        df_display = [{
            "Produkt": p['nazwa'],
            "Kategoria": p['kategorie']['nazwa'] if p['kategorie'] else "Brak",
            "Cena": f"{p['cena']:.2f} zł",
            "Ilość": p['liczba'],
            "Status": "🔴 MAŁO" if p['liczba'] < 10 else "🟢 OK"
        } for p in produkty]
        st.table(df_display)

# --- 2. NOWE ZAMÓWIENIE (BEZ ZMIAN) ---
with tab2:
    st.header("Realizacja Wydania")
    produkty = get_products()
    if produkty:
        prod_dict = {p['nazwa']: p for p in produkty}
        with st.form("form_order"):
            wybor = st.selectbox("Produkt", options=list(prod_dict.keys()))
            ilosc_w = st.number_input("Ilość wydawana", min_value=1, step=1)
            if st.form_submit_button("Zatwierdź"):
                p = prod_dict[wybor]
                if p['liczba'] >= ilosc_w:
                    supabase.table("zamowienia").insert({
                        "produkt_id": p['id'], "ilosc": ilosc_w, "cena_calkowita": p['cena'] * ilosc_w
                    }).execute()
                    supabase.table("produkty").update({"liczba": p['liczba'] - ilosc_w}).eq("id", p['id']).execute()
                    st.success("Wydano z magazynu!")
                    refresh_data(); st.rerun()
                else:
                    st.error("Brak na stanie!")

# --- 3. KATEGORIE ---
with tab3:
    st.header("Kategorie")
    new_cat = st.text_input("Nowa kategoria")
    if st.button("Dodaj"):
        if new_cat:
            supabase.table("kategorie").insert({"nazwa": new_cat}).execute()
            refresh_data(); st.rerun()
    
    kats = get_categories()
    for k in kats:
        c1, c2 = st.columns([5,1])
        c1.write(k['nazwa'])
        if c2.button("Usuń", key=f"k_{k['id']}"):
            try:
                supabase.table("kategorie").delete().eq("id", k['id']).execute()
                refresh_data(); st.rerun()
            except: st.error("Kategoria ma przypisane produkty!")

# --- 4. HISTORIA ---
with tab4:
    st.header("Historia")
    zam = get_orders()
    if zam:
        st.dataframe([{
            "Data": z['created_at'][:16],
            "Produkt": z['produkty']['nazwa'] if z['produkty'] else "Usunięty",
            "Ilość": z['ilosc'],
            "Suma": f"{z['cena_calkowita']:.2f} zł"
        } for z in zam], use_container_width=True)
