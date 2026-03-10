import streamlit as st
import pandas as pd
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="Petrol-İş TİS Servisi v1.7", layout="wide")

# --- SÜTUN BAŞLIKLARI (Sheets ile birebir eşleşmeli) ---
SHEET_HEADERS = [
    "İşlem Tarihi", "Uzman", "İşyeri", "Şubeler",
    "TİS Başlangıç", "TİS Bitiş", "Üye Sayısı", "Grev Durumu",
    "Toplam Çalışan",
    "Ana Maaş Tipi", "Ana Maaş Tutar",
    "Ek Ödeme 1 Mod", "Ek Ödeme 1 Değer", "Ek Ödeme 1 Periyot",
    "Ek Ödeme 2 Mod", "Ek Ödeme 2 Değer", "Ek Ödeme 2 Periyot",
    "Gıda Tip", "Gıda Tutar",
    "Yakacak Tip", "Yakacak Tutar",
    "Giyim Tip", "Giyim Tutar",
    "Ayakkabı Tip", "Ayakkabı Tutar",
    "Yılbaşı Tip", "Yılbaşı Tutar",
    "İzin Mod", "İzin Tip", "İzin Değer",
    "Bayram Mod", "Bayram Tip", "Bayram Değer",
    "Prim Mod", "Prim Tip", "Prim Değer",
    "İkramiye Günü",
    "Yasal Aile", "Muafiyet Aile", "Maktu Aile",
    "Yasal Çocuk", "Muafiyet Çocuk", "Maktu Çocuk Birim",
    "Vardiya Hesap", "Vardiya Mod", "Vardiya Değer",
    "Gece Hesap", "Gece Mod", "Gece Değer",
    "Ek Özel Tip", "Ek Özel Mod", "Ek Özel Değer",
    "Denge Aktif", "Denge Oran",
    "Ana Maaş (Brüt)", "Sosyal Paket", "Toplam Maliyet"
]

# --- KULLANICI VERİTABANI ---
def get_users():
    try:
        return st.secrets["users"]
    except Exception:
        return {}

