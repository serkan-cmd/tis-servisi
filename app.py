import streamlit as st
import pandas as pd
import io

# Sayfa ayarları
st.set_page_config(page_title="Petrol-İş TİS Servisi v1.1", layout="wide")

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
    asgari_ucret = st.number_input("Güncel Asgari Ücret (Brüt)", value=33030.00)

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
# 1. Ana Brüt Maaş
aylik_ana_brut = ucret / net_brut_oran if ucret_tipi == "Net" else ucret
gunluk_brut = aylik_ana_brut / 30

# 2. Ücrete Bağlı Ek Ödeme (TİS Maddesi)
if ek_odeme_modu == "Yüzde (%)":
    ek_brut = gunluk_brut * (ek_odeme_degeri / 100)
elif ek_odeme_modu == "Katsayı (Gün)":
    ek_brut = gunluk_brut * ek_odeme_degeri
else:
    ek_brut = ek_odeme_degeri
aylik_ek_ucret = ek_brut if periyot == "Aylık" else ek_brut / 12

# 3. Sosyal Yardım Maliyetleri (Aylık)
aylik_ikramiye_maliyeti = (gunluk_brut * ikramiye_gun) / 12
toplam_sosyal_yardim = gıda + yakacak + aylik_ikramiye_maliyeti

# 4. Genel Toplam
toplam_aylik_maliyet = aylik_ana_brut + aylik_ek_ucret + toplam_sosyal_yardim

# --- SONUÇLAR ---
st.divider()
m1, m2, m3 = st.columns(3)
m1.metric("Toplam Aylık Brüt Maliyet", f"{toplam_aylik_maliyet:,.2f} TL")
m2.metric("Sadece Sosyal Paket (Aylık)", f"{toplam_sosyal_yardim:,.2f} TL")
m3.metric("Ücrete Bağlı Ek (Aylık)", f"{aylik_ek_ucret:,.2f} TL")

# Detaylı Tablo Gösterimi
st.markdown("#### 📝 Maliyet Detayları")
detay_data = {
    "Kalem": ["Ana Maaş (Brüt)", "Ücrete Bağlı Ek Ödeme", "Gıda (Aylık Ort.)", "Yakacak", "İkramiye (Aylık Pay)"],
    "Tutar (TL)": [aylik_ana_brut, aylik_ek_ucret, gıda, yakacak, aylik_ikramiye_maliyeti]
}
st.table(pd.DataFrame(detay_data))

# Excel Çıktısı
if st.button("📊 Excel Çıktısı Hazırla"):
    df = pd.DataFrame(detay_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='TIS_Maliyet_Ozeti')
    
    st.download_button(
        label="📥 Excel Dosyasını İndir",
        data=output.getvalue(),
        file_name=f"tis_maliyet_{isyeri}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
