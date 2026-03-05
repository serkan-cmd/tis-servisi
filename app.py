import streamlit as st
import pandas as pd
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Sayfa ayarları
st.set_page_config(page_title="Petrol-İş TİS Servisi v1.5", layout="wide")

# --- KULLANICI VERİTABANI (ÖZEL ŞİFRELER) ---
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
    asgari_ucret_limit = st.number_input("Güncel Asgari Ücret (Brüt)", value=33030.00)
    
    st.subheader("⚖️ Yasal Yardımlar")
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
    c1, c2 = st.columns(2)
    with c1:
        u_tipi = st.radio("Ücret Tipi", ["Net", "Brüt"])
        u_tutar = st.number_input("Maaş Tutarı", value=20000.0)
    with c2:
        ek_mod = st.selectbox("Ek Ödeme Modu", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"])
        ek_val = st.number_input("Ek Ödeme Değeri", value=0.0)
        ek_per = st.selectbox("Periyot", ["Aylık", "Yıllık"])

    # --- HESAPLAMA ÇEKİRDEĞİ ---
    sabitler = {0.71491: 4462.03, 0.67241: 4788.45, 0.61291: 5865.80, 0.54491: 5865.80}
    a_brut = (u_tutar - sabitler[secilen_oran]) / secilen_oran if u_tipi == "Net" else u_tutar
    g_brut = a_brut / 30

    def calc_hybrid(val, mode, daily_base):
        if mode == "Maktu": return val
        elif mode == "Katsayı (Gün)": return daily_base * val
        elif mode == "Yüzde (%)": return daily_base * 30 * (val / 100)
        return 0

    st.markdown("### 🎁 Sosyal Yardımlar (Dinamik)")
    y1, y2, y3 = st.columns(3)
    
    with y1:
        gida = st.number_input("Gıda (Aylık/Brüt)", 1000.0)
        yakacak = st.number_input("Yakacak (Aylık/Brüt)", 1000.0)
        izin_mod = st.selectbox("İzin Parası Tipi", ["Maktu", "Katsayı (Gün)"])
        izin_val = st.number_input("İzin Değeri", 0.0)
        giyim = st.number_input("Giyim Yardımı (Yıllık)", 0.0)
        yasal_aile = st.checkbox("Yasal Aile Yardımı Uygula")

    with y2:
        yemek = st.number_input("Yemek (Günlük/Brüt)", 0.0)
        bayram_mod = st.selectbox("Bayram Yardımı Tipi", ["Maktu", "Katsayı (Gün)"])
        bayram_val = st.number_input("Bayram Değeri (Yıllık Toplam)", 0.0)
        ayakkabi = st.number_input("Ayakkabı (Yıllık)", 0.0)
        yilbasi = st.number_input("Yılbaşı Parası", 0.0)
        c06 = st.number_input("0-6 Çocuk Sayısı", 0, step=1)

    with y3:
        ikramiye = st.number_input("İkramiye (Yıllık Gün)", 120)
        prim_mod = st.selectbox("Prim Tipi", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"])
        prim_val = st.number_input("Prim Değeri", 0.0)
        diger = st.number_input("Diğer Sosyal (Aylık)", 0.0)
        maktu_aile = st.number_input("Maktu Aile Yardımı", 0.0)
        c6ustu = st.number_input("6+ Çocuk Sayısı", 0, step=1)

    st.markdown("### ⚡ Vardiya ve Gece Zamları")
    v1, v2 = st.columns(2)
    with v1:
        v_tip = st.selectbox("Vardiya Zammı Tipi", ["Sabit (Doğrudan Eklenir)", "Fiili Çalışma (195/225)"])
        v_mod = st.selectbox("Vardiya Hesaplama", ["Maktu", "Yüzde (%)"])
        v_val = st.number_input("Vardiya Değeri", 0.0)
    with v2:
        g_tip = st.selectbox("Gece Zammı Tipi", ["Sabit (Doğrudan Eklenir)", "Fiili Çalışma (80/225)"])
        g_mod = st.selectbox("Gece Hesaplama", ["Maktu", "Yüzde (%)"])
        g_val = st.number_input("Gece Değeri", 0.0)

    # --- HESAPLAMALAR ---
    ay_ek = calc_hybrid(ek_val, ek_mod, g_brut) if ek_per == "Aylık" else calc_hybrid(ek_val, ek_mod, g_brut) / 12
    ay_izin = calc_hybrid(izin_val, izin_mod, g_brut) / 12
    ay_bayram = calc_hybrid(bayram_val, bayram_mod, g_brut) / 12
    ay_prim = calc_hybrid(prim_val, prim_mod, g_brut)
    ay_giyim = (giyim + ayakkabi) / 12
    ay_ikramiye = (g_brut * ikramiye) / 12
    ay_yasal_sosyal = (aile_yasal if yasal_aile else 0) + (c06 * cocuk_0_6_yasal) + (c6ustu * cocuk_6_ustu_yasal)
    
    # Vardiya Hesaplama
    v_tutar = calc_hybrid(v_val, v_mod, g_brut)
    if v_tip == "Fiili Çalışma (195/225)": v_tutar = (v_tutar * 195) / 225
    
    # Gece Hesaplama
    g_tutar = calc_hybrid(g_val, g_mod, g_brut)
    if g_tip == "Fiili Çalışma (80/225)": g_tutar = (g_tutar * 80) / 225

    toplam_sosyal = gida + yakacak + ay_izin + ay_bayram + ay_prim + ay_giyim + ay_ikramiye + ay_yasal_sosyal + yilbasi/12 + diger + maktu_aile + (yemek*22.5) + v_tutar + g_tutar
    t_maliyet = a_brut + ay_ek + toplam_sosyal

    # --- SONUÇLAR ---
    st.divider()
    res1, res2, res3 = st.columns(3)
    res1.metric("Toplam Aylık Brüt Maliyet", f"{t_maliyet:,.2f} TL")
    res2.metric("Toplam Sosyal Paket", f"{toplam_sosyal:,.2f} TL")
    res3.metric("Ana Maaş (Brüt)", f"{a_brut:,.2f} TL")

    detay = {
        "Kalem": ["Ana Maaş", "Ek Ödeme", "Sosyal Paket Toplamı", "İkramiye Payı", "Vardiya/Gece Zammı"],
        "Tutar": [a_brut, ay_ek, toplam_sosyal, ay_ikramiye, v_tutar + g_tutar]
    }
    st.table(pd.DataFrame(detay))

   # --- KAYIT VE EXCEL ---
    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("💾 Veritabanına (Google Sheets) Kaydet"):
            try:
                scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                s = st.secrets["connections"]["gsheets"]
                creds_dict = {
                    "type": s["type"], "project_id": s["project_id"], "private_key_id": s["private_key_id"],
                    "private_key": s["private_key"], "client_email": s["client_email"], "client_id": s["client_id"],
                    "auth_uri": s["auth_uri"], "token_uri": s["token_uri"],
                    "auth_provider_x509_cert_url": s["auth_provider_x509_cert_url"],
                    "client_x509_cert_url": s["client_x509_cert_url"]
                }
                
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                client = gspread.authorize(creds)
                sheet = client.open_by_key("1kb6ceU5NjBNl1PB3vCspw90s8lYRVU7XVbMt97tfEbg").sheet1
                
                # Google Sheets'e gidecek veri listesi (Sütunları istediğin gibi artırabilirsin)
                yeni_satir = [
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                    st.session_state["active_user"],
                    isyeri_adi,
                    ", ".join(subeler), # Listeyi metne çevirir (Adana, Gebze gibi)
                    uye_sayisi,
                    grev_yasagi,
                    f"{a_brut:.2f}",
                    f"{toplam_sosyal:.2f}",
                    f"{t_maliyet:.2f}"
                ]
                
                sheet.append_row(yeni_satir)
                st.success(f"✅ {isyeri_adi} verileri başarıyla kaydedildi!")
                st.balloons()
            except Exception as e:
                st.error(f"Kayıt Hatası: {e}")

    with col_btn2:
        # Excel çıktısı için detay tablosunu kullanıyoruz
        df_excel = pd.DataFrame(detay)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_excel.to_excel(writer, index=False)
        st.download_button("📥 Excel İndir", output.getvalue(), f"{isyeri_adi}.xlsx")
