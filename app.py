import streamlit as st
import pandas as pd
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Sayfa ayarları
st.set_page_config(page_title="Petrol-İş TİS Servisi v1.5", layout="wide")

# --- KULLANICI VERİTABANI ---
users = {
    "ozgun2026": {"isim": "Özgün Çelik Aygün", "sifre": "ozgun123"},
    "tugce2026": {"isim": "Tuğçe Kalyoncu", "sifre": "tugce456"},
    "melis2026": {"isim": "Melis Akkuzu", "sifre": "melis789"},
    "serkan2026": {"isim": "Serkan Gümüşbaş", "sifre": "serkan321"}
}

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True

    st.markdown("<h2 style='text-align: center;'>🔐 Petrol-İş TİS Servisi Giriş</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1]) 
    with col2:
        user_id = st.text_input("Kullanıcı ID")
        password = st.text_input("Şifre", type="password")
        if st.button("Sisteme Giriş Yap"):
            if user_id in users and password == users[user_id]["sifre"]:
                st.session_state["password_correct"] = True
                st.session_state["active_user"] = users[user_id]["isim"]
                st.rerun()
            else: st.error("❌ Geçersiz Kullanıcı ID veya Şifre!")
    return False

if not check_password(): st.stop()

# --- YARDIMCI FONKSİYONLAR ---
def get_box_color(val, tip):
    if val == 0: return "#FFEBEE"
    elif tip == "Net": return "#E8F5E9"
    else: return "#FFFDE7"

def calc_hybrid(val, mode, daily_base):
    if mode == "Maktu": return val
    elif mode == "Katsayı (Gün)": return daily_base * val
    elif mode == "Yüzde (%)": return daily_base * 30 * (val / 100)
    return 0

def brutlestir(tutar, tip, oran, sabit):
    if tip == "Brüt": return tutar
    return (tutar - sabit) / oran

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👤 Uzman: **{st.session_state['active_user']}**")
    if st.button("Güvenli Çıkış"):
        st.session_state["password_correct"] = False
        st.rerun()
    asgari_ucret_limit = st.number_input("Güncel Asgari Ücret (Brüt)", value=33030.00)
    oran_etiketleri = {0.71491: "%15 Vergi Dilimi", 0.67241: "%20 Vergi Dilimi", 0.61291: "%27 Vergi Dilimi", 0.54491: "%35 Vergi Dilimi"}
    secilen_oran = st.radio("📉 Vergi Dilimi", options=list(oran_etiketleri.keys()), format_func=lambda x: oran_etiketleri[x], index=1)
    aile_yasal = st.number_input("657 Aile Yardımı", value=3154.63)
    cocuk_6_ustu_yasal = st.number_input("657 Çocuk (6+)", value=346.97)
    sabit_vergi_ind = oran_etiketleri[secilen_oran] # Buraya kendi mantığına göre sabitleri eşleştir

# --- ANA ARAYÜZ ---
tab1, tab2 = st.tabs(["💰 Ücret ve Sosyal Ödemeler", "🏢 İşyeri Bilgileri"])

with tab2:
    isyeri_adi = st.text_input("İşyeri Adı")
    subeler = st.multiselect("Şubeler", ["Adana", "İstanbul 1", "Kocaeli"])
    uye_sayisi = st.number_input("Üye Sayısı", value=0)
    grev_yasagi = st.selectbox("Grev Yasağı", ["Yok", "Var"])

with tab1:
    sabit_deger = 5865.80 # Örnek sabit
    c1, c2, c3 = st.columns(3)
    with c1:
        u_tipi = st.radio("Ücret Tipi", ["Net", "Brüt"])
        u_tutar = st.number_input("Maaş", value=20000.0)
    
    a_brut = (u_tutar - sabit_deger) / secilen_oran if u_tipi == "Net" else u_tutar
    g_brut = a_brut / 30

    st.markdown("### 🎁 Sosyal Yardımlar")
    # ... (Buraya üstte verdiğim renkli kod bloklarını yapıştır)
    # Hesaplamalar ve Kayıt Butonu kodu buraya gelecek...
    
    st.success("Tüm sistem güncellendi ve renkli mod aktif!")
