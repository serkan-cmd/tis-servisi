import streamlit as st
import pandas as pd
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Sayfa ayarları
st.set_page_config(page_title="Petrol-İş TİS Servisi v1.2", layout="wide")

# --- GÜVENLİK PANELİ ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True

    st.markdown("<h2 style='text-align: center;'>🔐 Petrol-İş TİS Servisi Giriş</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1]) 
    with col2:
        password = st.text_input("Lütfen Giriş Şifresini Yazın", type="password")
        if st.button("Giriş Yap"):
            if password == "tis2026": 
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ Hatalı şifre!")
    return False

if not check_password():
    st.stop()

# --- UYGULAMA BAŞLANGICI ---
with st.sidebar:
    if st.button("Güvenli Çıkış"):
        st.session_state["password_correct"] = False
        st.rerun()
    st.header("⚙️ Genel Ayarlar")
    net_brut_oran = st.number_input("Net-Brüt Oranı", value=0.67241, format="%.5f")
    asgari_ucret_limit = st.number_input("Güncel Asgari Ücret (Brüt)", value=33030.00)

st.title("📊 Petrol-İş TİS Servisi")
st.markdown("---")

# Ana Ekran: Veri Girişi
col1, col2 = st.columns(2)

with col1:
    isyeri = st.text_input("İşyeri Adı", placeholder="Örn: ABC Tekstil")
    ucret_tipi = st.radio("Ücret Tipi", ["Net", "Brüt"])
    ucret = st.number_input("Ortalama Aylık Maaş", value=20000.0)

with col2:
    st.subheader("🔗 Ücrete Bağlı Ek Ödeme")
    ek_odeme_modu = st.selectbox("Hesaplama Modu", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"])
    ek_odeme_degeri = st.number_input("Değer (Örn: %75 için 75)", value=0.0)
    periyot = st.selectbox("Ödeme Periyodu", ["Aylık", "Yıllık"])

# Sosyal Yardımlar Bölümü
st.markdown("### 🎁 Sosyal Yardımlar")
yardim_col1, yardim_col2, yardim_col3 = st.columns(3)

with yardim_col1:
    gıda = st.number_input("Aylık Gıda Yardımı (Brüt)", value=170.0)
with yardim_col2:
    yakacak = st.number_input("Aylık Yakacak Yardımı (Brüt)", value=1000.0)
with yardim_col3:
    ikramiye_gun = st.number_input("Yıllık İkramiye (Gün Sayısı)", value=60)

# --- HESAPLAMA MANTIĞI ---
aylik_ana_brut = ucret / net_brut_oran if ucret_tipi == "Net" else ucret
gunluk_brut = aylik_ana_brut / 30

if ek_odeme_modu == "Yüzde (%)":
    ek_brut = gunluk_brut * (ek_odeme_degeri / 100)
elif ek_odeme_modu == "Katsayı (Gün)":
    ek_brut = gunluk_brut * ek_odeme_degeri
else:
    ek_brut = ek_odeme_degeri
aylik_ek_ucret = ek_brut if periyot == "Aylık" else ek_brut / 12

aylik_ikramiye_maliyeti = (gunluk_brut * ikramiye_gun) / 12
toplam_sosyal_yardim = gıda + yakacak + aylik_ikramiye_maliyeti
toplam_aylik_maliyet = aylik_ana_brut + aylik_ek_ucret + toplam_sosyal_yardim

# --- SONUÇLAR VE UYARILAR ---
st.divider()

if aylik_ana_brut < asgari_ucret_limit:
    st.error(f"⚠️ UYARI: Hesaplanan Ana Brüt ({aylik_ana_brut:,.2f} TL), yasal asgari ücretin altında!")

m1, m2, m3 = st.columns(3)
m1.metric("Toplam Aylık Brüt Maliyet", f"{toplam_aylik_maliyet:,.2f} TL")
m2.metric("Sadece Sosyal Paket (Aylık)", f"{toplam_sosyal_yardim:,.2f} TL")
m3.metric("Ücrete Bağlı Ek (Aylık)", f"{aylik_ek_ucret:,.2f} TL")

# Detaylı Tablo
detay_data = {
    "Kalem": ["Ana Maaş (Brüt)", "Ücrete Bağlı Ek Ödeme", "Gıda", "Yakacak", "İkramiye (Pay)"],
    "Tutar (TL)": [aylik_ana_brut, aylik_ek_ucret, gıda, yakacak, aylik_ikramiye_maliyeti]
}
st.table(pd.DataFrame(detay_data))

# --- KAYIT VE EXCEL İŞLEMLERİ ---
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("💾 Veritabanına (Google Sheets) Kaydet"):
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            
            # Secrets'tan TOML formatındaki verileri dict olarak alıyoruz
            s = st.secrets["connections"]["gsheets"]
            creds_dict = {
                "type": s["type"],
                "project_id": s["project_id"],
                "private_key_id": s["private_key_id"],
                "private_key": s["private_key"],
                "client_email": s["client_email"],
                "client_id": s["client_id"],
                "auth_uri": s["auth_uri"],
                "token_uri": s["token_uri"],
                "auth_provider_x509_cert_url": s["auth_provider_x509_cert_url"],
                "client_x509_cert_url": s["client_x509_cert_url"]
            }
            
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            
            # Tablo ID'si
            sheet = client.open_by_key("1kb6ceU5NjBNl1PB3vCspw90s8lYRVU7XVbMt97tfEbg").sheet1
            
            yeni_satir = [
                datetime.now().strftime("%d/%m/%Y %H:%M"),
                "Petrol-İş Temsilcisi",
                isyeri,
                f"{aylik_ana_brut:.2f}",
                f"{aylik_ek_ucret:.2f}",
                f"{toplam_sosyal_yardim:.2f}",
                f"{toplam_aylik_maliyet:.2f}"
            ]
            
            sheet.append_row(yeni_satir)
            st.success(f"✅ {isyeri} başarıyla kaydedildi!")
            st.balloons()
            
        except Exception as e:
            st.error(f"Kayıt Hatası: {e}")

with col_btn2:
    df_excel = pd.DataFrame(detay_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_excel.to_excel(writer, index=False)
    st.download_button("📥 Excel İndir", output.getvalue(), f"{isyeri}.xlsx")
