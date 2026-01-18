import streamlit as st
import sqlite3
import pandas as pd

# Konfiguracja bazy danych
def init_db():
    conn = sqlite3.connect('magazyn.db')
    c = conn.cursor()
    # Tabela Kategorie
    c.execute('''CREATE TABLE IF NOT EXISTS kategorie (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nazwa TEXT NOT NULL,
                    opis TEXT)''')
    # Tabela Produkty
    c.execute('''CREATE TABLE IF NOT EXISTS produkty (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nazwa TEXT NOT NULL,
                    liczba INTEGER,
                    cena REAL,
                    kategoria_id INTEGER,
                    FOREIGN KEY (kategoria_id) REFERENCES kategorie(id))''')
    conn.commit()
    return conn

conn = init_db()

st.title("📦 System Zarządzania Produktami")

menu = ["Produkty", "Kategorie"]
choice = st.sidebar.selectbox("Nawigacja", menu)

# --- SEKCJA KATEGORIE ---
if choice == "Kategorie":
    st.header("Zarządzanie Kategoriami")
    
    with st.expander("Dodaj nową kategorię"):
        nazwa_kat = st.text_input("Nazwa kategorii")
        opis_kat = st.text_area("Opis")
        if st.button("Dodaj Kategorię"):
            conn.execute("INSERT INTO kategorie (nazwa, opis) VALUES (?, ?)", (nazwa_kat, opis_kat))
            conn.commit()
            st.success(f"Dodano kategorię: {nazwa_kat}")

    st.subheader("Lista Kategorii")
    df_kat = pd.read_sql_query("SELECT * FROM kategorie", conn)
    st.dataframe(df_kat, use_container_width=True)

    with st.expander("Usuń kategorię"):
        kat_to_del = st.selectbox("Wybierz kategorię do usunięcia", df_kat['nazwa'].tolist() if not df_kat.empty else [])
        if st.button("Usuń"):
            conn.execute("DELETE FROM kategorie WHERE nazwa = ?", (kat_to_del,))
            conn.commit()
            st.warning("Kategoria usunięta (pamiętaj o powiązanych produktach!)")
            st.rerun()

# --- SEKCJA PRODUKTY ---
else:
    st.header("Zarządzanie Produktami")
    
    with st.expander("Dodaj nowy produkt"):
        df_kat = pd.read_sql_query("SELECT id, nazwa FROM kategorie", conn)
        kat_dict = dict(zip(df_kat['nazwa'], df_kat['id']))
        
        nazwa_prod = st.text_input("Nazwa produktu")
        liczba = st.number_input("Liczba", min_value=0, step=1)
        cena = st.number_input("Cena", min_value=0.0, step=0.01)
        kat_wybor = st.selectbox("Kategoria", list(kat_dict.keys()))
        
        if st.button("Dodaj Produkt"):
            conn.execute("INSERT INTO produkty (nazwa, liczba, cena, kategoria_id) VALUES (?, ?, ?, ?)",
                         (nazwa_prod, liczba, cena, kat_dict[kat_wybor]))
            conn.commit()
            st.success(f"Dodano produkt: {nazwa_prod}")

    st.subheader("Lista Produktów")
    query = '''SELECT p.id, p.nazwa, p.liczba, p.cena, k.nazwa as kategoria 
               FROM produkty p JOIN kategorie k ON p.kategoria_id = k.id'''
    df_prod = pd.read_sql_query(query, conn)
    st.dataframe(df_prod, use_container_width=True)

    with st.expander("Usuń produkt"):
        prod_id = st.number_input("Podaj ID produktu do usunięcia", min_value=1, step=1)
        if st.button("Usuń Produkt"):
            conn.execute("DELETE FROM produkty WHERE id = ?", (prod_id,))
            conn.commit()
            st.warning(f"Produkt o ID {prod_id} został usunięty.")
            st.rerun()
