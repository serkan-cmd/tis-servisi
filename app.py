import streamlit as st
import pandas as pd
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="Petrol-İş TİS Servisi v2.0", layout="wide")

# ============================================================
# SABITLER
# ============================================================
SUBELER = ["Adana", "Adıyaman", "Aliağa", "Ankara", "Bandırma", "Batman",
           "Bursa", "Çankırı", "Düzce", "Gebze", "İstanbul 1", "İstanbul 2",
           "İzmir", "Kırıkkale", "Kocaeli", "Mersin", "Trakya"]

SEKTORLER = ["Petrol", "Petrol Depolama", "Genel Kimya", "Boya", "Plastik",
             "Otomotiv Yan Sanayi", "Lastik", "Gübre", "İlaç", "Cam"]

ULKELER = ["Türkiye", "ABD", "Almanya", "Fransa", "İngiltere", "İtalya",
           "Japonya", "Hollanda", "İsviçre", "İsveç", "Avustralya",
           "Avusturya", "Belçika", "Kanada", "Azerbaycan", "Diğer"]

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

AY_MAP = {a: i+1 for i, a in enumerate(AYLAR)}

SHEET_KEY = "1kb6ceU5NjBNl1PB3vCspw90s8lYRVU7XVbMt97tfEbg"

SHEET_HEADERS = [
    "Kayıt Tarihi", "Uzman", "İşyeri", "İşyeri Tipi", "Grev Durumu",
    "Yabancı Ortak", "Ortak Ülke", "İşveren Sendikası", "Sektör", "Grup",
    "Şubeler", "Üye Sayısı", "Toplam Çalışan",
    "TİS Başlangıç", "TİS Bitiş", "Zam Planı Özeti",
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

# ============================================================
# KULLANICI YÖNETİMİ
# ============================================================
def get_users():
    try:
        return st.secrets["users"]
    except Exception:
        return {}

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
        st.session_state["active_user"] = None
    if st.session_state["password_correct"]:
        return True
    st.markdown("<h2 style='text-align:center'>🔐 Petrol-İş TİS Servisi</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        uid = st.text_input("Kullanıcı ID")
        pwd = st.text_input("Şifre", type="password")
        if st.button("Giriş Yap"):
            users = get_users()
            if uid in users and pwd == users[uid]["sifre"]:
                st.session_state["password_correct"] = True
                st.session_state["active_user"] = users[uid]["isim"]
                st.rerun()
            else:
                st.error("❌ Geçersiz kullanıcı adı veya şifre!")
    return False

if not check_password():
    st.stop()

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown(f"### 👤 {st.session_state['active_user']}")
    if st.button("🚪 Güvenli Çıkış"):
        for k in list(st.session_state.keys()):
            if k not in {"password_correct", "active_user"}:
                del st.session_state[k]
        st.session_state["password_correct"] = False
        st.rerun()

    st.divider()
    st.header("⚙️ Genel Ayarlar")
    asgari_ucret = st.number_input("Asgari Ücret (Brüt)", value=33030.00)

    oran_map = {
        0.71491: "%15 Vergi Dilimi",
        0.67241: "%20 Vergi Dilimi",
        0.61291: "%27 Vergi Dilimi",
        0.54491: "%35 Vergi Dilimi"
    }
    secilen_oran = st.radio("📉 Vergi Dilimi",
                            options=list(oran_map.keys()),
                            format_func=lambda x: oran_map[x],
                            index=1)

    st.subheader("⚖️ Yasal Yardımlar")
    aile_yasal_sabit = st.number_input("657 Aile Yardımı", value=3154.63)
    cocuk_6_ustu = st.number_input("657 Çocuk (6+)", value=346.97)
    cocuk_0_6 = st.number_input("657 Çocuk (0-6)", value=693.94)
    muafiyet_aile = asgari_ucret * 0.10
    muafiyet_cocuk = (asgari_ucret * 0.02) * 2
    st.info(f"Muafiyet Aile: {muafiyet_aile:,.2f} TL\nMuafiyet Çocuk(2): {muafiyet_cocuk:,.2f} TL")

# ============================================================
# HESAPLAMA FONKSİYONLARI
# ============================================================
def calc_hybrid(val, mode, daily_base):
    if mode == "Maktu": return val
    elif mode == "Katsayı (Gün)": return daily_base * val
    elif mode == "Yüzde (%)": return daily_base * 30 * (val / 100)
    return 0

def maas_brutlestir(tutar, tip, oran):
    sabitler = {0.71491: 4462.03, 0.67241: 4788.45, 0.61291: 5865.80, 0.54491: 5865.80}
    if tip == "Brüt": return tutar
    return (tutar - sabitler.get(oran, 5865.80)) / oran

def yardim_brutlestir(tutar, tip, oran):
    if tip == "Brüt": return tutar
    return tutar / oran

def sf(val):
    try: return f"{float(val):.4f}"
    except: return "0.0000"

def zam_planini_uygula(baslangic_maas, zam_listesi):
    """Zam planını bugün itibarıyla uygulayarak güncel maaşı döndürür."""
    bugun = datetime.now().date()
    guncel = float(baslangic_maas)
    for donem in zam_listesi:
        try:
            zam_tarihi = datetime(int(donem["yil"]), AY_MAP[donem["ay"]], 1).date()
        except Exception:
            continue
        if zam_tarihi > bugun:
            continue
        hesap_tipi = donem.get("hesap_tipi", "Birbirine Bağlı (Bileşik)")
        if hesap_tipi == "Birbirine Bağlı (Bileşik)":
            gecici = guncel
            for kalem in donem.get("kalemler", []):
                ort_kidem = kalem.get("ort_kidem", 1.0) if kalem.get("kidemli", False) else 1.0
                etkili = kalem["deger"] * ort_kidem
                if kalem["tip"] == "Yüzde (%)":
                    gecici *= (1 + etkili / 100)
                else:
                    gecici += etkili
            guncel = gecici
        else:
            artis = 0.0
            for kalem in donem.get("kalemler", []):
                ort_kidem = kalem.get("ort_kidem", 1.0) if kalem.get("kidemli", False) else 1.0
                etkili = kalem["deger"] * ort_kidem
                if kalem["tip"] == "Yüzde (%)":
                    artis += guncel * (etkili / 100)
                else:
                    artis += etkili
            guncel += artis
    return guncel

# ============================================================
# GOOGLE SHEETS
# ============================================================
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    s = st.secrets["connections"]["gsheets"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(s), scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_KEY).sheet1

@st.cache_data(ttl=60)
def verileri_getir():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        s = st.secrets["connections"]["gsheets"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(s), scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_KEY).sheet1
        data = sheet.get_all_records(
            expected_headers=SHEET_HEADERS,   # ← BU SATIRI EKLEYİN
            head=1
        )
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Veri çekilemedi: {e}")
        return pd.DataFrame()

def baslik_guncelle(sheet):
    try:
        mevcut = sheet.row_values(1)
        if mevcut != SHEET_HEADERS:
            sheet.delete_rows(1)
            sheet.insert_row(SHEET_HEADERS, 1)
    except Exception as e:
        st.warning(f"Başlık güncellenemedi: {e}")

# ============================================================
# SESSION STATE
# ============================================================
def ss(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

ss("s_isyeri", ""); ss("s_isyeri_tipi", "İşyeri"); ss("s_grev", "Grev Yasağı Yok")
ss("s_yabanci", False); ss("s_ulke", "Türkiye"); ss("s_isv_sendika", "")
ss("s_sektor", "Genel Kimya"); ss("s_grup", ""); ss("s_subeler", [])
ss("s_uye", 0); ss("s_calisan", 0)
ss("s_tis_bas", datetime.now().date())
ss("s_tis_bit", datetime.now().replace(year=datetime.now().year + 2).date())
ss("s_zam_verileri", [])

ss("s_u_tipi", "Net"); ss("s_u_tutar", 20000.0)
ss("s_ek1_mod", "Maktu"); ss("s_ek1_val", 0.0); ss("s_ek1_per", "Aylık")
ss("s_ek2_mod", "Maktu"); ss("s_ek2_val", 0.0); ss("s_ek2_per", "Aylık")
ss("s_gida_tip", "Net"); ss("s_gida_val", 0.0)
ss("s_yakacak_tip", "Net"); ss("s_yakacak_val", 0.0)
ss("s_giyim_tip", "Net"); ss("s_giyim_val", 0.0)
ss("s_ayakkabi_tip", "Net"); ss("s_ayakkabi_val", 0.0)
ss("s_yilbasi_tip", "Net"); ss("s_yilbasi_val", 0.0)
ss("s_iz_m", "Maktu"); ss("s_iz_t", "Net"); ss("s_iz_v", 0.0)
ss("s_ba_m", "Maktu"); ss("s_ba_t", "Net"); ss("s_ba_v", 0.0)
ss("s_pr_m", "Maktu"); ss("s_pr_t", "Net"); ss("s_pr_v", 0.0)
ss("s_ikramiye", 0)
ss("s_yasal_aile", False); ss("s_muaf_aile", False); ss("s_maktu_aile", 0.0)
ss("s_yasal_cocuk", False); ss("s_muaf_cocuk", False); ss("s_maktu_cocuk", 0.0)
ss("s_v_hesap", "Sabit"); ss("s_v_mod", "Maktu"); ss("s_v_val", 0.0)
ss("s_g_hesap", "Sabit"); ss("s_g_mod", "Maktu"); ss("s_g_val", 0.0)
ss("s_eo_tip", "Günlük Ücret"); ss("s_eo_mod", "Katsayı"); ss("s_eo_val", 0.0)
ss("s_denge", False); ss("s_denge_oran", 11.0)

def sifirla():
    keys = [k for k in list(st.session_state.keys()) if k.startswith("s_")]
    for k in keys:
        del st.session_state[k]
    for wk in ["isyeri_k", "calisan_k", "ek1_val_k", "ek2_val_k", "v_v_k", "g_v_k", "eo_v_k"]:
        if wk in st.session_state:
            del st.session_state[wk]

def yukle_kayit(r):
    def rv(col, default=""):
        val = r.get(col, "")
        return val if val != "" else default

    def rf(col, default=0.0):
        try:
            val = str(r.get(col, "")).strip().replace(",", ".")
            return float(val) if val not in ("", "None") else float(default)
        except:
            return float(default)

    def ri(col, default=0):
        try:
            val = str(r.get(col, "")).strip()
            return int(float(val)) if val not in ("", "None") else int(default)
        except:
            return int(default)

    st.session_state["s_isyeri"] = rv("İşyeri")
    st.session_state["isyeri_k"] = rv("İşyeri")
    st.session_state["s_isyeri_tipi"] = rv("İşyeri Tipi", "İşyeri")
    st.session_state["s_grev"] = rv("Grev Durumu", "Grev Yasağı Yok")
    st.session_state["s_yabanci"] = rv("Yabancı Ortak", "False") == "True"
    st.session_state["s_ulke"] = rv("Ortak Ülke", "Türkiye")
    st.session_state["s_isv_sendika"] = rv("İşveren Sendikası")
    st.session_state["s_sektor"] = rv("Sektör", "Genel Kimya")
    st.session_state["s_grup"] = rv("Grup")
    try:
        sub_str = rv("Şubeler", "")
        st.session_state["s_subeler"] = [s.strip() for s in sub_str.split(",") if s.strip()]
    except:
        st.session_state["s_subeler"] = []
    st.session_state["s_uye"] = ri("Üye Sayısı")
    st.session_state["s_calisan"] = ri("Toplam Çalışan")
    st.session_state["calisan_k"] = ri("Toplam Çalışan")
    try:
        bas = rv("TİS Başlangıç")
        bit = rv("TİS Bitiş")
        if bas: st.session_state["s_tis_bas"] = datetime.strptime(bas, "%d/%m/%Y").date()
        if bit: st.session_state["s_tis_bit"] = datetime.strptime(bit, "%d/%m/%Y").date()
    except:
        pass
    st.session_state["s_u_tipi"] = rv("Ana Maaş Tipi", "Net")
    st.session_state["s_u_tutar"] = rf("Ana Maaş Tutar", 20000.0)
    st.session_state["s_ek1_mod"] = rv("Ek Ödeme 1 Mod", "Maktu")
    st.session_state["s_ek1_val"] = rf("Ek Ödeme 1 Değer")
    st.session_state["ek1_val_k"] = rf("Ek Ödeme 1 Değer")
    st.session_state["s_ek1_per"] = rv("Ek Ödeme 1 Periyot", "Aylık")
    st.session_state["s_ek2_mod"] = rv("Ek Ödeme 2 Mod", "Maktu")
    st.session_state["s_ek2_val"] = rf("Ek Ödeme 2 Değer")
    st.session_state["ek2_val_k"] = rf("Ek Ödeme 2 Değer")
    st.session_state["s_ek2_per"] = rv("Ek Ödeme 2 Periyot", "Aylık")
    st.session_state["s_gida_tip"] = rv("Gıda Tip", "Net")
    st.session_state["s_gida_val"] = rf("Gıda Tutar")
    st.session_state["s_yakacak_tip"] = rv("Yakacak Tip", "Net")
    st.session_state["s_yakacak_val"] = rf("Yakacak Tutar")
    st.session_state["s_giyim_tip"] = rv("Giyim Tip", "Net")
    st.session_state["s_giyim_val"] = rf("Giyim Tutar")
    st.session_state["s_ayakkabi_tip"] = rv("Ayakkabı Tip", "Net")
    st.session_state["s_ayakkabi_val"] = rf("Ayakkabı Tutar")
    st.session_state["s_yilbasi_tip"] = rv("Yılbaşı Tip", "Net")
    st.session_state["s_yilbasi_val"] = rf("Yılbaşı Tutar")
    st.session_state["s_iz_m"] = rv("İzin Mod", "Maktu")
    st.session_state["s_iz_t"] = rv("İzin Tip", "Net")
    st.session_state["s_iz_v"] = rf("İzin Değer")
    st.session_state["s_ba_m"] = rv("Bayram Mod", "Maktu")
    st.session_state["s_ba_t"] = rv("Bayram Tip", "Net")
    st.session_state["s_ba_v"] = rf("Bayram Değer")
    st.session_state["s_pr_m"] = rv("Prim Mod", "Maktu")
    st.session_state["s_pr_t"] = rv("Prim Tip", "Net")
    st.session_state["s_pr_v"] = rf("Prim Değer")
    st.session_state["s_ikramiye"] = ri("İkramiye Günü")
    st.session_state["s_yasal_aile"] = rv("Yasal Aile", "False") == "True"
    st.session_state["s_muaf_aile"] = rv("Muafiyet Aile", "False") == "True"
    st.session_state["s_maktu_aile"] = rf("Maktu Aile")
    st.session_state["s_yasal_cocuk"] = rv("Yasal Çocuk", "False") == "True"
    st.session_state["s_muaf_cocuk"] = rv("Muafiyet Çocuk", "False") == "True"
    st.session_state["s_maktu_cocuk"] = rf("Maktu Çocuk Birim")
    st.session_state["s_v_hesap"] = rv("Vardiya Hesap", "Sabit")
    st.session_state["s_v_mod"] = rv("Vardiya Mod", "Maktu")
    st.session_state["s_v_val"] = rf("Vardiya Değer")
    st.session_state["v_v_k"] = rf("Vardiya Değer")
    st.session_state["s_g_hesap"] = rv("Gece Hesap", "Sabit")
    st.session_state["s_g_mod"] = rv("Gece Mod", "Maktu")
    st.session_state["s_g_val"] = rf("Gece Değer")
    st.session_state["g_v_k"] = rf("Gece Değer")
    st.session_state["s_eo_tip"] = rv("Ek Özel Tip", "Günlük Ücret")
    st.session_state["s_eo_mod"] = rv("Ek Özel Mod", "Katsayı")
    st.session_state["s_eo_val"] = rf("Ek Özel Değer")
    st.session_state["eo_v_k"] = rf("Ek Özel Değer")
    st.session_state["s_denge"] = rv("Denge Aktif", "False") == "True"
    st.session_state["s_denge_oran"] = rf("Denge Oran", 11.0)

# ============================================================
# SEKMELER
# ============================================================
tab1, tab2, tab3 = st.tabs([
    "🏢 İşyeri Bilgileri",
    "💰 Ücret ve Sosyal Ödemeler",
    "📊 Karşılaştırma ve İstatistik"
])

# ============================================================
# TAB 1 — İŞYERİ BİLGİLERİ
# ============================================================
with tab1:
    st.header("🏢 İşyeri Bilgileri")

    df = verileri_getir()

    if st.button("➕ Yeni Kayıt"):
        sifirla()
        st.rerun()

    with st.expander("📂 Kayıtlı Veriyi Çağır", expanded=not df.empty):
        if not df.empty:
            isyeri_listesi = [i for i in df["İşyeri"].dropna().unique().tolist() if i != ""]
            if isyeri_listesi:
                sec = st.selectbox("İşyeri Seç", isyeri_listesi)
                if st.button("📥 Verileri Yükle"):
                    r = df[df["İşyeri"] == sec].iloc[0].to_dict()
                    yukle_kayit(r)
                    st.success(f"✅ {sec} yüklendi!")
                    st.rerun()
        st.subheader("📋 Kayıtlı İşyerleri")
        if not df.empty:
            goster = [c for c in ["İşyeri", "Sektör", "Şubeler", "TİS Başlangıç", "TİS Bitiş", "Toplam Maliyet"] if c in df.columns]
            st.dataframe(df[goster], use_container_width=True)
        else:
            st.info("Henüz kayıt yok.")

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🏭 Temel Bilgiler")
        isyeri_adi = st.text_input("İşyeri / İşletme Adı", value=st.session_state["s_isyeri"], key="isyeri_k")
        isyeri_tipi = st.radio("Tipi", ["İşyeri", "İşletme"],
                               index=["İşyeri", "İşletme"].index(st.session_state["s_isyeri_tipi"]),
                               horizontal=True)
        grev_yasagi = st.selectbox("Grev Yasağı", ["Grev Yasağı Yok", "Grev Yasağı Var"],
                                   index=["Grev Yasağı Yok", "Grev Yasağı Var"].index(st.session_state["s_grev"]))

        st.subheader("🌍 Ortaklık Bilgisi")
        yabanci_ortak = st.checkbox("Yabancı Ortaklı", value=st.session_state["s_yabanci"])
        ortak_ulke = "Türkiye"
        if yabanci_ortak:
            idx_ulke = ULKELER.index(st.session_state["s_ulke"]) if st.session_state["s_ulke"] in ULKELER else 0
            ortak_ulke = st.selectbox("Ortak Ülke", ULKELER, index=idx_ulke)
        isv_sendika = st.text_input("İşveren Sendikası", value=st.session_state["s_isv_sendika"])

        st.subheader("🏷️ Sektör / Grup")
        idx_sek = SEKTORLER.index(st.session_state["s_sektor"]) if st.session_state["s_sektor"] in SEKTORLER else 0
        sektor = st.selectbox("Sektör", SEKTORLER, index=idx_sek)
        grup = st.text_input("Grup (opsiyonel)", value=st.session_state["s_grup"])
        subeler = st.multiselect("Bağlı Şubeler", SUBELER, default=st.session_state["s_subeler"])

    with col_b:
        st.subheader("👥 Üye / Çalışan")
        uye_sayisi = st.number_input("Sendikalı Üye Sayısı", value=st.session_state["s_uye"], min_value=0)
        toplam_calisan = st.number_input("Toplam Çalışan Sayısı",
                                         value=st.session_state["s_calisan"], min_value=0, key="calisan_k")

        st.subheader("📅 TİS Dönemi")
        tis_bas = st.date_input("Başlangıç Tarihi", value=st.session_state["s_tis_bas"])
        tis_bit = st.date_input("Bitiş Tarihi", value=st.session_state["s_tis_bit"])

        bugun = datetime.now().date()
        bas_d = tis_bas.date() if hasattr(tis_bas, 'date') else tis_bas
        bit_d = tis_bit.date() if hasattr(tis_bit, 'date') else tis_bit
        kalan = max((bit_d - bugun).days, 0)
        toplam_gun = (bit_d - bas_d).days
        yuzde = min(max(((toplam_gun - kalan) / toplam_gun) * 100, 0), 100) if toplam_gun > 0 else 0
        st.progress(yuzde / 100)
        st.caption(f"Kalan: {kalan} gün")
        if kalan <= 0:
            st.error("❌ Sözleşme süresi doldu!")
        elif kalan <= 120:
            st.error("🚨 Yetki başvuru süresi başladı!")
        elif kalan <= 365:
            st.warning("⚠️ Son yılındasınız.")
        else:
            fark = toplam_gun + 1
            if fark < 365:
                st.warning(f"⚠️ TİS 1 yıldan az olamaz ({fark} gün)")
            elif fark > 1095:
                st.error("❌ TİS 3 yıldan fazla olamaz")
            else:
                st.success(f"✅ {round(fark/365,1)} yıl ({fark} gün)")

    # session_state güncelle
    st.session_state["s_isyeri"] = isyeri_adi
    st.session_state["s_isyeri_tipi"] = isyeri_tipi
    st.session_state["s_grev"] = grev_yasagi
    st.session_state["s_yabanci"] = yabanci_ortak
    st.session_state["s_ulke"] = ortak_ulke
    st.session_state["s_isv_sendika"] = isv_sendika
    st.session_state["s_sektor"] = sektor
    st.session_state["s_grup"] = grup
    st.session_state["s_subeler"] = subeler
    st.session_state["s_uye"] = uye_sayisi
    st.session_state["s_calisan"] = toplam_calisan
    st.session_state["s_tis_bas"] = bas_d
    st.session_state["s_tis_bit"] = bit_d

    # -------------------------------------------------------
    # ZAM PLANLAMA — Tab 1'in alt kısmı
    # -------------------------------------------------------
    st.divider()
    st.subheader("📈 Dinamik Zam Planlaması")
    st.caption("Sözleşme boyunca uygulanacak her zam dönemini ayrı ayrı tanımlayın.")

    zam_donem_sayisi = st.number_input("Kaç Farklı Zam Dönemi Var?",
                                        min_value=1, max_value=12, value=2,
                                        key="n_donem_sayisi")

    yeni_zamlar = []
    for i in range(int(zam_donem_sayisi)):
        with st.container(border=True):
            st.markdown(f"**{i+1}. Zam Dönemi**")
            ct1, ct2, ct3 = st.columns([1, 1, 2])
            with ct1:
                z_yil = st.selectbox("Yıl", [2024, 2025, 2026, 2027, 2028], key=f"z_yil_{i}")
            with ct2:
                z_ay = st.selectbox("Ay", AYLAR, key=f"z_ay_{i}")
            with ct3:
                z_not = st.text_input("Not", placeholder="örn: 1. Yıl 1. Altı Ay", key=f"z_not_{i}")

            hesap_tipi = st.radio(
                "Uygulama Biçimi",
                ["Birbirine Bağlı (Bileşik)", "Ana Ücrete Ayrı Ayrı (Toplamsal)"],
                key=f"h_tipi_{i}", horizontal=True
            )

            kalem_sayisi = st.number_input("Zam Kalemi Sayısı", min_value=1, max_value=5,
                                           value=1, key=f"k_sayisi_{i}")
            donem_kalemleri = []
            for j in range(int(kalem_sayisi)):
                ck1, ck2, ck3, ck4 = st.columns([1.5, 2, 1.5, 1.5])
                with ck1:
                    k_tip = st.selectbox("Tip", ["Yüzde (%)", "Maktu (TL)"], key=f"k_tip_{i}_{j}")
                with ck2:
                    k_val = st.number_input("Tutar / Oran", min_value=0.0, step=0.1, key=f"k_val_{i}_{j}")
                with ck3:
                    k_kidem = st.selectbox("Kapsam", ["Sabit", "Kıdeme Bağlı"], key=f"k_kidem_{i}_{j}")
                with ck4:
                    k_ort_kidem = 1.0
                    if k_kidem == "Kıdeme Bağlı":
                        k_ort_kidem = st.number_input("Ort. Kıdem (Yıl)", min_value=0.0,
                                                       value=10.0, key=f"k_ort_kidem_{i}_{j}")
                donem_kalemleri.append({
                    "tip": k_tip,
                    "deger": k_val,
                    "kidemli": k_kidem == "Kıdeme Bağlı",
                    "ort_kidem": k_ort_kidem
                })

            yeni_zamlar.append({
                "yil": z_yil,
                "ay": z_ay,
                "not": z_not,
                "hesap_tipi": hesap_tipi,
                "kalemler": donem_kalemleri
            })

    # Döngü bitti — session_state'e kaydet
    st.session_state["s_zam_verileri"] = yeni_zamlar

    # Zam planı özet önizleme
    if yeni_zamlar:
        st.markdown("**📋 Zam Planı Özeti**")
        for d in yeni_zamlar:
            kalem_str = ", ".join([
                f"%{k['deger']}" if k['tip'] == "Yüzde (%)" else f"{k['deger']:.0f} TL"
                for k in d["kalemler"]
            ])
            not_str = f" — {d['not']}" if d['not'] else ""
            st.caption(f"• {d['ay']} {d['yil']}: {kalem_str}{not_str}")

# ============================================================
# TAB 2 — ÜCRET VE SOSYAL ÖDEMELER
# ============================================================
with tab2:
    st.header("💰 Ücret ve Ek Ödemeler")

    c1, c2, c3 = st.columns(3)
    with c1:
        u_tipi = st.radio("Ücret Tipi", ["Net", "Brüt"],
                          index=["Net", "Brüt"].index(st.session_state["s_u_tipi"]))
        u_tutar = st.number_input("Çıplak Ücret (Girilen Değer)", value=st.session_state["s_u_tutar"], min_value=0.0)
    with c2:
        with st.container(border=True):
            st.caption("Ek Ödeme 1")
            ek1_mod = st.selectbox("Mod", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"],
                                   index=["Maktu", "Katsayı (Gün)", "Yüzde (%)"].index(st.session_state["s_ek1_mod"]),
                                   key="ek1_mod_w")
            ek1_val = st.number_input("Değer", value=st.session_state["s_ek1_val"], min_value=0.0, key="ek1_val_k")
            ek1_per = st.selectbox("Periyot", ["Aylık", "Yıllık"],
                                   index=["Aylık", "Yıllık"].index(st.session_state["s_ek1_per"]),
                                   key="ek1_per_w")
    with c3:
        with st.container(border=True):
            st.caption("Ek Ödeme 2")
            ek2_mod = st.selectbox("Mod", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"],
                                   index=["Maktu", "Katsayı (Gün)", "Yüzde (%)"].index(st.session_state["s_ek2_mod"]),
                                   key="ek2_mod_w")
            ek2_val = st.number_input("Değer", value=st.session_state["s_ek2_val"], min_value=0.0, key="ek2_val_k")
            ek2_per = st.selectbox("Periyot", ["Aylık", "Yıllık"],
                                   index=["Aylık", "Yıllık"].index(st.session_state["s_ek2_per"]),
                                   key="ek2_per_w")

    # Zam planını uygulayarak güncel maaşı hesapla
    maas_base = maas_brutlestir(u_tutar, u_tipi, secilen_oran)
    zam_listesi = st.session_state.get("s_zam_verileri", [])
    a_brut = zam_planini_uygula(maas_base, zam_listesi)
    g_brut = a_brut / 30

    if zam_listesi:
        st.info(f"📊 Zam planı uygulandı → Güncel Ana Maaş: **{a_brut:,.2f} TL** (Girilen: {maas_base:,.2f} TL)")

    st.markdown("### 🎁 Sosyal Yardımlar")
    cs1, cs2 = st.columns(2)
    with cs1:
        with st.container(border=True):
            st.write("🍞 **Gıda (Aylık)**")
            gida_tip = st.radio("", ["Net", "Brüt"], horizontal=True,
                                index=["Net", "Brüt"].index(st.session_state["s_gida_tip"]), key="gida_tip_w")
            gida_val = st.number_input("Tutar", value=st.session_state["s_gida_val"], min_value=0.0, key="gida_val_w")
            gida = yardim_brutlestir(gida_val, gida_tip, secilen_oran)
    with cs2:
        with st.container(border=True):
            st.write("🔥 **Yakacak (Aylık)**")
            yakacak_tip = st.radio("", ["Net", "Brüt"], horizontal=True,
                                   index=["Net", "Brüt"].index(st.session_state["s_yakacak_tip"]), key="yakacak_tip_w")
            yakacak_val = st.number_input("Tutar", value=st.session_state["s_yakacak_val"], min_value=0.0, key="yakacak_val_w")
            yakacak = yardim_brutlestir(yakacak_val, yakacak_tip, secilen_oran)

    cs3, cs4, cs5 = st.columns(3)
    with cs3:
        with st.container(border=True):
            st.write("👕 **Giyim (Yıllık)**")
            giyim_tip = st.radio("", ["Net", "Brüt"], horizontal=True,
                                 index=["Net", "Brüt"].index(st.session_state["s_giyim_tip"]), key="giyim_tip_w")
            giyim_val = st.number_input("Tutar", value=st.session_state["s_giyim_val"], min_value=0.0, key="giyim_val_w")
            giyim = yardim_brutlestir(giyim_val, giyim_tip, secilen_oran)
    with cs4:
        with st.container(border=True):
            st.write("👟 **Ayakkabı (Yıllık)**")
            ayakkabi_tip = st.radio("", ["Net", "Brüt"], horizontal=True,
                                    index=["Net", "Brüt"].index(st.session_state["s_ayakkabi_tip"]), key="ayakkabi_tip_w")
            ayakkabi_val = st.number_input("Tutar", value=st.session_state["s_ayakkabi_val"], min_value=0.0, key="ayakkabi_val_w")
            ayakkabi = yardim_brutlestir(ayakkabi_val, ayakkabi_tip, secilen_oran)
    with cs5:
        with st.container(border=True):
            st.write("🎁 **Yılbaşı (Yıllık)**")
            yilbasi_tip = st.radio("", ["Net", "Brüt"], horizontal=True,
                                   index=["Net", "Brüt"].index(st.session_state["s_yilbasi_tip"]), key="yilbasi_tip_w")
            yilbasi_val = st.number_input("Tutar", value=st.session_state["s_yilbasi_val"], min_value=0.0, key="yilbasi_val_w")
            yilbasi = yardim_brutlestir(yilbasi_val, yilbasi_tip, secilen_oran)

    cs6, cs7, cs8 = st.columns(3)
    with cs6:
        with st.container(border=True):
            st.write("📅 **İzin (Yıllık)**")
            iz_m = st.selectbox("Mod", ["Maktu", "Katsayı (Gün)"],
                                index=["Maktu", "Katsayı (Gün)"].index(st.session_state["s_iz_m"]), key="iz_m_w")
            iz_t = st.radio("", ["Net", "Brüt"], horizontal=True,
                            index=["Net", "Brüt"].index(st.session_state["s_iz_t"]), key="iz_t_w")
            iz_v = st.number_input("Değer", value=st.session_state["s_iz_v"], min_value=0.0, key="iz_v_w")
            ay_izin = yardim_brutlestir(calc_hybrid(iz_v, iz_m, g_brut), iz_t, secilen_oran) / 12
    with cs7:
        with st.container(border=True):
            st.write("🎉 **Bayram (Yıllık)**")
            ba_m = st.selectbox("Mod", ["Maktu", "Katsayı (Gün)"],
                                index=["Maktu", "Katsayı (Gün)"].index(st.session_state["s_ba_m"]), key="ba_m_w")
            ba_t = st.radio("", ["Net", "Brüt"], horizontal=True,
                            index=["Net", "Brüt"].index(st.session_state["s_ba_t"]), key="ba_t_w")
            ba_v = st.number_input("Değer", value=st.session_state["s_ba_v"], min_value=0.0, key="ba_v_w")
            ay_bayram = yardim_brutlestir(calc_hybrid(ba_v, ba_m, g_brut), ba_t, secilen_oran) / 12
    with cs8:
        with st.container(border=True):
            st.write("🏆 **Prim**")
            pr_m = st.selectbox("Mod", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"],
                                index=["Maktu", "Katsayı (Gün)", "Yüzde (%)"].index(st.session_state["s_pr_m"]), key="pr_m_w")
            pr_t = st.radio("", ["Net", "Brüt"], horizontal=True,
                            index=["Net", "Brüt"].index(st.session_state["s_pr_t"]), key="pr_t_w")
            pr_v = st.number_input("Değer", value=st.session_state["s_pr_v"], min_value=0.0, key="pr_v_w")
            ay_prim = yardim_brutlestir(calc_hybrid(pr_v, pr_m, g_brut), pr_t, secilen_oran)

    with st.container(border=True):
        ikramiye = st.number_input("💰 Yıllık İkramiye Günü", value=st.session_state["s_ikramiye"], min_value=0)
        ay_ikramiye = (g_brut * ikramiye) / 12

    with st.container(border=True):
        st.write("👨‍👩‍👧‍👦 **Aile & Çocuk**")
        cac1, cac2 = st.columns(2)
        with cac1:
            yasal_aile = st.checkbox("657 Aile Yardımı", value=st.session_state["s_yasal_aile"])
            muaf_aile = st.checkbox("Muafiyet Aile", value=st.session_state["s_muaf_aile"])
            maktu_aile = st.number_input("Maktu Aile", value=st.session_state["s_maktu_aile"], min_value=0.0)
        with cac2:
            yasal_cocuk = st.checkbox("657 Çocuk Yardımı", value=st.session_state["s_yasal_cocuk"])
            muaf_cocuk = st.checkbox("Muafiyet Çocuk", value=st.session_state["s_muaf_cocuk"])
            maktu_cocuk = st.number_input("Maktu Çocuk (Birim)", value=st.session_state["s_maktu_cocuk"], min_value=0.0)

    st.divider()
    st.markdown("### ⚡ Vardiya, Gece ve Özel")
    cv1, cv2, cv3 = st.columns(3)
    with cv1:
        with st.container(border=True):
            st.write("🔄 **Vardiya Zammı**")
            v_hesap = st.selectbox("Hesap Tipi", ["Sabit", "Fiili (195/225)"],
                                   index=["Sabit", "Fiili (195/225)"].index(st.session_state["s_v_hesap"]), key="v_h_w")
            v_mod = st.selectbox("Birim", ["Maktu", "Yüzde (%)"],
                                 index=["Maktu", "Yüzde (%)"].index(st.session_state["s_v_mod"]), key="v_m_w")
            v_val = st.number_input("Miktar", value=st.session_state["s_v_val"], min_value=0.0, key="v_v_k")
    with cv2:
        with st.container(border=True):
            st.write("🌙 **Gece Zammı**")
            g_hesap = st.selectbox("Hesap Tipi", ["Sabit", "Fiili (80/225)"],
                                   index=["Sabit", "Fiili (80/225)"].index(st.session_state["s_g_hesap"]), key="g_h_w")
            g_mod = st.selectbox("Birim", ["Maktu", "Yüzde (%)"],
                                 index=["Maktu", "Yüzde (%)"].index(st.session_state["s_g_mod"]), key="g_m_w")
            gece_val = st.number_input("Miktar", value=st.session_state["s_g_val"], min_value=0.0, key="g_v_k")
    with cv3:
        with st.container(border=True):
            st.write("➕ **Ek Özel**")
            eo_tip = st.selectbox("Baz", ["Günlük Ücret", "Aylık Ücret"],
                                  index=["Günlük Ücret", "Aylık Ücret"].index(st.session_state["s_eo_tip"]), key="eo_t_w")
            eo_mod = st.selectbox("Birim", ["Katsayı", "Yüzde (%)"],
                                  index=["Katsayı", "Yüzde (%)"].index(st.session_state["s_eo_mod"]), key="eo_m_w")
            eo_val = st.number_input("Miktar", value=st.session_state["s_eo_val"], min_value=0.0, key="eo_v_k")

    st.markdown("### 📈 Denge Ödentisi")
    with st.container(border=True):
        cd1, cd2 = st.columns(2)
        with cd1:
            denge_aktif = st.checkbox("Denge Ödentisi Uygula", value=st.session_state["s_denge"])
            denge_oran_pct = st.number_input("Oran (%)", value=st.session_state["s_denge_oran"], min_value=0.0)
        with cd2:
            st.caption("Baz: Ücret + İkramiye + Gece + Vardiya")

    # --- HESAPLAMALAR ---
    ay_ek1 = calc_hybrid(ek1_val, ek1_mod, g_brut) if ek1_per == "Aylık" else calc_hybrid(ek1_val, ek1_mod, g_brut) / 12
    ay_ek2 = calc_hybrid(ek2_val, ek2_mod, g_brut) if ek2_per == "Aylık" else calc_hybrid(ek2_val, ek2_mod, g_brut) / 12

    yasal_aile_t = aile_yasal_sabit if yasal_aile else 0
    muaf_aile_t = muafiyet_aile if muaf_aile else 0
    yasal_cocuk_t = (cocuk_6_ustu * 2) if yasal_cocuk else 0
    muaf_cocuk_t = muafiyet_cocuk if muaf_cocuk else 0
    ay_aile_cocuk = yasal_aile_t + muaf_aile_t + maktu_aile + yasal_cocuk_t + muaf_cocuk_t + (maktu_cocuk * 2)

    v_tutar = calc_hybrid(v_val, v_mod, g_brut)
    if v_hesap == "Fiili (195/225)":
        v_tutar = v_tutar * 195 / 225

    g_tutar = calc_hybrid(gece_val, g_mod, g_brut)
    if g_hesap == "Fiili (80/225)":
        g_tutar = g_tutar * 80 / 225

    if eo_tip == "Günlük Ücret":
        ay_ek_ozel = g_brut * (eo_val if eo_mod == "Katsayı" else eo_val / 100)
    else:
        ay_ek_ozel = a_brut * (eo_val if eo_mod == "Katsayı" else eo_val / 100)

    if denge_aktif:
        baz = a_brut + ay_ikramiye + g_tutar + v_tutar
        ay_denge = baz * (denge_oran_pct / 100)
        st.metric("Denge Ödentisi", f"{ay_denge:,.2f} TL")
    else:
        ay_denge = 0.0

    toplam_sosyal = (
        gida + yakacak + ay_izin + ay_bayram + ay_prim +
        (giyim + ayakkabi + yilbasi) / 12 +
        ay_ikramiye + ay_aile_cocuk +
        v_tutar + g_tutar + ay_ek_ozel + ay_denge
    )
    t_maliyet = a_brut + ay_ek1 + ay_ek2 + toplam_sosyal

    # --- SONUÇLAR ---
    st.divider()
    r1, r2, r3 = st.columns(3)
    r1.metric("💼 Toplam Aylık Maliyet", f"{t_maliyet:,.2f} TL")
    r2.metric("🎁 Sosyal Paket", f"{toplam_sosyal:,.2f} TL")
    r3.metric("💵 Ana Maaş (Brüt)", f"{a_brut:,.2f} TL")

    detay = pd.DataFrame({
        "Kalem": ["Ana Maaş", "Ek Ödemeler (1+2)", "Sosyal Paket", "Vardiya/Gece/Özel"],
        "Aylık Tutar (TL)": [
            f"{a_brut:,.2f}",
            f"{ay_ek1 + ay_ek2:,.2f}",
            f"{toplam_sosyal - v_tutar - g_tutar - ay_ek_ozel:,.2f}",
            f"{v_tutar + g_tutar + ay_ek_ozel:,.2f}"
        ]
    })
    st.table(detay)

    # --- KAYIT VE İNDİRME ---
    st.divider()
    kb1, kb2 = st.columns(2)
    with kb1:
        if st.button("💾 Veritabanına Kaydet"):
            try:
                sheet = get_sheet()
                baslik_guncelle(sheet)
                tis_bas_str = st.session_state["s_tis_bas"].strftime("%d/%m/%Y")
                tis_bit_str = st.session_state["s_tis_bit"].strftime("%d/%m/%Y")
                # Zam planı özet metni
                zam_ozet = " | ".join([
                    f"{d['ay']} {d['yil']}: " + ", ".join([
                        f"%{k['deger']}" if k['tip'] == "Yüzde (%)" else f"{k['deger']:.0f}TL"
                        for k in d["kalemler"]
                    ])
                    for d in st.session_state.get("s_zam_verileri", [])
                ])
                row = [
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                    st.session_state["active_user"],
                    st.session_state["s_isyeri"],
                    st.session_state["s_isyeri_tipi"],
                    st.session_state["s_grev"],
                    str(st.session_state["s_yabanci"]),
                    st.session_state["s_ulke"],
                    st.session_state["s_isv_sendika"],
                    st.session_state["s_sektor"],
                    st.session_state["s_grup"],
                    ", ".join(st.session_state["s_subeler"]),
                    st.session_state["s_uye"],
                    st.session_state["s_calisan"],
                    tis_bas_str, tis_bit_str,
                    zam_ozet,
                    u_tipi, sf(u_tutar),
                    ek1_mod, sf(ek1_val), ek1_per,
                    ek2_mod, sf(ek2_val), ek2_per,
                    gida_tip, sf(gida_val),
                    yakacak_tip, sf(yakacak_val),
                    giyim_tip, sf(giyim_val),
                    ayakkabi_tip, sf(ayakkabi_val),
                    yilbasi_tip, sf(yilbasi_val),
                    iz_m, iz_t, sf(iz_v),
                    ba_m, ba_t, sf(ba_v),
                    pr_m, pr_t, sf(pr_v),
                    ikramiye,
                    str(yasal_aile), str(muaf_aile), sf(maktu_aile),
                    str(yasal_cocuk), str(muaf_cocuk), sf(maktu_cocuk),
                    v_hesap, v_mod, sf(v_val),
                    g_hesap, g_mod, sf(gece_val),
                    eo_tip, eo_mod, sf(eo_val),
                    str(denge_aktif), sf(denge_oran_pct),
                    sf(a_brut), sf(toplam_sosyal), sf(t_maliyet)
                ]
                sheet.append_row(row)
                verileri_getir.clear()
                st.success("✅ Kaydedildi!")
                st.balloons()
            except Exception as e:
                st.error(f"Kayıt hatası: {e}")

    with kb2:
        rapor = {
            "Parametre": [
                "Uzman", "İşyeri", "Sektör", "Şubeler",
                "TİS Başlangıç", "TİS Bitiş", "Üye Sayısı", "Grev Durumu",
                "Ana Maaş (Brüt)", "Gıda", "Yakacak",
                "Giyim (Aylık)", "Ayakkabı (Aylık)", "Yılbaşı (Aylık)",
                "İzin (Aylık)", "Bayram (Aylık)", "Prim (Aylık)", "İkramiye (Aylık)",
                "Aile & Çocuk", "Vardiya", "Gece Zammı", "Özel Ek", "Denge",
                "Sosyal Paket", "Toplam Maliyet"
            ],
            "Değer": [
                st.session_state["active_user"],
                st.session_state["s_isyeri"],
                st.session_state["s_sektor"],
                ", ".join(st.session_state["s_subeler"]),
                st.session_state["s_tis_bas"].strftime("%d/%m/%Y"),
                st.session_state["s_tis_bit"].strftime("%d/%m/%Y"),
                st.session_state["s_uye"],
                st.session_state["s_grev"],
                f"{a_brut:,.2f} TL", f"{gida:,.2f} TL", f"{yakacak:,.2f} TL",
                f"{giyim/12:,.2f} TL", f"{ayakkabi/12:,.2f} TL", f"{yilbasi/12:,.2f} TL",
                f"{ay_izin:,.2f} TL", f"{ay_bayram:,.2f} TL",
                f"{ay_prim:,.2f} TL", f"{ay_ikramiye:,.2f} TL",
                f"{ay_aile_cocuk:,.2f} TL", f"{v_tutar:,.2f} TL",
                f"{g_tutar:,.2f} TL", f"{ay_ek_ozel:,.2f} TL", f"{ay_denge:,.2f} TL",
                f"{toplam_sosyal:,.2f} TL", f"{t_maliyet:,.2f} TL"
            ]
        }
        rapor_df = pd.DataFrame(rapor)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            rapor_df.to_excel(writer, index=False, sheet_name='TİS_Rapor')
            writer.sheets['TİS_Rapor'].set_column('A:B', 30)
        st.download_button(
            "📥 Excel Raporu İndir",
            data=output.getvalue(),
            file_name=f"{st.session_state['s_isyeri']}_TIS_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ============================================================
# TAB 3 — KARŞILAŞTIRMA VE İSTATİSTİK
# ============================================================
with tab3:
    st.header("📊 Karşılaştırma ve İstatistik")

    df3 = verileri_getir()

    if df3.empty:
        st.info("Henüz kayıtlı veri yok. Önce işyeri kaydedin.")
    else:
        for col in ["Ana Maaş (Brüt)", "Sosyal Paket", "Toplam Maliyet"]:
            if col in df3.columns:
                df3[col] = pd.to_numeric(df3[col].astype(str).str.replace(",", "."), errors='coerce')

        st.subheader("🔢 Genel Özet")
        og1, og2, og3, og4 = st.columns(4)
        og1.metric("Toplam İşyeri", len(df3))
        if "Üye Sayısı" in df3.columns:
            try:
                toplam_uye = pd.to_numeric(df3["Üye Sayısı"], errors='coerce').sum()
                og2.metric("Toplam Üye", f"{int(toplam_uye):,}")
            except:
                og2.metric("Toplam Üye", "-")
        if "Ana Maaş (Brüt)" in df3.columns:
            og3.metric("Ort. Çıplak Ücret", f"{df3['Ana Maaş (Brüt)'].mean():,.0f} TL")
        if "Toplam Maliyet" in df3.columns:
            og4.metric("Ort. Giydirilmiş Ücret", f"{df3['Toplam Maliyet'].mean():,.0f} TL")

        st.divider()

        st.subheader("🏙️ Şube Bazlı Karşılaştırma")
        if "Şubeler" in df3.columns and "Ana Maaş (Brüt)" in df3.columns:
            sube_rows = []
            for _, row in df3.iterrows():
                for s in str(row.get("Şubeler", "")).split(","):
                    s = s.strip()
                    if s:
                        sube_rows.append({"Şube": s,
                                          "Çıplak": row.get("Ana Maaş (Brüt)", 0),
                                          "Giydirilmiş": row.get("Toplam Maliyet", 0)})
            if sube_rows:
                sube_df = pd.DataFrame(sube_rows)
                sube_ozet = sube_df.groupby("Şube").agg(
                    İşyeri_Sayısı=("Çıplak", "count"),
                    Ort_Çıplak=("Çıplak", "mean"),
                    Ort_Giydirilmiş=("Giydirilmiş", "mean")
                ).reset_index().sort_values("Ort_Çıplak", ascending=False)
                sube_ozet["Ort_Çıplak"] = sube_ozet["Ort_Çıplak"].map("{:,.0f} TL".format)
                sube_ozet["Ort_Giydirilmiş"] = sube_ozet["Ort_Giydirilmiş"].map("{:,.0f} TL".format)
                sube_ozet.columns = ["Şube", "İşyeri Sayısı", "Ort. Çıplak Ücret", "Ort. Giydirilmiş Ücret"]
                st.dataframe(sube_ozet, use_container_width=True, hide_index=True)

        st.divider()

        st.subheader("🏭 Sektör Bazlı Karşılaştırma")
        if "Sektör" in df3.columns and "Ana Maaş (Brüt)" in df3.columns:
            sek_ozet = df3.groupby("Sektör").agg(
                İşyeri=("Ana Maaş (Brüt)", "count"),
                Ort_Çıplak=("Ana Maaş (Brüt)", "mean"),
                Ort_Giydirilmiş=("Toplam Maliyet", "mean")
            ).reset_index().sort_values("Ort_Çıplak", ascending=False)
            sek_ozet["Ort_Çıplak"] = sek_ozet["Ort_Çıplak"].map("{:,.0f} TL".format)
            sek_ozet["Ort_Giydirilmiş"] = sek_ozet["Ort_Giydirilmiş"].map("{:,.0f} TL".format)
            sek_ozet.columns = ["Sektör", "İşyeri Sayısı", "Ort. Çıplak Ücret", "Ort. Giydirilmiş Ücret"]
            st.dataframe(sek_ozet, use_container_width=True, hide_index=True)

        st.divider()

        st.subheader("🔍 İşyeri Karşılaştırması")
        if "İşyeri" in df3.columns:
            secilen = st.selectbox("İşyeri Seç", df3["İşyeri"].dropna().unique().tolist(), key="tab3_isyeri_sec")
            if secilen:
                sec_row = df3[df3["İşyeri"] == secilen].iloc[0]
                genel_ort_maas = df3["Ana Maaş (Brüt)"].mean()
                genel_ort_maliyet = df3["Toplam Maliyet"].mean()
                isyeri_maas = float(str(sec_row.get("Ana Maaş (Brüt)", 0)).replace(",", ".") or 0)
                isyeri_maliyet = float(str(sec_row.get("Toplam Maliyet", 0)).replace(",", ".") or 0)

                kk1, kk2 = st.columns(2)
                with kk1:
                    st.metric("Çıplak Ücret", f"{isyeri_maas:,.0f} TL",
                              delta=f"{isyeri_maas - genel_ort_maas:+,.0f} TL (genel ort.)")
                with kk2:
                    st.metric("Giydirilmiş Ücret", f"{isyeri_maliyet:,.0f} TL",
                              delta=f"{isyeri_maliyet - genel_ort_maliyet:+,.0f} TL (genel ort.)")

                if "Sektör" in df3.columns and sec_row.get("Sektör"):
                    sek = sec_row.get("Sektör")
                    sek_df = df3[df3["Sektör"] == sek]
                    sk1, sk2 = st.columns(2)
                    with sk1:
                        st.metric(f"{sek} Sektör Ort. — Çıplak",
                                  f"{sek_df['Ana Maaş (Brüt)'].mean():,.0f} TL",
                                  delta=f"{isyeri_maas - sek_df['Ana Maaş (Brüt)'].mean():+,.0f} TL")
                    with sk2:
                        st.metric(f"{sek} Sektör Ort. — Giydirilmiş",
                                  f"{sek_df['Toplam Maliyet'].mean():,.0f} TL",
                                  delta=f"{isyeri_maliyet - sek_df['Toplam Maliyet'].mean():+,.0f} TL")

        st.divider()

        st.subheader("📋 Tüm Kayıtlar")
        goster_cols = [c for c in ["İşyeri", "Sektör", "Şubeler", "Üye Sayısı",
                                    "TİS Başlangıç", "TİS Bitiş",
                                    "Ana Maaş (Brüt)", "Sosyal Paket", "Toplam Maliyet"] if c in df3.columns]
        st.dataframe(df3[goster_cols].sort_values("Toplam Maliyet", ascending=False),
                     use_container_width=True, hide_index=True)
