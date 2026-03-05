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

# --- GÜVENLİK PANELİ ---
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

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👤 Uzman: **{st.session_state['active_user']}**")
    if st.button("Güvenli Çıkış"):
        st.session_state["password_correct"] = False
        st.rerun()
    st.divider()
    st.header("⚙️ Genel Ayarlar")
    oran_etiketleri = {
        0.71491: "%15 Vergi Dilimi", 0.67241: "%20 Vergi Dilimi",
        0.61291: "%27 Vergi Dilimi", 0.54491: "%35 Vergi Dilimi"
    }
    secilen_oran = st.radio("📉 Vergi Dilimi Seçimi", options=list(oran_etiketleri.keys()), 
                            format_func=lambda x: oran_etiketleri[x], index=1)
    
    st.subheader("⚖️ Yasal Yardımlar (Aylık)")
    aile_yasal = st.number_input("Yasal Aile Yardımı", value=3154.63)
    cocuk_0_6_yasal = st.number_input("Yasal Çocuk (0-6)", value=693.94)
    cocuk_6_ustu_yasal = st.number_input("Yasal Çocuk (6+)", value=346.97)

# --- SEKME YAPISI ---
tab1, tab2 = st.tabs(["💰 Ücret ve Sosyal Ödemeler", "🏢 İşyeri Bilgileri"])

with tab2:
    st.header("🏢 İşyeri ve Şube Bilgileri")
    col_is1, col_is2 = st.columns(2)
    with col_is1:
        isyeri_adi = st.text_input("İşyeri Tam Adı", placeholder="Örn: ABC Kimya A.Ş.")
        subeler = st.multiselect("Bağlı Olduğu Şubeler", ["Adana", "Adıyaman", "Ankara", "Bandırma", "Batman", "Bursa", "Ceyhan", "Çankırı", "Gebze", "İstanbul 1", "İstanbul 2", "İzmir", "Kırıkkale", "Kocaeli", "Mersin", "Trakya", "Aliağa"])
    with col_is2:
        toplam_calisan = st.number_input("Toplam Çalışan Sayısı", value=0)
        uye_sayisi = st.number_input("Sendikalı Üye Sayısı", value=0)
        grev_yasagi = st.selectbox("Grev Yasağı Durumu", ["Grev Yasağı Yok", "Grev Yasağı Var"])

