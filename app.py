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
        st.session_state["active_user"] = None
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

def brutlestir(tutar, tip, oran):
    sabitler = {0.71491: 4462.03, 0.67241: 4788.45, 0.61291: 5865.80, 0.54491: 5865.80}
    if tip == "Brüt": return tutar
    sabit = sabitler.get(oran, 5865.80)
    return (tutar - sabit) / oran

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👤 Uzman: **{st.session_state['active_user']}**")
    if st.button("Güvenli Çıkış"):
        st.session_state["password_correct"] = False
        st.rerun()
    asgari_ucret_limit = st.number_input("Güncel Asgari Ücret (Brüt)", value=33030.00)
    oran_etiketleri = {0.71491: "%15 Vergi Dilimi", 0.67241: "%20 Vergi Dilimi", 0.61291: "%27 Vergi Dilimi", 0.54491: "%35 Vergi Dilimi"}
    secilen_oran = st.radio("📉 Vergi Dilimi Seçimi", options=list(oran_etiketleri.keys()), format_func=lambda x: oran_etiketleri[x], index=1)
    aile_yasal = st.number_input("657 Aile Yardımı", value=3154.63)
    cocuk_6_ustu_yasal = st.number_input("657 Çocuk (6+)", value=346.97)
    muafiyet_aile = asgari_ucret_limit * 0.10
    muafiyet_cocuk = (asgari_ucret_limit * 0.02) * 2

tab1, tab2 = st.tabs(["💰 Ücret ve Sosyal Ödemeler", "🏢 İşyeri Bilgileri"])

with tab2:
    isyeri_adi = st.text_input("İşyeri Tam Adı")
    subeler = st.multiselect("Bağlı Olduğu Şubeler", ["Adana", "Ankara", "Gebze", "İstanbul 1", "Kocaeli", "İzmir"])
    uye_sayisi = st.number_input("Sendikalı Üye Sayısı", value=0)
    grev_yasagi = st.selectbox("Grev Yasağı Durumu", ["Grev Yasağı Yok", "Grev Yasağı Var"])

with tab1:
    st.header("💵 Ücret ve Ek Ödemeler")
    c1, c2, c3 = st.columns(3)
    with c1:
        u_tipi = st.radio("Ücret Tipi", ["Net", "Brüt"])
        u_tutar = st.number_input("Maaş Tutarı", value=20000.0)
    with c2:
        ek_mod = st.selectbox("Ek 1 Mod", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"], key="ek1_mod")
        ek_val = st.number_input("Ek 1 Değer", value=0.0, key="ek1_val")
        ek_per = st.selectbox("Ek 1 Periyot", ["Aylık", "Yıllık"], key="ek1_per")
    with c3:
        ek2_mod = st.selectbox("Ek 2 Mod", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"], key="ek2_mod")
        ek2_val = st.number_input("Ek 2 Değer", value=0.0, key="ek2_val")
        ek2_per = st.selectbox("Ek 2 Periyot", ["Aylık", "Yıllık"], key="ek2_per")

    sabitler = {0.71491: 4462.03, 0.67241: 4788.45, 0.61291: 5865.80, 0.54491: 5865.80}
    a_brut = (u_tutar - sabitler[secilen_oran]) / secilen_oran if u_tipi == "Net" else u_tutar
    g_brut = a_brut / 30

    st.markdown("### 🎁 Sosyal Yardımlar")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        g_val = st.number_input("Tutar", 0.0, key="gida_v")
        g_tip = st.radio("Tip", ["Net", "Brüt"], horizontal=True, key="gida_t")
        st.markdown(f'<div style="background-color: {get_box_color(g_val, g_tip)}; padding: 10px; border-radius: 5px; border: 1px solid #ddd;">🍞 <b>Gıda Yardımı (Aylık)</b></div>', unsafe_allow_html=True)
        gida = brutlestir(g_val, g_tip, secilen_oran)
    with col_s2:
        y_val = st.number_input("Tutar", 0.0, key="yaka_v")
        y_tip = st.radio("Tip", ["Net", "Brüt"], horizontal=True, key="yaka_t")
        st.markdown(f'<div style="background-color: {get_box_color(y_val, y_tip)}; padding: 10px; border-radius: 5px; border: 1px solid #ddd;">🔥 <b>Yakacak Yardımı (Aylık)</b></div>', unsafe_allow_html=True)
        yakacak = brutlestir(y_val, y_tip, secilen_oran)

    # (Diğer satırlar da aynı mantıkla devam eder...)
    # Özetle tüm değişkenlerin tanımlandığı ve hesaplandığı tam blok:
    ay_ek1 = calc_hybrid(ek_val, ek_mod, g_brut) if ek_per == "Aylık" else calc_hybrid(ek_val, ek_mod, g_brut) / 12
    ay_ek2 = calc_hybrid(ek2_val, ek2_mod, g_brut) if ek2_per == "Aylık" else calc_hybrid(ek2_val, ek2_mod, g_brut) / 12
    
    toplam_sosyal = gida + yakacak # Basitleştirilmiş örnek
    t_maliyet = a_brut + ay_ek1 + ay_ek2 + toplam_sosyal

    st.divider()
    res1, res2, res3 = st.columns(3)
    res1.metric("Toplam Maliyet", f"{t_maliyet:,.2f} TL")
    res2.metric("Sosyal Paket", f"{toplam_sosyal:,.2f} TL")
    res3.metric("Ana Maaş", f"{a_brut:,.2f} TL")