# --- GÜVENLİK PANELİ ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
        st.session_state["active_user"] = None
    if st.session_state["password_correct"]:
        return True

    st.markdown("<h2 style='text-align: center;'>🔐 Petrol-İş TİS Servisi Giriş</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        user_id = st.text_input("Kullanıcı ID")
        password = st.text_input("Şifre", type="password")
        if st.button("Sisteme Giriş Yap"):
            users = get_users()
            if user_id in users and password == users[user_id]["sifre"]:
                st.session_state["password_correct"] = True
                st.session_state["active_user"] = users[user_id]["isim"]
                st.rerun()
            else:
                st.error("❌ Geçersiz Kullanıcı ID veya Şifre!")
    return False

if not check_password():
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👤 Uzman: **{st.session_state['active_user']}**")
    if st.button("Güvenli Çıkış"):
        korunan = {"password_correct", "active_user"}
        for key in list(st.session_state.keys()):
            if key not in korunan:
                del st.session_state[key]
        st.session_state["password_correct"] = False
        st.rerun()
    st.divider()
    st.header("⚙️ Genel Ayarlar")

    asgari_ucret_limit = st.number_input("Güncel Asgari Ücret (Brüt)", value=33030.00)

    oran_etiketleri = {
        0.71491: "%15 Vergi Dilimi",
        0.67241: "%20 Vergi Dilimi",
        0.61291: "%27 Vergi Dilimi",
        0.54491: "%35 Vergi Dilimi"
    }
    secilen_oran = st.radio(
        "📉 Vergi Dilimi Seçimi",
        options=list(oran_etiketleri.keys()),
        format_func=lambda x: oran_etiketleri[x],
        index=1
    )

    st.subheader("⚖️ Yasal Yardımlar (Aylık)")
    aile_yasal_sabit = st.number_input("657 S.K. Aile Yardımı", value=3154.63)
    cocuk_0_6_yasal = st.number_input("657 S.K. Çocuk (0-6)", value=693.94)
    cocuk_6_ustu_yasal = st.number_input("657 S.K. Çocuk (6+)", value=346.97)

    muafiyet_aile = asgari_ucret_limit * 0.10
    muafiyet_cocuk = (asgari_ucret_limit * 0.02) * 2

    st.info(f"Otomatik Muafiyetler:\n- Aile: {muafiyet_aile:,.2f} TL\n- Çocuk (2): {muafiyet_cocuk:,.2f} TL")

# --- HESAPLAMA FONKSİYONLARI ---
def calc_hybrid(val, mode, daily_base):
    if mode == "Maktu":
        return val
    elif mode == "Katsayı (Gün)":
        return daily_base * val
    elif mode == "Yüzde (%)":
        return daily_base * 30 * (val / 100)
    return 0

def maas_brutlestir(tutar, tip, oran):
    sabitler = {0.71491: 4462.03, 0.67241: 4788.45, 0.61291: 5865.80, 0.54491: 5865.80}
    if tip == "Brüt":
        return tutar
    return (tutar - sabitler.get(oran, 5865.80)) / oran

def yardim_brutlestir(tutar, tip, oran):
    if tip == "Brüt":
        return tutar
    return tutar / oran

# --- GOOGLE SHEETS BAĞLANTISI ---
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    s = st.secrets["connections"]["gsheets"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(s), scope)
    client = gspread.authorize(creds)
    return client.open_by_key("1kb6ceU5NjBNl1PB3vCspw90s8lYRVU7XVbMt97tfEbg").sheet1

def verileri_yukle_ve_getir():
    try:
        sheet = get_sheet()
        data = sheet.get_all_records(head=1)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Veritabanına bağlanılamadı: {e}")
        return pd.DataFrame()

def sheets_basliklarini_guncelle():
    """Sheets'in ilk satırını SHEET_HEADERS ile eşleştir."""
    try:
        sheet = get_sheet()
        mevcut = sheet.row_values(1)
        if mevcut != SHEET_HEADERS:
            sheet.delete_rows(1)
            sheet.insert_row(SHEET_HEADERS, 1)
    except Exception as e:
        st.warning(f"Başlık güncellenemedi: {e}")

# --- SESSION STATE VARSAYILANLARI ---
def ss_default(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

ss_default("ss_isyeri_adi", "")
ss_default("ss_subeler", [])
ss_default("ss_tis_bas", datetime.now().date())
ss_default("ss_tis_bit", datetime.now().replace(year=datetime.now().year + 2).date())
ss_default("ss_uye_sayisi", 0)
ss_default("ss_toplam_calisan", 0)
ss_default("ss_grev_yasagi", "Grev Yasağı Yok")
# Tab 1 alanları
ss_default("ss_u_tipi", "Net")
ss_default("ss_u_tutar", 20000.0)
ss_default("ss_ek1_mod", "Maktu")
ss_default("ss_ek1_val", 0.0)
ss_default("ss_ek1_per", "Aylık")
ss_default("ss_ek2_mod", "Maktu")
ss_default("ss_ek2_val", 0.0)
ss_default("ss_ek2_per", "Aylık")
ss_default("ss_gida_tip", "Net")
ss_default("ss_gida_val", 0.0)
ss_default("ss_yakacak_tip", "Net")
ss_default("ss_yakacak_val", 0.0)
ss_default("ss_giyim_tip", "Net")
ss_default("ss_giyim_val", 0.0)
ss_default("ss_ayakkabi_tip", "Net")
ss_default("ss_ayakkabi_val", 0.0)
ss_default("ss_yilbasi_tip", "Net")
ss_default("ss_yilbasi_val", 0.0)
ss_default("ss_iz_m", "Maktu")
ss_default("ss_iz_t", "Net")
ss_default("ss_iz_v", 0.0)
ss_default("ss_ba_m", "Maktu")
ss_default("ss_ba_t", "Net")
ss_default("ss_ba_v", 0.0)
ss_default("ss_pr_m", "Maktu")
ss_default("ss_pr_t", "Net")
ss_default("ss_pr_v", 0.0)
ss_default("ss_ikramiye", 0)
ss_default("ss_yasal_aile", False)
ss_default("ss_muafiyet_aile_tik", False)
ss_default("ss_maktu_aile", 0.0)
ss_default("ss_yasal_cocuk_tik", False)
ss_default("ss_muafiyet_cocuk_tik", False)
ss_default("ss_maktu_cocuk_birim", 0.0)
ss_default("ss_v_hesap", "Sabit")
ss_default("ss_v_mod", "Maktu")
ss_default("ss_v_val", 0.0)
ss_default("ss_g_hesap", "Sabit")
ss_default("ss_g_mod", "Maktu")
ss_default("ss_g_val", 0.0)
ss_default("ss_eo_tip", "Günlük Ücret")
ss_default("ss_eo_mod", "Katsayı")
ss_default("ss_eo_val", 0.0)
ss_default("ss_denge_aktif", False)
ss_default("ss_denge_oran", 11.0)

# --- SEKME YAPISI ---
tab1, tab2 = st.tabs(["💰 Ücret ve Sosyal Ödemeler", "🏢 İşyeri Bilgileri"])

# -------------------------------------------------------
# TAB 2 — İşyeri Bilgileri
# -------------------------------------------------------
with tab2:
    st.header("🏢 İşyeri ve Şube Bilgileri")

    df = verileri_yukle_ve_getir()

    if st.button("➕ Yeni Kayıt Başlat"):
        korunan = {"password_correct", "active_user"}
        for key in list(st.session_state.keys()):
            if key not in korunan:
                del st.session_state[key]
        # ss_ anahtarlarını varsayılan değerlere sıfırla
        st.session_state["ss_isyeri_adi"] = ""
        st.session_state["ss_subeler"] = []
        st.session_state["ss_tis_bas"] = datetime.now().date()
        st.session_state["ss_tis_bit"] = datetime.now().replace(year=datetime.now().year + 2).date()
        st.session_state["ss_uye_sayisi"] = 0
        st.session_state["ss_toplam_calisan"] = 0
        st.session_state["ss_grev_yasagi"] = "Grev Yasağı Yok"
        st.session_state["ss_u_tipi"] = "Net"
        st.session_state["ss_u_tutar"] = 20000.0
        st.session_state["ss_ek1_mod"] = "Maktu"
        st.session_state["ss_ek1_val"] = 0.0
        st.session_state["ss_ek1_per"] = "Aylık"
        st.session_state["ss_ek2_mod"] = "Maktu"
        st.session_state["ss_ek2_val"] = 0.0
        st.session_state["ss_ek2_per"] = "Aylık"
        st.session_state["ss_gida_tip"] = "Net"
        st.session_state["ss_gida_val"] = 0.0
        st.session_state["ss_yakacak_tip"] = "Net"
        st.session_state["ss_yakacak_val"] = 0.0
        st.session_state["ss_giyim_tip"] = "Net"
        st.session_state["ss_giyim_val"] = 0.0
        st.session_state["ss_ayakkabi_tip"] = "Net"
        st.session_state["ss_ayakkabi_val"] = 0.0
        st.session_state["ss_yilbasi_tip"] = "Net"
        st.session_state["ss_yilbasi_val"] = 0.0
        st.session_state["ss_iz_m"] = "Maktu"
        st.session_state["ss_iz_t"] = "Net"
        st.session_state["ss_iz_v"] = 0.0
        st.session_state["ss_ba_m"] = "Maktu"
        st.session_state["ss_ba_t"] = "Net"
        st.session_state["ss_ba_v"] = 0.0
        st.session_state["ss_pr_m"] = "Maktu"
        st.session_state["ss_pr_t"] = "Net"
        st.session_state["ss_pr_v"] = 0.0
        st.session_state["ss_ikramiye"] = 0
        st.session_state["ss_yasal_aile"] = False
        st.session_state["ss_muafiyet_aile_tik"] = False
        st.session_state["ss_maktu_aile"] = 0.0
        st.session_state["ss_yasal_cocuk_tik"] = False
        st.session_state["ss_muafiyet_cocuk_tik"] = False
        st.session_state["ss_maktu_cocuk_birim"] = 0.0
        st.session_state["ss_v_hesap"] = "Sabit"
        st.session_state["ss_v_mod"] = "Maktu"
        st.session_state["ss_v_val"] = 0.0
        st.session_state["ss_g_hesap"] = "Sabit"
        st.session_state["ss_g_mod"] = "Maktu"
        st.session_state["ss_g_val"] = 0.0
        st.session_state["ss_eo_tip"] = "Günlük Ücret"
        st.session_state["ss_eo_mod"] = "Katsayı"
        st.session_state["ss_eo_val"] = 0.0
        st.session_state["ss_denge_aktif"] = False
        st.session_state["ss_denge_oran"] = 11.0
        # Widget key'lerini de sıfırla
        st.session_state["isyeri_kutusu"] = ""
        st.session_state["calisan_sayisi_kutusu"] = 0
        st.session_state["ek1_mod"] = "Maktu"
        st.session_state["ek1_val"] = 0.0
        st.session_state["ek1_per"] = "Aylık"
        st.session_state["ek2_mod"] = "Maktu"
        st.session_state["ek2_val"] = 0.0
        st.session_state["ek2_per"] = "Aylık"
        st.session_state["v_h"] = "Sabit"
        st.session_state["v_m"] = "Maktu"
        st.session_state["v_v"] = 0.0
        st.session_state["g_h"] = "Sabit"
        st.session_state["g_m"] = "Maktu"
        st.session_state["g_v"] = 0.0
        st.session_state["eo_t"] = "Günlük Ücret"
        st.session_state["eo_m"] = "Katsayı"
        st.session_state["eo_v"] = 0.0
        st.rerun()

    with st.expander("📂 Kayıtlı Veriyi Çağır", expanded=True):
        if not df.empty:
            isyeri_listesi = df["İşyeri"].unique().tolist()
            secilen_isyeri = st.selectbox("Güncellenecek İşyerini Seçin", isyeri_listesi)

            if st.button("Verileri Seçili İşyeri İçin Yükle"):
                r = df[df["İşyeri"] == secilen_isyeri].iloc[0]

                def rv(col, default=""):
                    val = r.get(col, default)
                    return val if (val != "" and val is not None) else default

                def rf(col, default=0.0):
                    """Sheets'ten Türkçe formatlı sayıyı float'a çevirir (86188,68 → 86188.68)."""
                    try:
                        val = str(r.get(col, "")).strip()
                        if val == "" or val == "None":
                            return float(default)
                        if "," in val and "." in val:
                            # "86.188,68" → binlik nokta, ondalık virgül
                            val = val.replace(".", "").replace(",", ".")
                        elif "," in val:
                            # "86188,68" → sadece ondalık virgül
                            val = val.replace(",", ".")
                        return float(val)
                    except Exception:
                        return float(default)

                def ri(col, default=0):
                    try:
                        val = str(r.get(col, "")).strip()
                        if val == "" or val == "None":
                            return int(default)
                        return int(float(val))
                    except Exception:
                        return int(default)

                # Tab 2 alanları
                st.session_state["isyeri_kutusu"] = rv("İşyeri")
                st.session_state["calisan_sayisi_kutusu"] = ri("Toplam Çalışan")
                st.session_state["ss_isyeri_adi"] = rv("İşyeri")
                st.session_state["ss_toplam_calisan"] = ri("Toplam Çalışan")
                st.session_state["ss_uye_sayisi"] = ri("Üye Sayısı")
                st.session_state["ss_grev_yasagi"] = rv("Grev Durumu", "Grev Yasağı Yok")
                try:
                    bas_str = rv("TİS Başlangıç")
                    bit_str = rv("TİS Bitiş")
                    if bas_str:
                        st.session_state["ss_tis_bas"] = datetime.strptime(bas_str, "%d/%m/%Y").date()
                    if bit_str:
                        st.session_state["ss_tis_bit"] = datetime.strptime(bit_str, "%d/%m/%Y").date()
                except Exception:
                    pass
                try:
                    subeler_str = rv("Şubeler", "")
                    st.session_state["ss_subeler"] = [s.strip() for s in subeler_str.split(",") if s.strip()]
                except Exception:
                    pass

                # Tab 1 alanları
                st.session_state["ss_u_tipi"] = rv("Ana Maaş Tipi", "Net")
                st.session_state["ss_u_tutar"] = rf("Ana Maaş Tutar", 20000.0)
                st.session_state["ss_ek1_mod"] = rv("Ek Ödeme 1 Mod", "Maktu")
                st.session_state["ss_ek1_val"] = rf("Ek Ödeme 1 Değer")
                st.session_state["ss_ek1_per"] = rv("Ek Ödeme 1 Periyot", "Aylık")
                st.session_state["ss_ek2_mod"] = rv("Ek Ödeme 2 Mod", "Maktu")
                st.session_state["ss_ek2_val"] = rf("Ek Ödeme 2 Değer")
                st.session_state["ss_ek2_per"] = rv("Ek Ödeme 2 Periyot", "Aylık")
                st.session_state["ss_gida_tip"] = rv("Gıda Tip", "Net")
                st.session_state["ss_gida_val"] = rf("Gıda Tutar")
                st.session_state["ss_yakacak_tip"] = rv("Yakacak Tip", "Net")
                st.session_state["ss_yakacak_val"] = rf("Yakacak Tutar")
                st.session_state["ss_giyim_tip"] = rv("Giyim Tip", "Net")
                st.session_state["ss_giyim_val"] = rf("Giyim Tutar")
                st.session_state["ss_ayakkabi_tip"] = rv("Ayakkabı Tip", "Net")
                st.session_state["ss_ayakkabi_val"] = rf("Ayakkabı Tutar")
                st.session_state["ss_yilbasi_tip"] = rv("Yılbaşı Tip", "Net")
                st.session_state["ss_yilbasi_val"] = rf("Yılbaşı Tutar")
                st.session_state["ss_iz_m"] = rv("İzin Mod", "Maktu")
                st.session_state["ss_iz_t"] = rv("İzin Tip", "Net")
                st.session_state["ss_iz_v"] = rf("İzin Değer")
                st.session_state["ss_ba_m"] = rv("Bayram Mod", "Maktu")
                st.session_state["ss_ba_t"] = rv("Bayram Tip", "Net")
                st.session_state["ss_ba_v"] = rf("Bayram Değer")
                st.session_state["ss_pr_m"] = rv("Prim Mod", "Maktu")
                st.session_state["ss_pr_t"] = rv("Prim Tip", "Net")
                st.session_state["ss_pr_v"] = rf("Prim Değer")
                st.session_state["ss_ikramiye"] = ri("İkramiye Günü")
                st.session_state["ss_yasal_aile"] = rv("Yasal Aile", "False") == "True"
                st.session_state["ss_muafiyet_aile_tik"] = rv("Muafiyet Aile", "False") == "True"
                st.session_state["ss_maktu_aile"] = rf("Maktu Aile")
                st.session_state["ss_yasal_cocuk_tik"] = rv("Yasal Çocuk", "False") == "True"
                st.session_state["ss_muafiyet_cocuk_tik"] = rv("Muafiyet Çocuk", "False") == "True"
                st.session_state["ss_maktu_cocuk_birim"] = rf("Maktu Çocuk Birim")
                st.session_state["ss_v_hesap"] = rv("Vardiya Hesap", "Sabit")
                st.session_state["ss_v_mod"] = rv("Vardiya Mod", "Maktu")
                st.session_state["ss_v_val"] = rf("Vardiya Değer")
                st.session_state["ss_g_hesap"] = rv("Gece Hesap", "Sabit")
                st.session_state["ss_g_mod"] = rv("Gece Mod", "Maktu")
                st.session_state["ss_g_val"] = rf("Gece Değer")
                st.session_state["ss_eo_tip"] = rv("Ek Özel Tip", "Günlük Ücret")
                st.session_state["ss_eo_mod"] = rv("Ek Özel Mod", "Katsayı")
                st.session_state["ss_eo_val"] = rf("Ek Özel Değer")
                st.session_state["ss_denge_aktif"] = rv("Denge Aktif", "False") == "True"
                st.session_state["ss_denge_oran"] = rf("Denge Oran", 11.0)

                st.success(f"✅ {secilen_isyeri} verileri yüklendi! Tab 1'e geçerek kontrol edebilirsiniz.")

        st.divider()
        st.subheader("📋 Kayıtlı TİS Verileri")
        if not df.empty:
            goster_sutunlar = [c for c in ["İşyeri", "TİS Başlangıç", "TİS Bitiş", "Toplam Maliyet"] if c in df.columns]
            st.dataframe(df[goster_sutunlar], use_container_width=True)
        else:
            st.info("Henüz veritabanında kayıtlı bir TİS dosyası yok.")

    st.divider()
    col_is1, col_is2 = st.columns(2)
    with col_is1:
        isyeri_adi = st.text_input("İşyeri Tam Adı", key="isyeri_kutusu")
        subeler = st.multiselect(
            "Bağlı Olduğu Şubeler",
            ["Adana", "Adıyaman", "Ankara", "Bandırma", "Batman", "Bursa", "Ceyhan",
             "Çankırı", "Gebze", "İstanbul 1", "İstanbul 2", "İzmir", "Kırıkkale",
             "Kocaeli", "Mersin", "Trakya", "Aliağa"],
            default=st.session_state["ss_subeler"]
        )

        st.divider()
        st.subheader("📅 Sözleşme Dönemi")
        tis_baslangic = st.date_input("Yürürlük Başlangıç Tarihi", value=st.session_state["ss_tis_bas"])
        tis_bitis = st.date_input("Yürürlük Bitiş Tarihi", value=st.session_state["ss_tis_bit"])

        # session_state güncelle
        st.session_state["ss_isyeri_adi"] = isyeri_adi
        st.session_state["ss_subeler"] = subeler
        st.session_state["ss_tis_bas"] = tis_baslangic.date() if hasattr(tis_baslangic, 'date') else tis_baslangic
        st.session_state["ss_tis_bit"] = tis_bitis.date() if hasattr(tis_bitis, 'date') else tis_bitis

        st.divider()
        st.subheader("📊 Sözleşme İlerleme Durumu")
        bugun = datetime.now().date()
        toplam_sure_gun = (tis_bitis - tis_baslangic).days
        kalan_sure_gun = max((tis_bitis - bugun).days, 0)
        yuzde = min(max(((toplam_sure_gun - kalan_sure_gun) / toplam_sure_gun) * 100, 0), 100) if toplam_sure_gun > 0 else 0
        st.progress(yuzde / 100)
        st.write(f"**Kalan Süre:** {kalan_sure_gun} Gün")

        if kalan_sure_gun <= 0:
            st.error("❌ Sözleşme süresi dolmuştur!")
        elif kalan_sure_gun <= 120:
            st.error("🚨 YETKİ BAŞVURU SÜRESİ BAŞLADI!")
        elif kalan_sure_gun <= 365:
            st.warning("⚠️ Sözleşmenin son yılındasınız. Hazırlık sürecini başlatın.")
        else:
            st.success("✅ Sözleşme süreci normal takviminde ilerliyor.")

        bas_date = tis_baslangic.date() if hasattr(tis_baslangic, 'date') else tis_baslangic
        bit_date = tis_bitis.date() if hasattr(tis_bitis, 'date') else tis_bitis
        fark_gun = (bit_date - bas_date).days + 1

        if fark_gun < 365:
            st.warning(f"⚠️ TİS kanunen 1 yıldan az olamaz. (Tespit edilen: {fark_gun} gün)")
        elif fark_gun > 1095:
            st.error("❌ TİS kanunen 3 yıldan fazla olamaz.")
        else:
            yil_hesabi = round(fark_gun / 365, 1)
            st.success(f"✅ Sözleşme Süresi: {yil_hesabi} Yıl ({fark_gun} Gün)")

    with col_is2:
        toplam_calisan = st.number_input("Toplam Çalışan Sayısı", value=st.session_state["ss_toplam_calisan"], key="calisan_sayisi_kutusu")
        uye_sayisi = st.number_input("Sendikalı Üye Sayısı", value=st.session_state["ss_uye_sayisi"])
        grev_idx = ["Grev Yasağı Yok", "Grev Yasağı Var"].index(st.session_state["ss_grev_yasagi"]) if st.session_state["ss_grev_yasagi"] in ["Grev Yasağı Yok", "Grev Yasağı Var"] else 0
        grev_yasagi = st.selectbox("Grev Yasağı Durumu", ["Grev Yasağı Yok", "Grev Yasağı Var"], index=grev_idx)

        st.session_state["ss_uye_sayisi"] = uye_sayisi
        st.session_state["ss_grev_yasagi"] = grev_yasagi
        st.session_state["ss_toplam_calisan"] = toplam_calisan

# -------------------------------------------------------
# TAB 1 — Ücret ve Sosyal Ödemeler
# -------------------------------------------------------
with tab1:
    _isyeri_adi  = st.session_state["ss_isyeri_adi"]
    _subeler     = st.session_state["ss_subeler"]
    _tis_bas     = st.session_state["ss_tis_bas"]
    _tis_bit     = st.session_state["ss_tis_bit"]
    _uye_sayisi  = st.session_state["ss_uye_sayisi"]
    _grev_yasagi = st.session_state["ss_grev_yasagi"]

    st.header("💵 Ücret ve Ek Ödemeler")
    c1, c2, c3 = st.columns(3)
    with c1:
        u_tipi = st.radio("Ücret Tipi", ["Net", "Brüt"],
                          index=["Net", "Brüt"].index(st.session_state["ss_u_tipi"]))
        u_tutar = st.number_input("Çıplak Ücret Tutarı", value=st.session_state["ss_u_tutar"])
    with c2:
        st.info("Ek Ödeme 1")
        ek_mod = st.selectbox("Hesaplama Modu", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"],
                              index=["Maktu", "Katsayı (Gün)", "Yüzde (%)"].index(st.session_state["ss_ek1_mod"]),
                              key="ek1_mod")
        ek_val = st.number_input("Değer", value=st.session_state["ss_ek1_val"], key="ek1_val")
        ek_per = st.selectbox("Periyot", ["Aylık", "Yıllık"],
                              index=["Aylık", "Yıllık"].index(st.session_state["ss_ek1_per"]),
                              key="ek1_per")
    with c3:
        st.info("Ek Ödeme 2")
        ek2_mod = st.selectbox("Hesaplama Modu", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"],
                               index=["Maktu", "Katsayı (Gün)", "Yüzde (%)"].index(st.session_state["ss_ek2_mod"]),
                               key="ek2_mod")
        ek2_val = st.number_input("Değer", value=st.session_state["ss_ek2_val"], key="ek2_val")
        ek2_per = st.selectbox("Periyot", ["Aylık", "Yıllık"],
                               index=["Aylık", "Yıllık"].index(st.session_state["ss_ek2_per"]),
                               key="ek2_per")

    a_brut = maas_brutlestir(u_tutar, u_tipi, secilen_oran)
    g_brut = a_brut / 30

    st.markdown("### 🎁 Sosyal Yardımlar")

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        with st.container(border=True):
            st.write("🍞 **Gıda Yardımı (Aylık)**")
            g_tip = st.radio("Gıda Tip", ["Net", "Brüt"], horizontal=True,
                             index=["Net", "Brüt"].index(st.session_state["ss_gida_tip"]))
            g_val = st.number_input("Gıda Tutarı", value=st.session_state["ss_gida_val"])
            gida = yardim_brutlestir(g_val, g_tip, secilen_oran)
    with col_s2:
        with st.container(border=True):
            st.write("🔥 **Yakacak Yardımı (Aylık)**")
            y_tip = st.radio("Yakacak Tip", ["Net", "Brüt"], horizontal=True,
                             index=["Net", "Brüt"].index(st.session_state["ss_yakacak_tip"]))
            y_val = st.number_input("Yakacak Tutarı", value=st.session_state["ss_yakacak_val"])
            yakacak = yardim_brutlestir(y_val, y_tip, secilen_oran)

    col_s3, col_s4, col_s5 = st.columns(3)
    with col_s3:
        with st.container(border=True):
            st.write("👕 **Giyim (Yıllık)**")
            giy_tip = st.radio("Giyim Tip", ["Net", "Brüt"], horizontal=True,
                               index=["Net", "Brüt"].index(st.session_state["ss_giyim_tip"]))
            giyim = yardim_brutlestir(st.number_input("Giyim Tutar", value=st.session_state["ss_giyim_val"]), giy_tip, secilen_oran)
    with col_s4:
        with st.container(border=True):
            st.write("👟 **Ayakkabı (Yıllık)**")
            ayk_tip = st.radio("Ayakkabı Tip", ["Net", "Brüt"], horizontal=True,
                               index=["Net", "Brüt"].index(st.session_state["ss_ayakkabi_tip"]))
            ayakkabi = yardim_brutlestir(st.number_input("Ayakkabı Tutar", value=st.session_state["ss_ayakkabi_val"]), ayk_tip, secilen_oran)
    with col_s5:
        with st.container(border=True):
            st.write("🎁 **Yılbaşı (Yıllık)**")
            yil_tip = st.radio("Yılbaşı Tip", ["Net", "Brüt"], horizontal=True,
                               index=["Net", "Brüt"].index(st.session_state["ss_yilbasi_tip"]))
            yilbasi = yardim_brutlestir(st.number_input("Yılbaşı Tutar", value=st.session_state["ss_yilbasi_val"]), yil_tip, secilen_oran)

    col_s6, col_s7, col_s8 = st.columns(3)
    with col_s6:
        with st.container(border=True):
            st.write("📅 **İzin Parası (Yıllık)**")
            iz_m = st.selectbox("İzin Mod", ["Maktu", "Katsayı (Gün)"],
                                index=["Maktu", "Katsayı (Gün)"].index(st.session_state["ss_iz_m"]))
            iz_t = st.radio("İzin Tip", ["Net", "Brüt"], horizontal=True,
                            index=["Net", "Brüt"].index(st.session_state["ss_iz_t"]))
            iz_v = st.number_input("İzin Değer", value=st.session_state["ss_iz_v"])
            ay_izin = yardim_brutlestir(calc_hybrid(iz_v, iz_m, g_brut), iz_t, secilen_oran) / 12
    with col_s7:
        with st.container(border=True):
            st.write("🎉 **Bayram Yardımı (Yıllık)**")
            ba_m = st.selectbox("Bayram Mod", ["Maktu", "Katsayı (Gün)"],
                                index=["Maktu", "Katsayı (Gün)"].index(st.session_state["ss_ba_m"]))
            ba_t = st.radio("Bayram Tip", ["Net", "Brüt"], horizontal=True,
                            index=["Net", "Brüt"].index(st.session_state["ss_ba_t"]))
            ba_v = st.number_input("Bayram Değer", value=st.session_state["ss_ba_v"])
            ay_bayram = yardim_brutlestir(calc_hybrid(ba_v, ba_m, g_brut), ba_t, secilen_oran) / 12
    with col_s8:
        with st.container(border=True):
            st.write("🏆 **Prim Ödemesi**")
            pr_m = st.selectbox("Prim Mod", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"],
                                index=["Maktu", "Katsayı (Gün)", "Yüzde (%)"].index(st.session_state["ss_pr_m"]))
            pr_t = st.radio("Prim Tip", ["Net", "Brüt"], horizontal=True,
                            index=["Net", "Brüt"].index(st.session_state["ss_pr_t"]))
            pr_v = st.number_input("Prim Değer", value=st.session_state["ss_pr_v"])
            ay_prim = yardim_brutlestir(calc_hybrid(pr_v, pr_m, g_brut), pr_t, secilen_oran)

    with st.container(border=True):
        ikramiye = st.number_input("💰 Yıllık Toplam İkramiye Günü", value=st.session_state["ss_ikramiye"])
        ay_ikramiye = (g_brut * ikramiye) / 12

    with st.container(border=True):
        st.write("👨‍👩‍👧‍👦 **Aile & Çocuk Yardımı**")
        col_ac1, col_ac2 = st.columns(2)
        with col_ac1:
            yasal_aile = st.checkbox("657 Aile Yardımı", value=st.session_state["ss_yasal_aile"])
            muafiyet_aile_tik = st.checkbox("Muafiyet Aile", value=st.session_state["ss_muafiyet_aile_tik"])
            maktu_aile = st.number_input("Maktu Aile", value=st.session_state["ss_maktu_aile"])
        with col_ac2:
            yasal_cocuk_tik = st.checkbox("657 Çocuk Yardımı", value=st.session_state["ss_yasal_cocuk_tik"])
            muafiyet_cocuk_tik = st.checkbox("Muafiyet Çocuk", value=st.session_state["ss_muafiyet_cocuk_tik"])
            maktu_cocuk_birim = st.number_input("Maktu Çocuk (Birim)", value=st.session_state["ss_maktu_cocuk_birim"])

    st.divider()
    st.markdown("### ⚡ Özel Ödemeler (Vardiya, Gece ve Ek)")
    v1, v2, v3 = st.columns(3)
    with v1:
        with st.container(border=True):
            st.write("🔄 **Vardiya Zammı**")
            v_hesap_tipi = st.selectbox("Hesaplama Türü", ["Sabit", "Fiili (195/225)"],
                                        index=["Sabit", "Fiili (195/225)"].index(st.session_state["ss_v_hesap"]),
                                        key="v_h")
            v_mod = st.selectbox("Birim", ["Maktu", "Yüzde (%)"],
                                 index=["Maktu", "Yüzde (%)"].index(st.session_state["ss_v_mod"]),
                                 key="v_m")
            v_val = st.number_input("Miktar", value=st.session_state["ss_v_val"], key="v_v")
    with v2:
        with st.container(border=True):
            st.write("🌙 **Gece Zammı**")
            g_hesap_tipi = st.selectbox("Hesaplama Türü", ["Sabit", "Fiili (80/225)"],
                                        index=["Sabit", "Fiili (80/225)"].index(st.session_state["ss_g_hesap"]),
                                        key="g_h")
            g_mod = st.selectbox("Birim", ["Maktu", "Yüzde (%)"],
                                 index=["Maktu", "Yüzde (%)"].index(st.session_state["ss_g_mod"]),
                                 key="g_m")
            g_val = st.number_input("Miktar", value=st.session_state["ss_g_val"], key="g_v")
    with v3:
        with st.container(border=True):
            st.write("➕ **Ücrete Bağlı Ek Özel**")
            ek_ozel_tip = st.selectbox("Baz Alınacak Ücret", ["Günlük Ücret", "Aylık Ücret"],
                                       index=["Günlük Ücret", "Aylık Ücret"].index(st.session_state["ss_eo_tip"]),
                                       key="eo_t")
            ek_ozel_mod = st.selectbox("Birim", ["Katsayı", "Yüzde (%)"],
                                       index=["Katsayı", "Yüzde (%)"].index(st.session_state["ss_eo_mod"]),
                                       key="eo_m")
            ek_ozel_val = st.number_input("Miktar", value=st.session_state["ss_eo_val"], key="eo_v")

    # --- FİNAL HESAPLAMALAR ---
    ay_ek1 = calc_hybrid(ek_val, ek_mod, g_brut) if ek_per == "Aylık" else calc_hybrid(ek_val, ek_mod, g_brut) / 12
    ay_ek2 = calc_hybrid(ek2_val, ek2_mod, g_brut) if ek2_per == "Aylık" else calc_hybrid(ek2_val, ek2_mod, g_brut) / 12

    sabit_cocuk_sayisi = 2
    yasal_aile_tutar = aile_yasal_sabit if yasal_aile else 0
    muafiyet_aile_tutar = muafiyet_aile if muafiyet_aile_tik else 0
    yasal_cocuk_tutar = (cocuk_6_ustu_yasal * sabit_cocuk_sayisi) if yasal_cocuk_tik else 0
    muafiyet_cocuk_tutar = muafiyet_cocuk if muafiyet_cocuk_tik else 0
    maktu_cocuk_toplam = maktu_cocuk_birim * sabit_cocuk_sayisi
    ay_aile_cocuk_paketi = (
        yasal_aile_tutar + muafiyet_aile_tutar + maktu_aile +
        yasal_cocuk_tutar + muafiyet_cocuk_tutar + maktu_cocuk_toplam
    )

    v_tutar = calc_hybrid(v_val, v_mod, g_brut)
    if v_hesap_tipi == "Fiili (195/225)":
        v_tutar = (v_tutar * 195) / 225
    g_tutar = calc_hybrid(g_val, g_mod, g_brut)
    if g_hesap_tipi == "Fiili (80/225)":
        g_tutar = (g_tutar * 80) / 225

    if ek_ozel_tip == "Günlük Ücret":
        ay_ek_ozel = g_brut * (ek_ozel_val if ek_ozel_mod == "Katsayı" else ek_ozel_val / 100)
    else:
        ay_ek_ozel = a_brut * (ek_ozel_val if ek_ozel_mod == "Katsayı" else ek_ozel_val / 100)

    st.markdown("### 📈 Ücrete Bağlı Ek Ödemeler (Denge Ödentisi)")
    with st.container(border=True):
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            denge_aktif = st.checkbox("Denge Ödentisi Uygula", value=st.session_state["ss_denge_aktif"])
            denge_oran = st.number_input("Denge Ödentisi Oranı (%)", value=st.session_state["ss_denge_oran"]) / 100
        with col_d2:
            st.write("Hesaplanacak Baz:")
            st.caption("Ücret + İkramiye + Gece Z. + Vardiya Z.")

        if denge_aktif:
            baz_tutar = a_brut + ay_ikramiye + g_tutar + v_tutar
            ay_denge = baz_tutar * denge_oran
            st.metric("Hesaplanan Denge Ödentisi", f"{ay_denge:,.2f} TL")
        else:
            ay_denge = 0.0

    toplam_sosyal = (
        gida + yakacak + ay_izin + ay_bayram + ay_prim +
        (giyim + ayakkabi + yilbasi) / 12 +
        ay_ikramiye + ay_aile_cocuk_paketi +
        v_tutar + g_tutar + ay_ek_ozel + ay_denge
    )
    t_maliyet = a_brut + ay_ek1 + ay_ek2 + toplam_sosyal

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

    st.divider()
    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("💾 Veritabanına Kaydet"):
            try:
                sheet = get_sheet()
                # Başlıkları kontrol et ve gerekirse güncelle
                sheets_basliklarini_guncelle()

                _tis_bas_str = _tis_bas.strftime("%d/%m/%Y") if hasattr(_tis_bas, 'strftime') else str(_tis_bas)
                _tis_bit_str = _tis_bit.strftime("%d/%m/%Y") if hasattr(_tis_bit, 'strftime') else str(_tis_bit)

                kayit_row = [
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                    st.session_state["active_user"],
                    _isyeri_adi,
                    ", ".join(_subeler),
                    _tis_bas_str,
                    _tis_bit_str,
                    _uye_sayisi,
                    _grev_yasagi,
                    st.session_state["ss_toplam_calisan"],
                    u_tipi, u_tutar,
                    ek_mod, ek_val, ek_per,
                    ek2_mod, ek2_val, ek2_per,
                    g_tip, g_val,
                    y_tip, y_val,
                    giy_tip, st.session_state["ss_giyim_val"],
                    ayk_tip, st.session_state["ss_ayakkabi_val"],
                    yil_tip, st.session_state["ss_yilbasi_val"],
                    iz_m, iz_t, iz_v,
                    ba_m, ba_t, ba_v,
                    pr_m, pr_t, pr_v,
                    ikramiye,
                    str(yasal_aile), str(muafiyet_aile_tik), maktu_aile,
                    str(yasal_cocuk_tik), str(muafiyet_cocuk_tik), maktu_cocuk_birim,
                    v_hesap_tipi, v_mod, v_val,
                    g_hesap_tipi, g_mod, g_val,
                    ek_ozel_tip, ek_ozel_mod, ek_ozel_val,
                    str(denge_aktif), st.session_state["ss_denge_oran"],
                    f"{a_brut:.2f}",
                    f"{toplam_sosyal:.2f}",
                    f"{t_maliyet:.2f}"
                ]

                sheet.append_row(kayit_row)
                st.success("✅ Tüm veriler Google Sheets'e kaydedildi!")
                st.balloons()
            except Exception as e:
                st.error(f"Kayıt Hatası: {e}")

    with col_btn2:
        rapor_verisi = {
            "Parametre": [
                "İşlem Tarihi", "Uzman", "İşyeri", "Şubeler",
                "TİS Başlangıç", "TİS Bitiş", "Üye Sayısı", "Grev Durumu",
                "Ana Maaş (Brüt)", "Gıda Yardımı", "Yakacak Yardımı",
                "Giyim (Aylık)", "Ayakkabı (Aylık)", "Yılbaşı (Aylık)",
                "İzin Parası (Aylık)", "Bayram Yardımı (Aylık)",
                "Prim (Aylık)", "İkramiye (Aylık)",
                "Aile & Çocuk Paketi", "Vardiya Zammı",
                "Gece Zammı", "Özel Ek", "Denge Ödentisi",
                "Toplam Sosyal Paket", "Toplam Maliyet"
            ],
            "Değer": [
                datetime.now().strftime("%d/%m/%Y %H:%M"),
                st.session_state["active_user"],
                _isyeri_adi, ", ".join(_subeler),
                _tis_bas.strftime("%d/%m/%Y") if hasattr(_tis_bas, 'strftime') else str(_tis_bas),
                _tis_bit.strftime("%d/%m/%Y") if hasattr(_tis_bit, 'strftime') else str(_tis_bit),
                _uye_sayisi, _grev_yasagi,
                f"{a_brut:,.2f} TL", f"{gida:,.2f} TL", f"{yakacak:,.2f} TL",
                f"{giyim/12:,.2f} TL", f"{ayakkabi/12:,.2f} TL", f"{yilbasi/12:,.2f} TL",
                f"{ay_izin:,.2f} TL", f"{ay_bayram:,.2f} TL",
                f"{ay_prim:,.2f} TL", f"{ay_ikramiye:,.2f} TL",
                f"{ay_aile_cocuk_paketi:,.2f} TL", f"{v_tutar:,.2f} TL",
                f"{g_tutar:,.2f} TL", f"{ay_ek_ozel:,.2f} TL", f"{ay_denge:,.2f} TL",
                f"{toplam_sosyal:,.2f} TL", f"{t_maliyet:,.2f} TL"
            ]
        }
        rapor_df = pd.DataFrame(rapor_verisi)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            rapor_df.to_excel(writer, index=False, sheet_name='TİS_Detayli_Rapor')
            writer.sheets['TİS_Detayli_Rapor'].set_column('A:B', 30)

        st.download_button(
            label="📥 Detaylı Excel Raporu İndir",
            data=output.getvalue(),
            file_name=f"{_isyeri_adi}_TIS_Rapor_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