with tab1:
    st.header("💵 Ücret ve Ek Ödemeler")
    c1, c2, c3 = st.columns(3)
    with c1:
        u_tipi = st.radio("Ücret Tipi", ["Net", "Brüt"])
        u_tutar = st.number_input("Maaş Tutarı", value=20000.0)
    with c2:
        st.info("Ek Ödeme 1")
        ek_mod = st.selectbox("Hesaplama Modu", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"], key="ek1_mod")
        ek_val = st.number_input("Değer", value=0.0, key="ek1_val")
        ek_per = st.selectbox("Periyot", ["Aylık", "Yıllık"], key="ek1_per")
    with c3:
        st.info("Ek Ödeme 2 (Yeni)")
        ek2_mod = st.selectbox("Hesaplama Modu", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"], key="ek2_mod")
        ek2_val = st.number_input("Değer", value=0.0, key="ek2_val")
        ek2_per = st.selectbox("Periyot", ["Aylık", "Yıllık"], key="ek2_per")

    # --- HESAPLAMA ÇEKİRDEĞİ ---
    sabitler = {0.71491: 4462.03, 0.67241: 4788.45, 0.61291: 5865.80, 0.54491: 5865.80}
    a_brut = (u_tutar - sabitler[secilen_oran]) / secilen_oran if u_tipi == "Net" else u_tutar
    g_brut = a_brut / 30

    def calc_hybrid(val, mode, daily_base):
        if mode == "Maktu": return val
        elif mode == "Katsayı (Gün)": return daily_base * val
        elif mode == "Yüzde (%)": return daily_base * 30 * (val / 100)
        return 0

    st.markdown("### 🎁 Sosyal Yardımlar")
    y1, y2, y3 = st.columns(3)
    
    with y1:
        gida = st.number_input("Gıda (Aylık/Brüt)", 0.0)
        yakacak = st.number_input("Yakacak (Aylık/Brüt)", 0.0)
        giyim = st.number_input("Giyim Yardımı (Yıllık)", 0.0)
        ayakkabi = st.number_input("Ayakkabı (Yıllık)", 0.0)
        yilbasi = st.number_input("Yılbaşı Parası (Yıllık)", 0.0)
        ikramiye = st.number_input("İkramiye (Yıllık Toplam Gün)", 120)

    with y2:
        with st.container(border=True):
            st.write("📅 **İzin Parası**")
            izin_mod = st.selectbox("Tipi", ["Maktu", "Katsayı (Gün)"], key="iz_m")
            izin_val = st.number_input("Değeri", 0.0, key="iz_v")
        
        with st.container(border=True):
            st.write("🎉 **Bayram Yardımı**")
            bayram_mod = st.selectbox("Tipi", ["Maktu", "Katsayı (Gün)"], key="ba_m")
            bayram_val = st.number_input("Değeri (Yıllık Toplam)", 0.0, key="ba_v")

    with y3:
        with st.container(border=True):
            st.write("🏆 **Prim Ödemesi**")
            prim_mod = st.selectbox("Tipi", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"], key="pr_m")
            prim_val = st.number_input("Değeri", 0.0, key="pr_v")
        
        with st.container(border=True):
            st.write("👨‍👩‍👧‍👦 **Aile & Çocuk Yardımı**")
            
            # Aile Yardımı Bölümü
            yasal_aile = st.checkbox("Yasal Aile Yardımı Uygula")
            maktu_aile = st.number_input("Maktu Ek Aile Yardımı", 0.0, help="Sendika tarafından kazanılan sabit tutar")
            
            st.divider()
            
            # Çocuk Yardımı Bölümü
            yasal_cocuk_tik = st.checkbox("Yasal Çocuk Zammı Uygula", help="Yasal 6+ yaş tutarının 2 katı (Her çocuk için)")
            maktu_cocuk_birim = st.number_input("Maktu Çocuk Yardımı (Birim)", 0.0, help="Çocuk başına maktu ödeme tutarı")
    st.divider()
    st.markdown("### ⚡ Özel Ödemeler (Vardiya, Gece ve Ek)")
    v1, v2, v3 = st.columns(3)
    
    with v1:
        with st.container(border=True):
            st.write("🔄 **Vardiya Zammı**")
            v_tip = st.selectbox("Hesaplama Türü", ["Sabit", "Fiili (195/225)"])
            v_mod = st.selectbox("Birim", ["Maktu", "Yüzde (%)"], key="v_m")
            v_val = st.number_input("Miktar", 0.0, key="v_v")
            
    with v2:
        with st.container(border=True):
            st.write("🌙 **Gece Zammı**")
            g_tip = st.selectbox("Hesaplama Türü", ["Sabit", "Fiili (80/225)"])
            g_mod = st.selectbox("Birim", ["Maktu", "Yüzde (%)"], key="g_m")
            g_val = st.number_input("Miktar", 0.0, key="g_v")

    with v3:
        with st.container(border=True):
            st.write("➕ **Ücrete Bağlı Ek Özel**")
            ek_ozel_tip = st.selectbox("Baz Alınacak Ücret", ["Günlük Ücret", "Aylık Ücret"])
            ek_ozel_mod = st.selectbox("Birim", ["Katsayı", "Yüzde (%)"], key="eo_m")
            ek_ozel_val = st.number_input("Miktar", 0.0, key="eo_v")

    # --- HESAPLAMALAR ---
    ay_ek1 = calc_hybrid(ek_val, ek_mod, g_brut) if ek_per == "Aylık" else calc_hybrid(ek_val, ek_mod, g_brut) / 12
    ay_ek2 = calc_hybrid(ek2_val, ek2_mod, g_brut) if ek2_per == "Aylık" else calc_hybrid(ek2_val, ek2_mod, g_brut) / 12
    
    # Yeni Ek Özel Ödeme Hesaplaması
    if ek_ozel_tip == "Günlük Ücret":
        ay_ek_ozel = g_brut * (ek_ozel_val if ek_ozel_mod == "Katsayı" else ek_ozel_val / 100)
    else:
        ay_ek_ozel = a_brut * (ek_ozel_val if ek_ozel_mod == "Katsayı" else ek_ozel_val / 100)

    ay_izin = calc_hybrid(izin_val, izin_mod, g_brut) / 12
    ay_bayram = calc_hybrid(bayram_val, bayram_mod, g_brut) / 12
    ay_prim = calc_hybrid(prim_val, prim_mod, g_brut)
    ay_yasal_sosyal = (aile_yasal if yasal_aile else 0) + (c06 * cocuk_0_6_yasal) + (c6ustu * cocuk_6_ustu_yasal)
    
    # Vardiya ve Gece Hesaplama
    v_tutar = calc_hybrid(v_val, v_mod, g_brut)
    if v_tip == "Fiili (195/225)": v_tutar = (v_tutar * 195) / 225
    
    g_tutar = calc_hybrid(g_val, g_mod, g_brut)
    if g_tip == "Fiili (80/225)": g_tutar = (g_tutar * 80) / 225

    ay_ikramiye = (g_brut * ikramiye) / 12
    toplam_sosyal = gida + yakacak + ay_izin + ay_bayram + ay_prim + (giyim+ayakkabi+yilbasi)/12 + ay_ikramiye + ay_yasal_sosyal + maktu_aile + v_tutar + g_tutar + ay_ek_ozel
    t_maliyet = a_brut + ay_ek1 + ay_ek2 + toplam_sosyal

    # --- SONUÇLAR ---
    st.divider()
    res1, res2, res3 = st.columns(3)
    res1.metric("Toplam Aylık Brüt Maliyet", f"{t_maliyet:,.2f} TL")
    res2.metric("Toplam Sosyal Paket", f"{toplam_sosyal:,.2f} TL")
    res3.metric("Ana Maaş (Brüt)", f"{a_brut:,.2f} TL")

    detay_df = pd.DataFrame({
        "Kalem": ["Ana Maaş", "Ek Ödemeler (1+2)", "Sosyal Paket", "Vardiya/Gece/Özel Ek"],
        "Tutar": [a_brut, ay_ek1 + ay_ek2, toplam_sosyal - (v_tutar + g_tutar + ay_ek_ozel), v_tutar + g_tutar + ay_ek_ozel]
    })
    st.table(detay_df)

    # --- KAYIT ---
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("💾 Veritabanına Kaydet"):
            try:
                scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                s = st.secrets["connections"]["gsheets"]
                creds = ServiceAccountCredentials.from_json_keyfile_dict({
                    "type": s["type"], "project_id": s["project_id"], "private_key_id": s["private_key_id"],
                    "private_key": s["private_key"], "client_email": s["client_email"], "client_id": s["client_id"],
                    "auth_uri": s["auth_uri"], "token_uri": s["token_uri"],
                    "auth_provider_x509_cert_url": s["auth_provider_x509_cert_url"],
                    "client_x509_cert_url": s["client_x509_cert_url"]
                }, scope)
                client = gspread.authorize(creds)
                sheet = client.open_by_key("1kb6ceU5NjBNl1PB3vCspw90s8lYRVU7XVbMt97tfEbg").sheet1
                
                sheet.append_row([
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                    st.session_state["active_user"], isyeri_adi, ", ".join(subeler),
                    uye_sayisi, grev_yasagi, f"{a_brut:.2f}", f"{toplam_sosyal:.2f}", f"{t_maliyet:.2f}"
                ])
                st.success("✅ Kaydedildi!")
                st.balloons()
            except Exception as e: st.error(f"Hata: {e}")

    with col_btn2:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            detay_df.to_excel(writer, index=False)
        st.download_button("📥 Excel İndir", output.getvalue(), f"{isyeri_adi}_hesap.xlsx")
