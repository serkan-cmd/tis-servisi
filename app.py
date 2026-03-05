import streamlit as st
import pandas as pd

# Sayfa ayarları
st.set_page_config(page_title="Petrol-İş TİS Servisi v1.0", layout="wide")

# --- GÜVENLİK PANELİ FONKSİYONU ---
def check_password():
    """Doğru şifre girilirse True döndürür."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    # Giriş Ekranı Tasarımı
    st.markdown("<h2 style='text-align: center;'>🔐 Petrol-İş TİS Servisi Giriş</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1]) 
    with col2:
        password = st.text_input("Lütfen Giriş Şifresini Yazın", type="password")
        if st.button("Giriş Yap"):
            # ŞİFREYİ BURADAN DEĞİŞTİREBİLİRSİN
            if password == "tis2026": 
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("❌ Hatalı şifre! Lütfen tekrar deneyin.")
    return False

# Şifre kontrolü geçilemezse uygulamanın geri kalanını çalıştırma
if not check_password():
    st.stop()

# --- UYGULAMA BAŞLANGICI (Şifre doğruysa burası çalışır) ---

# Yan Menüde Çıkış Butonu
with st.sidebar:
    if st.button("Güvenli Çıkış"):
        st.session_state["password_correct"] = False
        st.rerun()

st.title("📊 Petrol-İş TİS Servisi")
st.markdown("---")

# Yan Menü: Sabit Parametreler
with st.sidebar:
    st.header("⚙️ Genel Ayarlar")
    net_brut_oran = st.number_input("Net-Brüt Oranı", value=0.67241, format="%.5f")
    asgari_ucret = st.number_input("Güncel Asgari Ücret (Brüt)", value=20002.50)

# Ana Ekran: Veri Girişi
col1, col2 = st.columns(2)

with col1:
    isyeri = st.text_input("İşyeri Adı", placeholder="Örn: ABC Tekstil")
    ucret_tipi = st.radio("Ücret Tipi", ["Net", "Brüt"])
    ucret = st.number_input("Ortalama Aylık Ücret", value=20000.0)

with col2:
    st.subheader("Ücrete Bağlı Ek Ödeme")
    ek_odeme_modu = st.selectbox("Hesaplama Modu", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"])
    ek_odeme_degeri = st.number_input("Değer (Örn: %75 için 75)", value=0.0)
    periyot = st.selectbox("Ödeme Periyodu", ["Aylık", "Yıllık"])

# --- HESAPLAMA MANTIĞI ---
# 1. Brüt Maaşı Bul
aylik_brut = ucret / net_brut_oran if ucret_tipi == "Net" else ucret
gunluk_brut = aylik_brut / 30

# 2. Ek Ödemeyi Hesapla
if ek_odeme_modu == "Yüzde (%)":
    ek_brut = gunluk_brut * (ek_odeme_degeri / 100)
elif ek_odeme_modu == "Katsayı (Gün)":
    ek_brut = gunluk_brut * ek_odeme_degeri
else:
    ek_brut = ek_odeme_degeri # Maktu brüt varsayıyoruz

# Eğer yıllık ise aya böl
hesaplanan_ek = ek_brut if periyot == "Aylık" else ek_brut / 12

# Sosyal Yardımlar Bölümü
st.subheader("🎁 Sosyal Yardımlar")
yardim_col1, yardim_col2 = st.columns(2)

with yardim_col1:
    yemek = st.number_input("Günlük Yemek Yardımı (Brüt)", value=170.0)
    yakacak = st.number_input("Aylık Yakacak Yardımı (Brüt)", value=1000.0)

with yardim_col2:
    ikramiye_gun = st.number_input("Yıllık İkramiye (Gün Sayısı)", value=60)

# 3. Sonuçları Göster
st.divider()
toplam_maliyet = aylik_brut + hesaplanan_ek

res1, res2 = st.columns(2)
res1.metric("Toplam Aylık Brüt Maliyet", f"{toplam_maliyet:,.2f} TL")
res2.metric("Ek Ödeme Payı (Brüt)", f"{hesaplanan_ek:,.2f} TL")

if st.button("📊 Excel Çıktısı Hazırla"):
    df = pd.DataFrame([{
        "İşyeri": isyeri,
        "Brüt Maaş": aylik_brut,
        "Ek Ödeme": hesaplanan_ek,
        "Toplam": toplam_maliyet
    }])
    # Excel dosyasını indirme butonu ekleme (Streamlit yolu)
    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Özet')
    
    st.download_button(
        label="📥 Excel Dosyasını İndir",
        data=output.getvalue(),
        file_name=f"tis_ozet_{isyeri}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
