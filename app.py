import streamlit as st
import pandas as pd
import io
import json
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

SEKTORLER = ["Özel", "Kamu"]

GRUPLAR = ["Petrol", "Petrol Depolama", "Genel Kimya", "Boya", "Plastik",
           "Otomotiv Yan Sanayi", "Lastik", "Gübre", "İlaç", "Cam", "Diğer"]

ULKELER = [
    "Türkiye","Almanya","Fransa","İngiltere","İtalya","ABD","Japonya",
    "Hollanda","İsviçre","İsveç","Avustralya","Avusturya","Belçika",
    "Kanada","Azerbaycan","Çin","Güney Kore","Hindistan","Brezilya",
    "Meksika","İspanya","Portekiz","Danimarka","Norveç","Finlandiya",
    "Polonya","Çek Cumhuriyeti","Macaristan","Romanya","Bulgaristan",
    "Yunanistan","Hırvatistan","Slovenya","Slovakya","Estonya","Letonya",
    "Litvanya","İrlanda","Lüksemburg","Katar","BAE","Suudi Arabistan",
    "İsrail","Güney Afrika","Diğer"
]

ISV_SENDIKALARI = [
    "İşveren Sendikası Yok",
    "Kiplas",
    "Tühis",
    "İlaç İşverenleri Sendikası",
]

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
    "Ek Ödeme 1 Mod", "Ek Ödeme 1 Değer", "Ek Ödeme 1 Periyot", "Ek Ödeme 1 Tip", "Ek Ödeme 1 Zam",
    "Ek Ödeme 2 Mod", "Ek Ödeme 2 Değer", "Ek Ödeme 2 Periyot", "Ek Ödeme 2 Tip", "Ek Ödeme 2 Zam",
    "Gıda Tip", "Gıda Tutar", "Gıda Periyot", "Gıda Not",
    "Yakacak Mod", "Yakacak Tip", "Yakacak KDV", "Yakacak Tutar", "Yakacak M3", "Yakacak Birim", "Yakacak Periyot", "Yakacak Not",
    "Giyim Tip", "Giyim Tutar", "Giyim Periyot", "Giyim Not",
    "Ayakkabı Tip", "Ayakkabı Tutar", "Ayakkabı Periyot", "Ayakkabı Not",
    "Yılbaşı Tip", "Yılbaşı Tutar", "Yılbaşı Periyot", "Yılbaşı Not",
    "İzin Mod", "İzin Tip", "İzin Değer", "İzin Periyot", "İzin Not",
    "Bayram Mod", "Bayram Tip", "Bayram Değer", "Bayram Periyot", "Bayram Not",
    "Prim Mod", "Prim Tip", "Prim Değer", "Prim Periyot", "Prim Not",
    "İkramiye Günü", "İkramiye Not",
    "Yasal Aile", "Yasal Aile Pct", "Muafiyet Aile", "Muafiyet Aile Pct", "Maktu Aile", "Aile Not",
    "Yasal Çocuk", "Yasal Çocuk Pct", "Muafiyet Çocuk", "Muafiyet Çocuk Pct", "Maktu Çocuk Birim", "Çocuk Not",
    "Vardiya Hesap", "Vardiya Mod", "Vardiya Değer", "Vardiya Not",
    "Gece Hesap", "Gece Mod", "Gece Değer", "Gece Not",
    "Ek Özel Tip", "Ek Özel Mod", "Ek Özel Değer", "Ek Özel Not",
    "Denge Aktif", "Denge Oran",
    "Sosyal Zam Pct",
    "Zam JSON",
    "Ana Maaş (Brüt)", "Sosyal Paket", "Toplam Maliyet"
]

# ============================================================
# VARSAYILAN DEĞERLER
# ============================================================
DEFAULTS = {
    "s_isyeri": "", "s_isyeri_tipi": "İşyeri", "s_grev": "Grev Yasağı Yok",
    "s_yabanci": False, "s_ulke": "Türkiye", "s_isv_sendika": "İşveren Sendikası Yok",
    "s_sektor": "Özel", "s_grup": "Petrol", "s_subeler": [],
    "s_uye": 0, "s_calisan": 0,
    "s_tis_bas": datetime.now().date(),
    "s_tis_bit": datetime.now().replace(year=datetime.now().year + 2).date(),
    "s_zam_verileri": [],
    "s_u_tipi": "Net", "s_u_tutar": 20000.0,
    "s_ek1_mod": "Maktu", "s_ek1_val": 0.0, "s_ek1_per": "Aylık",
    "s_ek1_tip": "Net", "s_ek1_zam": 0.0,
    "s_ek2_mod": "Maktu", "s_ek2_val": 0.0, "s_ek2_per": "Aylık",
    "s_ek2_tip": "Net", "s_ek2_zam": 0.0,
    # Gıda
    "s_gida_tip": "Net", "s_gida_val": 0.0, "s_gida_per": "Aylık", "s_gida_not": "",
    # Yakacak
    "s_yakacak_mod": "Maktu", "s_yakacak_kdv": "KDV Dahil Değil",
    "s_yakacak_tip": "Net", "s_yakacak_val": 0.0, "s_yakacak_m3": 0.0, "s_yakacak_birim": 0.0,
    "s_yakacak_per": "Yıllık", "s_yakacak_not": "",
    # Giyim
    "s_giyim_tip": "Net", "s_giyim_val": 0.0, "s_giyim_per": "Yıllık", "s_giyim_not": "",
    # Ayakkabı
    "s_ayakkabi_tip": "Net", "s_ayakkabi_val": 0.0, "s_ayakkabi_per": "Yıllık", "s_ayakkabi_not": "",
    # Yılbaşı
    "s_yilbasi_tip": "Net", "s_yilbasi_val": 0.0, "s_yilbasi_per": "Yıllık", "s_yilbasi_not": "",
    # İzin
    "s_iz_m": "Maktu", "s_iz_t": "Net", "s_iz_v": 0.0, "s_iz_per": "Yıllık", "s_iz_not": "",
    # Bayram
    "s_ba_m": "Maktu", "s_ba_t": "Net", "s_ba_v": 0.0, "s_ba_per": "Yıllık", "s_ba_not": "",
    # Prim
    "s_pr_m": "Maktu", "s_pr_t": "Net", "s_pr_v": 0.0, "s_pr_per": "Aylık", "s_pr_not": "",
    # İkramiye
    "s_ikramiye": 0, "s_ikramiye_not": "",
    # Aile & Çocuk
    "s_yasal_aile": False, "s_yasal_aile_pct": 100.0,
    "s_muaf_aile": False, "s_muaf_aile_pct": 100.0,
    "s_maktu_aile": 0.0, "s_aile_not": "",
    "s_yasal_cocuk": False, "s_yasal_cocuk_pct": 100.0,
    "s_muaf_cocuk": False, "s_muaf_cocuk_pct": 100.0,
    "s_maktu_cocuk": 0.0, "s_cocuk_not": "",
    # Vardiya
    "s_v_hesap": "Sabit", "s_v_mod": "Maktu", "s_v_val": 0.0, "s_v_not": "",
    # Gece
    "s_g_hesap": "Sabit", "s_g_mod": "Maktu", "s_g_val": 0.0, "s_g_not": "",
    # Ek özel
    "s_eo_tip": "Günlük Ücret", "s_eo_mod": "Katsayı", "s_eo_val": 0.0, "s_eo_not": "",
    # Denge
    "s_denge": False, "s_denge_oran": 11.0,
    # Toplu sosyal zam
    "s_sosyal_zam_pct": 0.0,
    # Bireysel sosyal artış oranları (%)
    "s_gida_zam": 0.0,
    "s_yakacak_zam": 0.0,
    "s_giyim_zam": 0.0,
    "s_ayakkabi_zam": 0.0,
    "s_yilbasi_zam": 0.0,
    "s_iz_zam": 0.0,
    "s_ba_zam": 0.0,
    "s_pr_zam": 0.0,
    "s_ikramiye_zam": 0.0,
}

# ============================================================
# KULLANICI YÖNETİMİ
# ============================================================
def get_users():
    try: return st.secrets["users"]
    except: return {}

def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
        st.session_state["active_user"] = None
    if st.session_state["password_correct"]: return True
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
# SESSION STATE
# ============================================================
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def sifirla():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    # Zam dönem widget key'lerini de temizle
    for k in list(st.session_state.keys()):
        if any(k.startswith(p) for p in ["z_yil_","z_ay_","z_not_","h_tipi_","z_uygula_",
                                           "k_sayisi_","k_tip_","k_val_","k_kidem_","k_ort_kidem_",
                                           "n_donem_sayisi"]):
            del st.session_state[k]

# ============================================================
# KAYIT YÜKLE
# ============================================================
def yukle_kayit(r):
    def rv(col, default=""):
        val = r.get(col, ""); return val if (val != "" and val is not None) else default
    def rf(col, default=0.0):
        try:
            val = str(r.get(col, "")).strip().replace(",", ".")
            return float(val) if val not in ("", "None") else float(default)
        except: return float(default)
    def ri(col, default=0):
        try:
            val = str(r.get(col, "")).strip()
            return int(float(val)) if val not in ("", "None") else int(default)
        except: return int(default)
    def rs(col, choices, default):
        val = rv(col, default); return val if val in choices else default

    st.session_state["s_isyeri"]      = rv("İşyeri")
    st.session_state["s_isyeri_tipi"] = rs("İşyeri Tipi", ["İşyeri", "İşletme"], "İşyeri")
    st.session_state["s_grev"]        = rs("Grev Durumu", ["Grev Yasağı Yok", "Grev Yasağı Var"], "Grev Yasağı Yok")
    st.session_state["s_yabanci"]     = rv("Yabancı Ortak", "False") == "True"
    st.session_state["s_ulke"]        = rs("Ortak Ülke", ULKELER, "Türkiye")
    st.session_state["s_isv_sendika"] = rs("İşveren Sendikası", ISV_SENDIKALARI, "İşveren Sendikası Yok")
    st.session_state["s_sektor"]      = rs("Sektör", SEKTORLER, "Özel")
    st.session_state["s_grup"]        = rs("Grup", GRUPLAR, "Petrol")
    try:
        sub_str = rv("Şubeler", "")
        st.session_state["s_subeler"] = [s.strip() for s in sub_str.split(",") if s.strip()]
    except: st.session_state["s_subeler"] = []
    st.session_state["s_uye"]     = ri("Üye Sayısı")
    st.session_state["s_calisan"] = ri("Toplam Çalışan")
    try:
        bas = rv("TİS Başlangıç"); bit = rv("TİS Bitiş")
        if bas: st.session_state["s_tis_bas"] = datetime.strptime(bas, "%d/%m/%Y").date()
        if bit: st.session_state["s_tis_bit"] = datetime.strptime(bit, "%d/%m/%Y").date()
    except: pass
    st.session_state["s_u_tipi"]  = rs("Ana Maaş Tipi", ["Net", "Brüt"], "Net")
    st.session_state["s_u_tutar"] = rf("Ana Maaş Tutar", 20000.0)
    st.session_state["s_ek1_mod"] = rs("Ek Ödeme 1 Mod", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"], "Maktu")
    st.session_state["s_ek1_val"] = rf("Ek Ödeme 1 Değer")
    st.session_state["s_ek1_per"] = rs("Ek Ödeme 1 Periyot", ["Aylık", "Yıllık"], "Aylık")
    st.session_state["s_ek1_tip"] = rs("Ek Ödeme 1 Tip", ["Net", "Brüt"], "Net")
    st.session_state["s_ek1_zam"] = rf("Ek Ödeme 1 Zam", 0.0)
    st.session_state["s_ek2_mod"] = rs("Ek Ödeme 2 Mod", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"], "Maktu")
    st.session_state["s_ek2_val"] = rf("Ek Ödeme 2 Değer")
    st.session_state["s_ek2_per"] = rs("Ek Ödeme 2 Periyot", ["Aylık", "Yıllık"], "Aylık")
    st.session_state["s_ek2_tip"] = rs("Ek Ödeme 2 Tip", ["Net", "Brüt"], "Net")
    st.session_state["s_ek2_zam"] = rf("Ek Ödeme 2 Zam", 0.0)
    # Gıda
    st.session_state["s_gida_tip"] = rs("Gıda Tip", ["Net", "Brüt"], "Net")
    st.session_state["s_gida_val"] = rf("Gıda Tutar")
    st.session_state["s_gida_per"] = rs("Gıda Periyot", ["Aylık", "Yıllık"], "Aylık")
    st.session_state["s_gida_not"] = rv("Gıda Not")
    # Yakacak
    st.session_state["s_yakacak_tip"] = rs("Yakacak Tip", ["Net", "Brüt"], "Net")
    st.session_state["s_yakacak_mod"]   = rs("Yakacak Mod", ["Maktu", "Metreküp"], "Maktu")
    st.session_state["s_yakacak_kdv"]   = rs("Yakacak KDV", ["KDV Dahil Değil", "KDV Dahil"], "KDV Dahil Değil")
    st.session_state["s_yakacak_val"]   = rf("Yakacak Tutar")
    st.session_state["s_yakacak_m3"]    = rf("Yakacak M3")
    st.session_state["s_yakacak_birim"] = rf("Yakacak Birim")
    st.session_state["s_yakacak_per"]   = rs("Yakacak Periyot", ["Aylık", "Yıllık"], "Yıllık")
    st.session_state["s_yakacak_not"]   = rv("Yakacak Not")
    # Giyim
    st.session_state["s_giyim_tip"] = rs("Giyim Tip", ["Net", "Brüt"], "Net")
    st.session_state["s_giyim_val"] = rf("Giyim Tutar")
    st.session_state["s_giyim_per"] = rs("Giyim Periyot", ["Aylık", "Yıllık"], "Yıllık")
    st.session_state["s_giyim_not"] = rv("Giyim Not")
    # Ayakkabı
    st.session_state["s_ayakkabi_tip"] = rs("Ayakkabı Tip", ["Net", "Brüt"], "Net")
    st.session_state["s_ayakkabi_val"] = rf("Ayakkabı Tutar")
    st.session_state["s_ayakkabi_per"] = rs("Ayakkabı Periyot", ["Aylık", "Yıllık"], "Yıllık")
    st.session_state["s_ayakkabi_not"] = rv("Ayakkabı Not")
    # Yılbaşı
    st.session_state["s_yilbasi_tip"] = rs("Yılbaşı Tip", ["Net", "Brüt"], "Net")
    st.session_state["s_yilbasi_val"] = rf("Yılbaşı Tutar")
    st.session_state["s_yilbasi_per"] = rs("Yılbaşı Periyot", ["Aylık", "Yıllık"], "Yıllık")
    st.session_state["s_yilbasi_not"] = rv("Yılbaşı Not")
    # İzin
    st.session_state["s_iz_m"]   = rs("İzin Mod", ["Maktu", "Katsayı (Gün)"], "Maktu")
    st.session_state["s_iz_t"]   = rs("İzin Tip", ["Net", "Brüt"], "Net")
    st.session_state["s_iz_v"]   = rf("İzin Değer")
    st.session_state["s_iz_per"] = rs("İzin Periyot", ["Aylık", "Yıllık"], "Yıllık")
    st.session_state["s_iz_not"] = rv("İzin Not")
    # Bayram
    st.session_state["s_ba_m"]   = rs("Bayram Mod", ["Maktu", "Katsayı (Gün)"], "Maktu")
    st.session_state["s_ba_t"]   = rs("Bayram Tip", ["Net", "Brüt"], "Net")
    st.session_state["s_ba_v"]   = rf("Bayram Değer")
    st.session_state["s_ba_per"] = rs("Bayram Periyot", ["Aylık", "Yıllık"], "Yıllık")
    st.session_state["s_ba_not"] = rv("Bayram Not")
    # Prim
    st.session_state["s_pr_m"]   = rs("Prim Mod", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"], "Maktu")
    st.session_state["s_pr_t"]   = rs("Prim Tip", ["Net", "Brüt"], "Net")
    st.session_state["s_pr_v"]   = rf("Prim Değer")
    st.session_state["s_pr_per"] = rs("Prim Periyot", ["Aylık", "Yıllık"], "Aylık")
    st.session_state["s_pr_not"] = rv("Prim Not")
    # İkramiye
    st.session_state["s_ikramiye"]     = ri("İkramiye Günü")
    st.session_state["s_ikramiye_not"] = rv("İkramiye Not")
    # Aile & Çocuk
    st.session_state["s_yasal_aile"]      = rv("Yasal Aile", "False") == "True"
    st.session_state["s_yasal_aile_pct"]  = rf("Yasal Aile Pct", 100.0)
    st.session_state["s_muaf_aile"]       = rv("Muafiyet Aile", "False") == "True"
    st.session_state["s_muaf_aile_pct"]   = rf("Muafiyet Aile Pct", 100.0)
    st.session_state["s_maktu_aile"]      = rf("Maktu Aile")
    st.session_state["s_aile_not"]        = rv("Aile Not")
    st.session_state["s_yasal_cocuk"]     = rv("Yasal Çocuk", "False") == "True"
    st.session_state["s_yasal_cocuk_pct"] = rf("Yasal Çocuk Pct", 100.0)
    st.session_state["s_muaf_cocuk"]      = rv("Muafiyet Çocuk", "False") == "True"
    st.session_state["s_muaf_cocuk_pct"]  = rf("Muafiyet Çocuk Pct", 100.0)
    st.session_state["s_maktu_cocuk"]     = rf("Maktu Çocuk Birim")
    st.session_state["s_cocuk_not"]       = rv("Çocuk Not")
    # Vardiya, Gece, Ek özel
    st.session_state["s_v_hesap"] = rs("Vardiya Hesap", ["Sabit", "Fiili (195/225)"], "Sabit")
    st.session_state["s_v_mod"]   = rs("Vardiya Mod", ["Maktu", "Yüzde (%)"], "Maktu")
    st.session_state["s_v_val"]   = rf("Vardiya Değer")
    st.session_state["s_v_not"]   = rv("Vardiya Not")
    st.session_state["s_g_hesap"] = rs("Gece Hesap", ["Sabit", "Fiili (80/225)"], "Sabit")
    st.session_state["s_g_mod"]   = rs("Gece Mod", ["Maktu", "Yüzde (%)"], "Maktu")
    st.session_state["s_g_val"]   = rf("Gece Değer")
    st.session_state["s_g_not"]   = rv("Gece Not")
    st.session_state["s_eo_tip"]  = rs("Ek Özel Tip", ["Günlük Ücret", "Aylık Ücret"], "Günlük Ücret")
    st.session_state["s_eo_mod"]  = rs("Ek Özel Mod", ["Katsayı", "Yüzde (%)"], "Katsayı")
    st.session_state["s_eo_val"]  = rf("Ek Özel Değer")
    st.session_state["s_eo_not"]  = rv("Ek Özel Not")
    st.session_state["s_denge"]      = rv("Denge Aktif", "False") == "True"
    st.session_state["s_denge_oran"] = rf("Denge Oran", 11.0)
    st.session_state["s_sosyal_zam_pct"] = rf("Sosyal Zam Pct", 0.0)
    # Bireysel artış oranları (eski kayıtlarda yoksa 0)
    st.session_state["s_gida_zam"]     = rf("Gida Zam",     0.0)
    st.session_state["s_yakacak_zam"]  = rf("Yakacak Zam",  0.0)
    st.session_state["s_giyim_zam"]    = rf("Giyim Zam",    0.0)
    st.session_state["s_ayakkabi_zam"] = rf("Ayakkabi Zam", 0.0)
    st.session_state["s_yilbasi_zam"]  = rf("Yilbasi Zam",  0.0)
    st.session_state["s_iz_zam"]       = rf("Iz Zam",       0.0)
    st.session_state["s_ba_zam"]       = rf("Ba Zam",       0.0)
    st.session_state["s_pr_zam"]       = rf("Pr Zam",       0.0)
    st.session_state["s_ikramiye_zam"] = rf("Ikramiye Zam", 0.0)
    # Zam verilerini JSON'dan yükle
    try:
        zam_json = rv("Zam JSON", "[]")
        zam_data = json.loads(zam_json) if zam_json else []
        st.session_state["s_zam_verileri"] = zam_data if isinstance(zam_data, list) else []
    except:
        st.session_state["s_zam_verileri"] = []

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

def ayliklandir(tutar, periyot):
    """Yıllık tutarı aylığa çevirir, aylık ise dokunmaz."""
    return tutar / 12 if periyot == "Yıllık" else tutar

def sf(val):
    try: return f"{float(val):.4f}"
    except: return "0.0000"

def zam_planini_uygula(baslangic_maas, zam_listesi):
    bugun  = datetime.now().date()
    guncel = float(baslangic_maas)
    for donem in zam_listesi:
        if not donem.get("uygula", False): continue
        try:
            zam_tarihi = datetime(int(donem["yil"]), AY_MAP[donem["ay"]], 1).date()
        except: continue
        if zam_tarihi > bugun: continue
        hesap_tipi = donem.get("hesap_tipi", "Birbirine Bağlı (Bileşik)")
        if hesap_tipi == "Birbirine Bağlı (Bileşik)":
            gecici = guncel
            for kalem in donem.get("kalemler", []):
                ort_kidem = kalem.get("ort_kidem", 1.0) if kalem.get("kidemli", False) else 1.0
                etkili = kalem["deger"] * ort_kidem
                gecici = gecici * (1 + etkili/100) if kalem["tip"] == "Yüzde (%)" else gecici + etkili
            guncel = gecici
        else:
            artis = 0.0
            for kalem in donem.get("kalemler", []):
                ort_kidem = kalem.get("ort_kidem", 1.0) if kalem.get("kidemli", False) else 1.0
                etkili = kalem["deger"] * ort_kidem
                artis += guncel * (etkili/100) if kalem["tip"] == "Yüzde (%)" else etkili
            guncel += artis
    return guncel

def yakacak_hesapla():
    """Yakacak ödentisini brüt TL olarak döndürür (aylık)."""
    mod = st.session_state["s_yakacak_mod"]
    per = st.session_state["s_yakacak_per"]
    tip = st.session_state["s_yakacak_tip"]

    if mod == "Maktu":
        val = yardim_brutlestir(
            st.session_state["s_yakacak_val"],
            tip,
            secilen_oran
        )
    else:
        m3    = st.session_state["s_yakacak_m3"]
        birim = st.session_state["s_yakacak_birim"]
        kdv   = st.session_state["s_yakacak_kdv"]

        tutar = m3 * birim
        if kdv == "KDV Dahil Değil":
            tutar *= 1.20

        val = yardim_brutlestir(
            tutar,
            tip,
            secilen_oran
        )

    return ayliklandir(val, per)

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
        sheet  = client.open_by_key(SHEET_KEY).sheet1
        # Başlık uyuşmazlığında graceful fallback
        try:
            data = sheet.get_all_records(expected_headers=SHEET_HEADERS, head=1)
        except Exception:
            all_vals = sheet.get_all_values()
            if len(all_vals) < 2:
                return pd.DataFrame()
            headers = all_vals[0]
            rows    = all_vals[1:]
            data    = [dict(zip(headers, row)) for row in rows]
        df = pd.DataFrame(data)
        # Eksik yeni sütunları boş string ile tamamla
        for col in SHEET_HEADERS:
            if col not in df.columns:
                df[col] = ""
        return df
    except Exception as e:
        st.error(f"Veri çekilemedi: {e}"); return pd.DataFrame()

def baslik_guncelle(sheet):
    """Veriyi koruyarak başlık satırını günceller."""
    try:
        mevcut = sheet.row_values(1)
        if mevcut == SHEET_HEADERS:
            return
        sheet.delete_rows(1)
        sheet.insert_row(SHEET_HEADERS, 1)
    except Exception as e:
        st.warning(f"Başlık güncellenemedi: {e}")

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown(f"### 👤 {st.session_state['active_user']}")
    if st.button("🚪 Güvenli Çıkış"):
        for k in list(st.session_state.keys()):
            if k not in {"password_correct", "active_user"}: del st.session_state[k]
        st.session_state["password_correct"] = False; st.rerun()

    st.divider()
    st.header("⚙️ Genel Ayarlar")
    asgari_ucret = st.number_input("Asgari Ücret (Brüt)", value=33030.00)
    oran_map = {0.71491: "%15 Vergi", 0.67241: "%20 Vergi", 0.61291: "%27 Vergi", 0.54491: "%35 Vergi"}
    secilen_oran = st.radio("📉 Vergi Dilimi", options=list(oran_map.keys()),
                            format_func=lambda x: oran_map[x], index=1)
    st.subheader("⚖️ Yasal Yardımlar")
    aile_yasal_sabit = st.number_input("657 Aile Yardımı", value=3154.63)
    cocuk_6_ustu     = st.number_input("657 Çocuk (6+)",   value=346.97)
    cocuk_0_6        = st.number_input("657 Çocuk (0-6)",  value=693.94)
    muafiyet_aile    = asgari_ucret * 0.10
    muafiyet_cocuk   = (asgari_ucret * 0.02) * 2
    st.info(f"Muafiyet Aile: {muafiyet_aile:,.2f} TL\nMuafiyet Çocuk(2): {muafiyet_cocuk:,.2f} TL")

# ============================================================
# SEKMELER
# ============================================================
tab1, tab2, tab3 = st.tabs(["🏢 İşyeri Bilgileri", "💰 Ücret ve Sosyal Ödemeler", "📊 Karşılaştırma ve İstatistik"])

# ============================================================
# TAB 1
# ============================================================
with tab1:
    st.header("🏢 İşyeri Bilgileri")
    df = verileri_getir()

    if st.button("➕ Yeni Kayıt"):
        sifirla(); st.rerun()

    with st.expander("📂 Kayıtlı Veriyi Çağır", expanded=not df.empty):
        if not df.empty:
            isyeri_listesi = [i for i in df["İşyeri"].dropna().unique().tolist() if i != ""]
            if isyeri_listesi:
                sec = st.selectbox("İşyeri Seç", isyeri_listesi)
                if st.button("📥 Verileri Yükle"):
                    r = df[df["İşyeri"] == sec].iloc[0].to_dict()
                    yukle_kayit(r); st.success(f"✅ {sec} yüklendi!"); st.rerun()
        st.subheader("📋 Kayıtlı İşyerleri")
        if not df.empty:
            goster = [c for c in ["İşyeri","Sektör","Grup","Şubeler","TİS Başlangıç","TİS Bitiş","Toplam Maliyet"] if c in df.columns]
            st.dataframe(df[goster], use_container_width=True)
        else: st.info("Henüz kayıt yok.")

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("🏭 Temel Bilgiler")
        st.text_input("İşyeri / İşletme Adı", key="s_isyeri")
        st.radio("Tipi", ["İşyeri", "İşletme"], key="s_isyeri_tipi", horizontal=True)
        st.selectbox("Grev Yasağı", ["Grev Yasağı Yok", "Grev Yasağı Var"], key="s_grev")
        st.subheader("🌍 Ortaklık Bilgisi")
        st.checkbox("Yabancı Ortaklı", key="s_yabanci")
        if st.session_state["s_yabanci"]:
            st.selectbox("Ortak Ülke", ULKELER, key="s_ulke")
        else:
            st.session_state["s_ulke"] = "Türkiye"
        st.selectbox("İşveren Sendikası", ISV_SENDIKALARI, key="s_isv_sendika")
        st.subheader("🏷️ Sektör / Grup")
        st.radio("Sektör", SEKTORLER, key="s_sektor", horizontal=True)
        st.selectbox("Grup", GRUPLAR, key="s_grup")
        st.multiselect("Bağlı Şubeler", SUBELER, key="s_subeler")
    with col_b:
        st.subheader("👥 Üye / Çalışan")
        st.number_input("Sendikalı Üye Sayısı", min_value=0, key="s_uye")
        st.number_input("Toplam Çalışan Sayısı", min_value=0, key="s_calisan")
        st.subheader("📅 TİS Dönemi")
        st.date_input("Başlangıç Tarihi", key="s_tis_bas")
        st.date_input("Bitiş Tarihi", key="s_tis_bit")
        bugun = datetime.now().date()
        bas_d = st.session_state["s_tis_bas"]; bit_d = st.session_state["s_tis_bit"]
        kalan = max((bit_d - bugun).days, 0); toplam_gun = (bit_d - bas_d).days
        yuzde = min(max(((toplam_gun-kalan)/toplam_gun)*100, 0), 100) if toplam_gun > 0 else 0
        st.progress(yuzde / 100); st.caption(f"Kalan: {kalan} gün")
        if kalan <= 0: st.error("❌ Sözleşme süresi doldu!")
        elif kalan <= 120: st.error("🚨 Yetki başvuru süresi başladı!")
        elif kalan <= 365: st.warning("⚠️ Son yılındasınız.")
        else:
            fark = toplam_gun + 1
            if fark < 365: st.warning(f"⚠️ TİS 1 yıldan az ({fark} gün)")
            elif fark > 1095: st.error("❌ TİS 3 yıldan fazla")
            else: st.success(f"✅ {round(fark/365,1)} yıl ({fark} gün)")

    # ZAM PLANLAMA
    st.divider()
    st.subheader("📈 Dinamik Zam Planlaması")
    st.caption("Sözleşme boyunca uygulanacak her zam dönemini ayrı ayrı tanımlayın.")
    # Zam dönem sayısını s_zam_verileri'nden başlat
    _mevcut_zam_sayisi = len(st.session_state.get("s_zam_verileri", []))
    _baslangic_sayi = max(_mevcut_zam_sayisi, 1) if _mevcut_zam_sayisi > 0 else 2
    zam_donem_sayisi = st.number_input("Kaç Farklı Zam Dönemi Var?", min_value=1, max_value=12,
                                        value=_baslangic_sayi, key="n_donem_sayisi")
    _kayitli = st.session_state.get("s_zam_verileri", [])
    yeni_zamlar = []
    for i in range(int(zam_donem_sayisi)):
        # Kayıtlı veriden varsayılanları al
        _d = _kayitli[i] if i < len(_kayitli) else {}
        _d_yil  = _d.get("yil", 2026)
        _d_ay   = _d.get("ay", AYLAR[0])
        _d_not  = _d.get("not", "")
        _d_htip = _d.get("hesap_tipi", "Birbirine Bağlı (Bileşik)")
        _d_uygula = _d.get("uygula", False)
        _d_kalemler = _d.get("kalemler", [{}])
        _d_ksayi = max(len(_d_kalemler), 1)

        # Widget key'lerini session_state'e pre-populate et
        if f"z_yil_{i}" not in st.session_state:   st.session_state[f"z_yil_{i}"]   = _d_yil
        if f"z_ay_{i}" not in st.session_state:    st.session_state[f"z_ay_{i}"]    = _d_ay
        if f"z_not_{i}" not in st.session_state:   st.session_state[f"z_not_{i}"]   = _d_not
        if f"h_tipi_{i}" not in st.session_state:  st.session_state[f"h_tipi_{i}"]  = _d_htip
        if f"z_uygula_{i}" not in st.session_state: st.session_state[f"z_uygula_{i}"] = _d_uygula
        if f"k_sayisi_{i}" not in st.session_state: st.session_state[f"k_sayisi_{i}"] = _d_ksayi
        for j, _k in enumerate(_d_kalemler):
            if f"k_tip_{i}_{j}" not in st.session_state:
                st.session_state[f"k_tip_{i}_{j}"] = _k.get("tip", "Yüzde (%)")
            if f"k_val_{i}_{j}" not in st.session_state:
                st.session_state[f"k_val_{i}_{j}"] = float(_k.get("deger", 0.0))
            if f"k_kidem_{i}_{j}" not in st.session_state:
                st.session_state[f"k_kidem_{i}_{j}"] = "Kıdeme Bağlı" if _k.get("kidemli") else "Sabit"
            if f"k_ort_kidem_{i}_{j}" not in st.session_state:
                st.session_state[f"k_ort_kidem_{i}_{j}"] = float(_k.get("ort_kidem", 10.0))

        with st.container(border=True):
            hd1, hd2 = st.columns([3, 1])
            with hd1: st.markdown(f"**{i+1}. Zam Dönemi**")
            with hd2: z_uygula = st.checkbox("✅ Hesaba Kat", key=f"z_uygula_{i}",
                                              help="Bu zammı maaş hesabına dahil etmek için işaretleyin.")
            ct1, ct2, ct3 = st.columns([1,1,2])
            with ct1: z_yil = st.selectbox("Yıl", [2024,2025,2026,2027,2028], key=f"z_yil_{i}")
            with ct2: z_ay  = st.selectbox("Ay", AYLAR, key=f"z_ay_{i}")
            with ct3: z_not = st.text_input("Not", placeholder="örn: 1. Yıl 1. Altı Ay", key=f"z_not_{i}")
            hesap_tipi = st.radio("Uygulama Biçimi",
                ["Birbirine Bağlı (Bileşik)", "Ana Ücrete Ayrı Ayrı (Toplamsal)"],
                key=f"h_tipi_{i}", horizontal=True)
            kalem_sayisi = st.number_input("Zam Kalemi Sayısı", min_value=1, max_value=5, key=f"k_sayisi_{i}")
            donem_kalemleri = []
            for j in range(int(kalem_sayisi)):
                if f"k_tip_{i}_{j}" not in st.session_state:   st.session_state[f"k_tip_{i}_{j}"]   = "Yüzde (%)"
                if f"k_val_{i}_{j}" not in st.session_state:   st.session_state[f"k_val_{i}_{j}"]   = 0.0
                if f"k_kidem_{i}_{j}" not in st.session_state: st.session_state[f"k_kidem_{i}_{j}"] = "Sabit"
                ck1, ck2, ck3, ck4 = st.columns([1.5,2,1.5,1.5])
                with ck1: k_tip   = st.selectbox("Tip", ["Yüzde (%)", "Maktu (TL)"], key=f"k_tip_{i}_{j}")
                with ck2: k_val   = st.number_input("Tutar / Oran", min_value=0.0, step=0.1, key=f"k_val_{i}_{j}")
                with ck3: k_kidem = st.selectbox("Kapsam", ["Sabit", "Kıdeme Bağlı"], key=f"k_kidem_{i}_{j}")
                with ck4:
                    k_ort_kidem = 1.0
                    if k_kidem == "Kıdeme Bağlı":
                        if f"k_ort_kidem_{i}_{j}" not in st.session_state:
                            st.session_state[f"k_ort_kidem_{i}_{j}"] = 10.0
                        k_ort_kidem = st.number_input("Ort. Kıdem (Yıl)", min_value=0.0, key=f"k_ort_kidem_{i}_{j}")
                donem_kalemleri.append({"tip": k_tip, "deger": k_val,
                                        "kidemli": k_kidem=="Kıdeme Bağlı", "ort_kidem": k_ort_kidem})
            yeni_zamlar.append({"yil": z_yil, "ay": z_ay, "not": z_not,
                                 "hesap_tipi": hesap_tipi, "kalemler": donem_kalemleri, "uygula": z_uygula})
    st.session_state["s_zam_verileri"] = yeni_zamlar
    if yeni_zamlar:
        st.markdown("**📋 Zam Planı Özeti**")
        for d in yeni_zamlar:
            kalem_str = ", ".join([f"%{k['deger']}" if k['tip']=="Yüzde (%)" else f"{k['deger']:.0f} TL" for k in d["kalemler"]])
            not_str = f" — {d['not']}" if d['not'] else ""
            durum   = "✅ uygulanıyor" if d["uygula"] else "📋 kayıtlı"
            st.caption(f"• {d['ay']} {d['yil']}: {kalem_str}{not_str} — {durum}")

# ============================================================
# TAB 2
# ============================================================
with tab2:
    st.header("💰 Ücret ve Ek Ödemeler")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.radio("Ücret Tipi", ["Net", "Brüt"], key="s_u_tipi")
        st.number_input("Çıplak Ücret (Girilen Değer)", min_value=0.0, key="s_u_tutar")
    with c2:
        with st.container(border=True):
            ek1h1, ek1h2 = st.columns([3,1])
            with ek1h1: st.caption("💼 Ek Ödeme 1")
            with ek1h2: st.selectbox("", ["Aylık","Yıllık"], key="s_ek1_per", label_visibility="collapsed")
            st.selectbox("Mod", ["Maktu","Katsayı (Gün)","Yüzde (%)"], key="s_ek1_mod")
            ek1r1, ek1r2 = st.columns([2,1])
            with ek1r1: st.radio("", ["Net","Brüt"], horizontal=True, key="s_ek1_tip")
            with ek1r2: st.number_input("+%", min_value=0.0, max_value=500.0, step=0.5,
                                         key="s_ek1_zam", help="Ek Ödeme 1'e özel artış")
            st.number_input("Değer", min_value=0.0, key="s_ek1_val")
    with c3:
        with st.container(border=True):
            ek2h1, ek2h2 = st.columns([3,1])
            with ek2h1: st.caption("💼 Ek Ödeme 2")
            with ek2h2: st.selectbox("", ["Aylık","Yıllık"], key="s_ek2_per", label_visibility="collapsed")
            st.selectbox("Mod", ["Maktu","Katsayı (Gün)","Yüzde (%)"], key="s_ek2_mod")
            ek2r1, ek2r2 = st.columns([2,1])
            with ek2r1: st.radio("", ["Net","Brüt"], horizontal=True, key="s_ek2_tip")
            with ek2r2: st.number_input("+%", min_value=0.0, max_value=500.0, step=0.5,
                                         key="s_ek2_zam", help="Ek Ödeme 2'ye özel artış")
            st.number_input("Değer", min_value=0.0, key="s_ek2_val")

    maas_base   = maas_brutlestir(st.session_state["s_u_tutar"], st.session_state["s_u_tipi"], secilen_oran)
    zam_listesi = st.session_state.get("s_zam_verileri", [])
    a_brut      = zam_planini_uygula(maas_base, zam_listesi)
    g_brut      = a_brut / 30

    uygulanan = [d for d in zam_listesi if d.get("uygula", False)]
    if zam_listesi:
        if uygulanan:
            st.info(f"📊 {len(uygulanan)} zam uygulandı → Ana Maaş: **{a_brut:,.2f} TL** (Girilen: {maas_base:,.2f} TL)")
        else:
            st.warning(f"📋 {len(zam_listesi)} zam kayıtlı, hiçbiri işaretlenmemiş → **{a_brut:,.2f} TL**")

    # ── TOPLU SOSYAL ZAM ──────────────────────────────────────
    st.divider()
    with st.container(border=True):
        st.markdown("### 🔁 Toplu Sosyal Ödeme Artışı")
        zc1, zc2 = st.columns([2,3])
        with zc1:
            st.number_input("Tüm Sosyal Ödemelere Uygulanacak Artış (%)",
                            min_value=0.0, max_value=500.0, step=0.5, key="s_sosyal_zam_pct",
                            help="0 girerseniz artış uygulanmaz. Bireysel tutarlar zaten girilmişse bu oran üstüne eklenir.")
        with zc2:
            zam_carpan = 1 + st.session_state["s_sosyal_zam_pct"] / 100
            st.info(f"Çarpan: ×{zam_carpan:.4f}  — Sosyal tutarlar bu çarpanla artırılır.")

    st.markdown("### 🎁 Sosyal Yardımlar")

    # ── YARDIMCI: başlık + periyot + bireysel artış + not ────
    def sosyal_baslik(etiket, per_key, not_key, zam_key=None):
        r1, r2, r3, r4 = st.columns([2, 1, 1, 2])
        with r1: st.write(etiket)
        with r2: st.selectbox("Periyot", ["Aylık", "Yıllık"], key=per_key, label_visibility="collapsed")
        with r3:
            if zam_key:
                st.number_input("+%", min_value=0.0, max_value=500.0, step=0.5,
                                key=zam_key, label_visibility="collapsed",
                                help="Bu kaleme özel artış oranı (%)")
        with r4: st.text_input("Açıklama", key=not_key, placeholder="Not...", label_visibility="collapsed")

    def carpan(zam_key):
        """Toplu zam + bireysel zam çarpanını döndürür."""
        bireysel = st.session_state.get(zam_key, 0.0) if zam_key else 0.0
        return (1 + st.session_state["s_sosyal_zam_pct"] / 100) * (1 + bireysel / 100)

    def goster_artis(baz, son, etiket="Aylık brüt"):
        """Artış varsa baz ve son tutarı göster."""
        if abs(son - baz) > 0.01:
            st.caption(f"{etiket}: {baz:,.2f} → **{son:,.2f} TL**")
        else:
            st.caption(f"{etiket}: {son:,.2f} TL")

    # ─────────────────────────────────────────────────────────
    # YERLEŞİM: her kart tam genişlik, kontroller kart içinde
    # 2 sütun yan yana. Başlık satırı: etiket | periyot
    # Alt satır: tutar | +% bireysel | not
    # ─────────────────────────────────────────────────────────

    # 1. İKRAMİYE (tam genişlik)
    with st.container(border=True):
        hb1, hb2 = st.columns([3, 1])
        with hb1: st.markdown("💰 **İkramiye**")
        with hb2: st.caption("(yıllık gün)")
        ib1, ib2, ib3 = st.columns([2, 1, 2])
        with ib1: st.number_input("Yıllık İkramiye Günü", min_value=0, key="s_ikramiye")
        with ib2: st.number_input("+%", min_value=0.0, max_value=500.0, step=0.5,
                                   key="s_ikramiye_zam", label_visibility="visible",
                                   help="İkramiyeye özel artış")
        with ib3: st.text_input("Not", key="s_ikramiye_not", placeholder="Açıklama...")
        ik_baz = (g_brut * st.session_state["s_ikramiye"]) / 12
        ay_ikramiye = ik_baz * carpan("s_ikramiye_zam")
        goster_artis(ik_baz, ay_ikramiye, "Aylık ikramiye")

    # 2-3. İZİN + BAYRAM (yan yana)
    r23a, r23b = st.columns(2)
    with r23a:
        with st.container(border=True):
            h1, h2 = st.columns([3, 1])
            with h1: st.markdown("📅 **İzin Parası**")
            with h2: st.selectbox("", ["Yıllık","Aylık"], key="s_iz_per", label_visibility="collapsed")
            st.selectbox("Mod", ["Maktu","Katsayı (Gün)"], key="s_iz_m")
            c1,c2,c3 = st.columns([2,1,2])
            with c1: st.radio("", ["Net","Brüt"], horizontal=True, key="s_iz_t")
            with c2: st.number_input("+%", min_value=0.0, max_value=500.0, step=0.5,
                                     key="s_iz_zam", help="İzin parasına özel artış")
            with c3: st.text_input("Not", key="s_iz_not", placeholder="Açıklama...")
            st.number_input("Değer", min_value=0.0, key="s_iz_v")
            iz_ham  = yardim_brutlestir(calc_hybrid(st.session_state["s_iz_v"], st.session_state["s_iz_m"], g_brut),
                                        st.session_state["s_iz_t"], secilen_oran)
            iz_baz  = ayliklandir(iz_ham, st.session_state["s_iz_per"])
            ay_izin = iz_baz * carpan("s_iz_zam")
            goster_artis(iz_baz, ay_izin)
    with r23b:
        with st.container(border=True):
            h1, h2 = st.columns([3, 1])
            with h1: st.markdown("🎉 **Bayram Parası**")
            with h2: st.selectbox("", ["Yıllık","Aylık"], key="s_ba_per", label_visibility="collapsed")
            st.selectbox("Mod", ["Maktu","Katsayı (Gün)"], key="s_ba_m")
            c1,c2,c3 = st.columns([2,1,2])
            with c1: st.radio("", ["Net","Brüt"], horizontal=True, key="s_ba_t")
            with c2: st.number_input("+%", min_value=0.0, max_value=500.0, step=0.5,
                                     key="s_ba_zam", help="Bayram parasına özel artış")
            with c3: st.text_input("Not", key="s_ba_not", placeholder="Açıklama...")
            st.number_input("Değer", min_value=0.0, key="s_ba_v")
            ba_ham    = yardim_brutlestir(calc_hybrid(st.session_state["s_ba_v"], st.session_state["s_ba_m"], g_brut),
                                          st.session_state["s_ba_t"], secilen_oran)
            ba_baz    = ayliklandir(ba_ham, st.session_state["s_ba_per"])
            ay_bayram = ba_baz * carpan("s_ba_zam")
            goster_artis(ba_baz, ay_bayram)

    # 4. YAKACAK (tam genişlik — içeriği değişken)
    with st.container(border=True):
        yh1, yh2, yh3 = st.columns([3, 1, 1])
        with yh1: st.markdown("🔥 **Yakacak Parası**")
        with yh2: st.selectbox("", ["Yıllık","Aylık"], key="s_yakacak_per", label_visibility="collapsed")
        with yh3: st.selectbox("", ["Maktu","Metreküp"], key="s_yakacak_mod", label_visibility="collapsed")
        if st.session_state["s_yakacak_mod"] == "Maktu":
            yc1, yc2, yc3 = st.columns([2, 1, 2])
            with yc1:
                st.radio("", ["Net","Brüt"], horizontal=True, key="s_yakacak_tip")
                st.number_input("Tutar", min_value=0.0, key="s_yakacak_val")
            with yc2: st.number_input("+%", min_value=0.0, max_value=500.0, step=0.5,
                                       key="s_yakacak_zam", help="Yakacağa özel artış")
            with yc3: st.text_input("Not", key="s_yakacak_not", placeholder="Açıklama...")
        else:
            st.selectbox("KDV Durumu", ["KDV Dahil Değil","KDV Dahil"], key="s_yakacak_kdv")
            ym1, ym2, ym3, ym4 = st.columns([2, 2, 1, 2])
            with ym1: st.number_input("Metreküp", min_value=0.0, step=1.0, key="s_yakacak_m3")
            with ym2: st.number_input("Birim Fiyat (TL)", min_value=0.0, step=0.001, format="%.3f", key="s_yakacak_birim")
            with ym3: st.number_input("+%", min_value=0.0, max_value=500.0, step=0.5,
                                       key="s_yakacak_zam", help="Yakacağa özel artış")
            with ym4: st.text_input("Not", key="s_yakacak_not", placeholder="Açıklama...")
            net_tutar = st.session_state["s_yakacak_m3"] * st.session_state["s_yakacak_birim"]
            kdv_tutar = net_tutar * 1.20 if st.session_state["s_yakacak_kdv"] == "KDV Dahil Değil" else net_tutar
            st.info(f"Net: {net_tutar:,.2f} TL  →  KDV'li: {kdv_tutar:,.2f} TL")
            st.session_state["s_yakacak_val"] = kdv_tutar
        yak_baz = yakacak_hesapla()
        yakacak = yak_baz * carpan("s_yakacak_zam")
        goster_artis(yak_baz, yakacak)

    # 5-6. GİYİM + AYAKKABI (yan yana)
    r56a, r56b = st.columns(2)
    with r56a:
        with st.container(border=True):
            h1, h2 = st.columns([3, 1])
            with h1: st.markdown("👕 **Giyim Parası**")
            with h2: st.selectbox("", ["Yıllık","Aylık"], key="s_giyim_per", label_visibility="collapsed")
            st.radio("", ["Net","Brüt"], horizontal=True, key="s_giyim_tip")
            c1,c2,c3 = st.columns([2,1,2])
            with c1: st.number_input("Tutar", min_value=0.0, key="s_giyim_val")
            with c2: st.number_input("+%", min_value=0.0, max_value=500.0, step=0.5,
                                     key="s_giyim_zam", help="Giyime özel artış")
            with c3: st.text_input("Not", key="s_giyim_not", placeholder="Açıklama...")
            giyim_ham = yardim_brutlestir(st.session_state["s_giyim_val"], st.session_state["s_giyim_tip"], secilen_oran)
            giyim_baz = ayliklandir(giyim_ham, st.session_state["s_giyim_per"])
            giyim     = giyim_baz * carpan("s_giyim_zam")
            goster_artis(giyim_baz, giyim)
    with r56b:
        with st.container(border=True):
            h1, h2 = st.columns([3, 1])
            with h1: st.markdown("👟 **Ayakkabı Parası**")
            with h2: st.selectbox("", ["Yıllık","Aylık"], key="s_ayakkabi_per", label_visibility="collapsed")
            st.radio("", ["Net","Brüt"], horizontal=True, key="s_ayakkabi_tip")
            c1,c2,c3 = st.columns([2,1,2])
            with c1: st.number_input("Tutar", min_value=0.0, key="s_ayakkabi_val")
            with c2: st.number_input("+%", min_value=0.0, max_value=500.0, step=0.5,
                                     key="s_ayakkabi_zam", help="Ayakkabıya özel artış")
            with c3: st.text_input("Not", key="s_ayakkabi_not", placeholder="Açıklama...")
            ayakkabi_ham = yardim_brutlestir(st.session_state["s_ayakkabi_val"], st.session_state["s_ayakkabi_tip"], secilen_oran)
            ayakkabi_baz = ayliklandir(ayakkabi_ham, st.session_state["s_ayakkabi_per"])
            ayakkabi     = ayakkabi_baz * carpan("s_ayakkabi_zam")
            goster_artis(ayakkabi_baz, ayakkabi)

    # 7-8. GIDA + YILBAŞI (yan yana)
    r78a, r78b = st.columns(2)
    with r78a:
        with st.container(border=True):
            h1, h2 = st.columns([3, 1])
            with h1: st.markdown("🍞 **Gıda Parası**")
            with h2: st.selectbox("", ["Aylık","Yıllık"], key="s_gida_per", label_visibility="collapsed")
            st.radio("", ["Net","Brüt"], horizontal=True, key="s_gida_tip")
            c1,c2,c3 = st.columns([2,1,2])
            with c1: st.number_input("Tutar", min_value=0.0, key="s_gida_val")
            with c2: st.number_input("+%", min_value=0.0, max_value=500.0, step=0.5,
                                     key="s_gida_zam", help="Gıdaya özel artış")
            with c3: st.text_input("Not", key="s_gida_not", placeholder="Açıklama...")
            gida_ham = yardim_brutlestir(st.session_state["s_gida_val"], st.session_state["s_gida_tip"], secilen_oran)
            gida_baz = ayliklandir(gida_ham, st.session_state["s_gida_per"])
            gida     = gida_baz * carpan("s_gida_zam")
            goster_artis(gida_baz, gida)
    with r78b:
        with st.container(border=True):
            h1, h2 = st.columns([3, 1])
            with h1: st.markdown("🎁 **Yılbaşı Parası**")
            with h2: st.selectbox("", ["Yıllık","Aylık"], key="s_yilbasi_per", label_visibility="collapsed")
            st.radio("", ["Net","Brüt"], horizontal=True, key="s_yilbasi_tip")
            c1,c2,c3 = st.columns([2,1,2])
            with c1: st.number_input("Tutar", min_value=0.0, key="s_yilbasi_val")
            with c2: st.number_input("+%", min_value=0.0, max_value=500.0, step=0.5,
                                     key="s_yilbasi_zam", help="Yılbaşına özel artış")
            with c3: st.text_input("Not", key="s_yilbasi_not", placeholder="Açıklama...")
            yilbasi_ham = yardim_brutlestir(st.session_state["s_yilbasi_val"], st.session_state["s_yilbasi_tip"], secilen_oran)
            yilbasi_baz = ayliklandir(yilbasi_ham, st.session_state["s_yilbasi_per"])
            yilbasi     = yilbasi_baz * carpan("s_yilbasi_zam")
            goster_artis(yilbasi_baz, yilbasi)

    # 9-10. AİLE + ÇOCUK (yan yana)
    r910a, r910b = st.columns(2)
    with r910a:
        with st.container(border=True):
            st.markdown("👨‍👩‍👧 **Aile Yardımı**")
            al1, al2 = st.columns(2)
            with al1: st.checkbox("657 Aile Yardımı", key="s_yasal_aile")
            with al2:
                if st.session_state["s_yasal_aile"]:
                    st.number_input("Ödeme Oranı (%)", min_value=1.0, max_value=100.0,
                                    step=1.0, key="s_yasal_aile_pct", help="%100 = tam yasal tutar")
            al3, al4 = st.columns(2)
            with al3: st.checkbox("Muafiyet Aile", key="s_muaf_aile")
            with al4:
                if st.session_state["s_muaf_aile"]:
                    st.number_input("Ödeme Oranı (%)", min_value=1.0, max_value=100.0,
                                    step=1.0, key="s_muaf_aile_pct", help="%100 = tam muafiyet tutarı")
            st.number_input("Maktu Aile (TL)", min_value=0.0, key="s_maktu_aile")
            st.text_input("Aile Notu", key="s_aile_not", placeholder="Not...")
    with r910b:
        with st.container(border=True):
            st.markdown("👶 **Çocuk Yardımı** (2 çocuk baz)")
            cl1, cl2 = st.columns(2)
            with cl1: st.checkbox("657 Çocuk Yardımı", key="s_yasal_cocuk")
            with cl2:
                if st.session_state["s_yasal_cocuk"]:
                    st.number_input("Ödeme Oranı (%)", min_value=1.0, max_value=100.0,
                                    step=1.0, key="s_yasal_cocuk_pct", help="%100 = tam yasal tutar")
            cl3, cl4 = st.columns(2)
            with cl3: st.checkbox("Muafiyet Çocuk", key="s_muaf_cocuk")
            with cl4:
                if st.session_state["s_muaf_cocuk"]:
                    st.number_input("Ödeme Oranı (%)", min_value=1.0, max_value=100.0,
                                    step=1.0, key="s_muaf_cocuk_pct", help="%100 = tam muafiyet tutarı")
            st.number_input("Maktu Çocuk (Birim TL)", min_value=0.0, key="s_maktu_cocuk")
            st.text_input("Çocuk Notu", key="s_cocuk_not", placeholder="Not...")

    # 11. PRİM (tam genişlik)
    with st.container(border=True):
        ph1, ph2 = st.columns([3, 1])
        with ph1: st.markdown("🏆 **Prim**")
        with ph2: st.selectbox("", ["Aylık","Yıllık"], key="s_pr_per", label_visibility="collapsed")
        pc1, pc2, pc3 = st.columns([2, 2, 1])
        with pc1: st.selectbox("Mod", ["Maktu","Katsayı (Gün)","Yüzde (%)"], key="s_pr_m")
        with pc2: st.radio("", ["Net","Brüt"], horizontal=True, key="s_pr_t")
        with pc3: st.number_input("+%", min_value=0.0, max_value=500.0, step=0.5,
                                   key="s_pr_zam", help="Prime özel artış")
        pd1, pd2 = st.columns([2, 3])
        with pd1: st.number_input("Değer", min_value=0.0, key="s_pr_v")
        with pd2: st.text_input("Not", key="s_pr_not", placeholder="Açıklama...")
        pr_ham  = yardim_brutlestir(calc_hybrid(st.session_state["s_pr_v"], st.session_state["s_pr_m"], g_brut),
                                    st.session_state["s_pr_t"], secilen_oran)
        pr_baz  = ayliklandir(pr_ham, st.session_state["s_pr_per"])
        ay_prim = pr_baz * carpan("s_pr_zam")
        goster_artis(pr_baz, ay_prim)

    st.divider()
    st.markdown("### ⚡ Vardiya, Gece ve Özel")
    cv1, cv2, cv3 = st.columns(3)
    with cv1:
        with st.container(border=True):
            st.write("🔄 **Vardiya Zammı**")
            st.text_input("Not", key="s_v_not", placeholder="Açıklama...")
            st.selectbox("Hesap Tipi", ["Sabit","Fiili (195/225)"], key="s_v_hesap")
            st.selectbox("Birim", ["Maktu","Yüzde (%)"], key="s_v_mod")
            st.number_input("Miktar", min_value=0.0, key="s_v_val")
    with cv2:
        with st.container(border=True):
            st.write("🌙 **Gece Zammı**")
            st.text_input("Not", key="s_g_not", placeholder="Açıklama...")
            st.selectbox("Hesap Tipi", ["Sabit","Fiili (80/225)"], key="s_g_hesap")
            st.selectbox("Birim", ["Maktu","Yüzde (%)"], key="s_g_mod")
            st.number_input("Miktar", min_value=0.0, key="s_g_val")
    with cv3:
        with st.container(border=True):
            st.write("➕ **Ek Özel**")
            st.text_input("Not", key="s_eo_not", placeholder="Açıklama...")
            st.selectbox("Baz", ["Günlük Ücret","Aylık Ücret"], key="s_eo_tip")
            st.selectbox("Birim", ["Katsayı","Yüzde (%)"], key="s_eo_mod")
            st.number_input("Miktar", min_value=0.0, key="s_eo_val")

    st.markdown("### 📈 Denge Ödentisi")
    with st.container(border=True):
        cd1, cd2 = st.columns(2)
        with cd1:
            st.checkbox("Denge Ödentisi Uygula", key="s_denge")
            st.number_input("Oran (%)", min_value=0.0, key="s_denge_oran")
        with cd2: st.caption("Baz: Ücret + İkramiye + Gece + Vardiya")

    # ── HESAPLAMALAR ──────────────────────────────────────────
    ek1_per = st.session_state["s_ek1_per"]
    ek2_per = st.session_state["s_ek2_per"]
    _ek1_ham = yardim_brutlestir(
        calc_hybrid(st.session_state["s_ek1_val"], st.session_state["s_ek1_mod"], g_brut),
        st.session_state["s_ek1_tip"], secilen_oran)
    _ek2_ham = yardim_brutlestir(
        calc_hybrid(st.session_state["s_ek2_val"], st.session_state["s_ek2_mod"], g_brut),
        st.session_state["s_ek2_tip"], secilen_oran)
    ay_ek1 = ((_ek1_ham if ek1_per=="Aylık" else _ek1_ham/12)
              * (1 + st.session_state["s_ek1_zam"]/100))
    ay_ek2 = ((_ek2_ham if ek2_per=="Aylık" else _ek2_ham/12)
              * (1 + st.session_state["s_ek2_zam"]/100))

    # Aile/Çocuk hesabı (yüzde oranı uygulanır)
    yasal_aile_t  = aile_yasal_sabit * (st.session_state["s_yasal_aile_pct"]/100) if st.session_state["s_yasal_aile"] else 0
    muaf_aile_t   = muafiyet_aile    * (st.session_state["s_muaf_aile_pct"]/100)  if st.session_state["s_muaf_aile"]  else 0
    yasal_cocuk_t = (cocuk_6_ustu*2) * (st.session_state["s_yasal_cocuk_pct"]/100) if st.session_state["s_yasal_cocuk"] else 0
    muaf_cocuk_t  = muafiyet_cocuk   * (st.session_state["s_muaf_cocuk_pct"]/100)  if st.session_state["s_muaf_cocuk"]  else 0
    ay_aile_cocuk = (yasal_aile_t + muaf_aile_t + st.session_state["s_maktu_aile"] +
                     yasal_cocuk_t + muaf_cocuk_t + st.session_state["s_maktu_cocuk"]*2)

    v_tutar = calc_hybrid(st.session_state["s_v_val"], st.session_state["s_v_mod"], g_brut)
    if st.session_state["s_v_hesap"] == "Fiili (195/225)": v_tutar = v_tutar * 195/225

    def gece_zammi_hesapla():
        mod = st.session_state["s_g_mod"]       # "Maktu" veya "%"
        hesap = st.session_state["s_g_hesap"]   # "Fiili (80/225)"
        val = st.session_state["s_g_val"]
        brut_ucret = g_brut  # senin mevcut brüt ücret değişkenin

        if hesap == "Fiili (80/225)":

            if mod == "Maktu":
                # Saatlik girildi → direkt 80 ile çarp
                g_tutar = val * 80

            else:
                # Yüzde girildi
                saatlik = brut_ucret / 225
                saatlik_zam = saatlik * (val / 100)
                g_tutar = saatlik_zam * 80

        else:
            # diğer sistem varsa (eski mantık)
            g_tutar = calc_hybrid(val, mod, brut_ucret)

        return g_tutar

    eo_val = st.session_state["s_eo_val"]; eo_mod = st.session_state["s_eo_mod"]
    ay_ek_ozel = g_brut * (eo_val if eo_mod=="Katsayı" else eo_val/100) \
                 if st.session_state["s_eo_tip"]=="Günlük Ücret" \
                 else a_brut * (eo_val if eo_mod=="Katsayı" else eo_val/100)

    if st.session_state["s_denge"]:
        g_tutar = gece_zammi_hesapla()
        baz = a_brut + ay_ikramiye + g_tutar + v_tutar
        ay_denge = baz * (st.session_state["s_denge_oran"]/100)
        st.metric("Denge Ödentisi", f"{ay_denge:,.2f} TL")
    else: ay_denge = 0.0

    toplam_sosyal = (gida + yakacak + ay_izin + ay_bayram + ay_prim +
                     giyim + ayakkabi + yilbasi +
                     ay_ikramiye + ay_aile_cocuk +
                     v_tutar + g_tutar + ay_ek_ozel + ay_denge)
    t_maliyet = a_brut + ay_ek1 + ay_ek2 + toplam_sosyal

    # ── SONUÇLAR ──────────────────────────────────────────────
    st.divider()
    r1, r2, r3 = st.columns(3)
    r1.metric("💼 Toplam Aylık Maliyet", f"{t_maliyet:,.2f} TL")
    r2.metric("🎁 Sosyal Paket", f"{toplam_sosyal:,.2f} TL")
    r3.metric("💵 Ana Maaş (Brüt)", f"{a_brut:,.2f} TL")
    st.table(pd.DataFrame({
        "Kalem": ["Ana Maaş", "Ek Ödemeler (1+2)", "Sosyal Paket", "Vardiya/Gece/Özel"],
        "Aylık Tutar (TL)": [f"{a_brut:,.2f}", f"{ay_ek1+ay_ek2:,.2f}",
                              f"{toplam_sosyal-v_tutar-g_tutar-ay_ek_ozel:,.2f}",
                              f"{v_tutar+g_tutar+ay_ek_ozel:,.2f}"]
    }))

    # ── KAYIT ──────────────────────────────────────────────────
    st.divider()
    kb1, kb2 = st.columns(2)
    with kb1:
        if st.button("💾 Veritabanına Kaydet"):
            try:
                sheet = get_sheet(); baslik_guncelle(sheet)
                tis_bas_str = st.session_state["s_tis_bas"].strftime("%d/%m/%Y")
                tis_bit_str = st.session_state["s_tis_bit"].strftime("%d/%m/%Y")
                zam_ozet = " | ".join([
                    f"{d['ay']} {d['yil']}: " +
                    ", ".join([f"%{k['deger']}" if k['tip']=="Yüzde (%)" else f"{k['deger']:.0f}TL" for k in d["kalemler"]]) +
                    (" ✅" if d.get("uygula") else "")
                    for d in st.session_state.get("s_zam_verileri", [])
                ])
                # Zam verilerini JSON olarak sakla
                zam_json = json.dumps(st.session_state.get("s_zam_verileri", []),
                                      ensure_ascii=False, default=str)
                row = [
                    datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state["active_user"],
                    st.session_state["s_isyeri"], st.session_state["s_isyeri_tipi"],
                    st.session_state["s_grev"], str(st.session_state["s_yabanci"]),
                    st.session_state["s_ulke"], st.session_state["s_isv_sendika"],
                    st.session_state["s_sektor"], st.session_state["s_grup"],
                    ", ".join(st.session_state["s_subeler"]),
                    st.session_state["s_uye"], st.session_state["s_calisan"],
                    tis_bas_str, tis_bit_str, zam_ozet,
                    st.session_state["s_u_tipi"],  sf(st.session_state["s_u_tutar"]),
                    st.session_state["s_ek1_mod"], sf(st.session_state["s_ek1_val"]),
                    st.session_state["s_ek1_per"], st.session_state["s_ek1_tip"], sf(st.session_state["s_ek1_zam"]),
                    st.session_state["s_ek2_mod"], sf(st.session_state["s_ek2_val"]),
                    st.session_state["s_ek2_per"], st.session_state["s_ek2_tip"], sf(st.session_state["s_ek2_zam"]),
                    # Gıda
                    st.session_state["s_gida_tip"], sf(st.session_state["s_gida_val"]),
                    st.session_state["s_gida_per"], st.session_state["s_gida_not"],
                    # Yakacak
                    st.session_state["s_yakacak_mod"], st.session_state["s_yakacak_kdv"],
                    sf(st.session_state["s_yakacak_val"]), sf(st.session_state["s_yakacak_m3"]),
                    sf(st.session_state["s_yakacak_birim"]),
                    st.session_state["s_yakacak_per"], st.session_state["s_yakacak_not"],
                    # Giyim
                    st.session_state["s_giyim_tip"], sf(st.session_state["s_giyim_val"]),
                    st.session_state["s_giyim_per"], st.session_state["s_giyim_not"],
                    # Ayakkabı
                    st.session_state["s_ayakkabi_tip"], sf(st.session_state["s_ayakkabi_val"]),
                    st.session_state["s_ayakkabi_per"], st.session_state["s_ayakkabi_not"],
                    # Yılbaşı
                    st.session_state["s_yilbasi_tip"], sf(st.session_state["s_yilbasi_val"]),
                    st.session_state["s_yilbasi_per"], st.session_state["s_yilbasi_not"],
                    # İzin
                    st.session_state["s_iz_m"], st.session_state["s_iz_t"],
                    sf(st.session_state["s_iz_v"]), st.session_state["s_iz_per"], st.session_state["s_iz_not"],
                    # Bayram
                    st.session_state["s_ba_m"], st.session_state["s_ba_t"],
                    sf(st.session_state["s_ba_v"]), st.session_state["s_ba_per"], st.session_state["s_ba_not"],
                    # Prim
                    st.session_state["s_pr_m"], st.session_state["s_pr_t"],
                    sf(st.session_state["s_pr_v"]), st.session_state["s_pr_per"], st.session_state["s_pr_not"],
                    # İkramiye
                    st.session_state["s_ikramiye"], st.session_state["s_ikramiye_not"],
                    # Aile
                    str(st.session_state["s_yasal_aile"]), sf(st.session_state["s_yasal_aile_pct"]),
                    str(st.session_state["s_muaf_aile"]),  sf(st.session_state["s_muaf_aile_pct"]),
                    sf(st.session_state["s_maktu_aile"]),  st.session_state["s_aile_not"],
                    # Çocuk
                    str(st.session_state["s_yasal_cocuk"]), sf(st.session_state["s_yasal_cocuk_pct"]),
                    str(st.session_state["s_muaf_cocuk"]),  sf(st.session_state["s_muaf_cocuk_pct"]),
                    sf(st.session_state["s_maktu_cocuk"]),  st.session_state["s_cocuk_not"],
                    # Vardiya, Gece, Ek özel
                    st.session_state["s_v_hesap"], st.session_state["s_v_mod"],
                    sf(st.session_state["s_v_val"]), st.session_state["s_v_not"],
                    st.session_state["s_g_hesap"], st.session_state["s_g_mod"],
                    sf(st.session_state["s_g_val"]), st.session_state["s_g_not"],
                    st.session_state["s_eo_tip"], st.session_state["s_eo_mod"],
                    sf(st.session_state["s_eo_val"]), st.session_state["s_eo_not"],
                    str(st.session_state["s_denge"]), sf(st.session_state["s_denge_oran"]),
                    sf(st.session_state["s_sosyal_zam_pct"]),
                    zam_json,
                    sf(a_brut), sf(toplam_sosyal), sf(t_maliyet)
                ]
                sheet.append_row(row)
                verileri_getir.clear()
                st.success("✅ Kaydedildi!"); st.balloons()
            except Exception as e:
                st.error(f"Kayıt hatası: {e}")

    with kb2:
        rapor = {
            "Parametre": [
                "Uzman","İşyeri","Sektör","Grup","Şubeler","TİS Başlangıç","TİS Bitiş",
                "Üye Sayısı","Grev Durumu","Ana Maaş (Brüt)","Gıda","Yakacak",
                "Giyim","Ayakkabı","Yılbaşı","İzin","Bayram","Prim","İkramiye",
                "Aile & Çocuk","Vardiya","Gece Zammı","Özel Ek","Denge",
                "Sosyal Paket","Toplam Maliyet"
            ],
            "Değer": [
                st.session_state["active_user"], st.session_state["s_isyeri"],
                st.session_state["s_sektor"], st.session_state["s_grup"],
                ", ".join(st.session_state["s_subeler"]),
                st.session_state["s_tis_bas"].strftime("%d/%m/%Y"),
                st.session_state["s_tis_bit"].strftime("%d/%m/%Y"),
                st.session_state["s_uye"], st.session_state["s_grev"],
                f"{a_brut:,.2f} TL", f"{gida:,.2f} TL", f"{yakacak:,.2f} TL",
                f"{giyim:,.2f} TL",  f"{ayakkabi:,.2f} TL", f"{yilbasi:,.2f} TL",
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
        st.download_button("📥 Excel Raporu İndir", data=output.getvalue(),
            file_name=f"{st.session_state['s_isyeri']}_TIS_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ============================================================
# TAB 3
# ============================================================
with tab3:
    st.header("📊 Karşılaştırma ve İstatistik")
    df3 = verileri_getir()
    if df3.empty:
        st.info("Henüz kayıtlı veri yok.")
    else:
        for col in ["Ana Maaş (Brüt)", "Sosyal Paket", "Toplam Maliyet"]:
            if col in df3.columns:
                df3[col] = pd.to_numeric(df3[col].astype(str).str.replace(",","."), errors='coerce')

        st.subheader("🔢 Genel Özet")
        og1, og2, og3, og4 = st.columns(4)
        og1.metric("Toplam İşyeri", len(df3))
        if "Üye Sayısı" in df3.columns:
            try: og2.metric("Toplam Üye", f"{int(pd.to_numeric(df3['Üye Sayısı'], errors='coerce').sum()):,}")
            except: og2.metric("Toplam Üye", "-")
        if "Ana Maaş (Brüt)" in df3.columns:
            og3.metric("Ort. Çıplak Ücret", f"{df3['Ana Maaş (Brüt)'].mean():,.0f} TL")
        if "Toplam Maliyet" in df3.columns:
            og4.metric("Ort. Giydirilmiş Ücret", f"{df3['Toplam Maliyet'].mean():,.0f} TL")

        st.divider()
        st.subheader("🏙️ Şube Bazlı Karşılaştırma")
        if "Şubeler" in df3.columns and "Ana Maaş (Brüt)" in df3.columns:
            sube_rows = []
            for _, row in df3.iterrows():
                for s in str(row.get("Şubeler","")).split(","):
                    s = s.strip()
                    if s: sube_rows.append({"Şube":s,"Çıplak":row.get("Ana Maaş (Brüt)",0),"Giydirilmiş":row.get("Toplam Maliyet",0)})
            if sube_rows:
                sube_df   = pd.DataFrame(sube_rows)
                sube_ozet = sube_df.groupby("Şube").agg(
                    İşyeri_Sayısı=("Çıplak","count"), Ort_Çıplak=("Çıplak","mean"), Ort_Giydirilmiş=("Giydirilmiş","mean")
                ).reset_index().sort_values("Ort_Çıplak", ascending=False)
                sube_ozet["Ort_Çıplak"]      = sube_ozet["Ort_Çıplak"].map("{:,.0f} TL".format)
                sube_ozet["Ort_Giydirilmiş"] = sube_ozet["Ort_Giydirilmiş"].map("{:,.0f} TL".format)
                sube_ozet.columns = ["Şube","İşyeri Sayısı","Ort. Çıplak Ücret","Ort. Giydirilmiş Ücret"]
                st.dataframe(sube_ozet, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("🏭 Sektör / Grup Bazlı")
        scol1, scol2 = st.columns(2)
        with scol1:
            st.markdown("**Sektör**")
            if "Sektör" in df3.columns:
                sek_ozet = df3.groupby("Sektör").agg(
                    İşyeri=("Ana Maaş (Brüt)","count"), Ort_Çıplak=("Ana Maaş (Brüt)","mean"), Ort_Giydirilmiş=("Toplam Maliyet","mean")
                ).reset_index().sort_values("Ort_Çıplak", ascending=False)
                sek_ozet["Ort_Çıplak"]      = sek_ozet["Ort_Çıplak"].map("{:,.0f} TL".format)
                sek_ozet["Ort_Giydirilmiş"] = sek_ozet["Ort_Giydirilmiş"].map("{:,.0f} TL".format)
                sek_ozet.columns = ["Sektör","İşyeri Sayısı","Ort. Çıplak","Ort. Giydirilmiş"]
                st.dataframe(sek_ozet, use_container_width=True, hide_index=True)
        with scol2:
            st.markdown("**Grup**")
            if "Grup" in df3.columns:
                grup_ozet = df3.groupby("Grup").agg(
                    İşyeri=("Ana Maaş (Brüt)","count"), Ort_Çıplak=("Ana Maaş (Brüt)","mean"), Ort_Giydirilmiş=("Toplam Maliyet","mean")
                ).reset_index().sort_values("Ort_Çıplak", ascending=False)
                grup_ozet["Ort_Çıplak"]      = grup_ozet["Ort_Çıplak"].map("{:,.0f} TL".format)
                grup_ozet["Ort_Giydirilmiş"] = grup_ozet["Ort_Giydirilmiş"].map("{:,.0f} TL".format)
                grup_ozet.columns = ["Grup","İşyeri Sayısı","Ort. Çıplak","Ort. Giydirilmiş"]
                st.dataframe(grup_ozet, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("🔍 İşyeri Karşılaştırması")
        if "İşyeri" in df3.columns:
            secilen = st.selectbox("İşyeri Seç", df3["İşyeri"].dropna().unique().tolist(), key="tab3_isyeri_sec")
            if secilen:
                sec_row           = df3[df3["İşyeri"]==secilen].iloc[0]
                genel_ort_maas    = df3["Ana Maaş (Brüt)"].mean()
                genel_ort_maliyet = df3["Toplam Maliyet"].mean()
                isyeri_maas    = float(str(sec_row.get("Ana Maaş (Brüt)",0)).replace(",",".") or 0)
                isyeri_maliyet = float(str(sec_row.get("Toplam Maliyet",0)).replace(",",".") or 0)
                kk1, kk2 = st.columns(2)
                with kk1: st.metric("Çıplak Ücret", f"{isyeri_maas:,.0f} TL",
                                     delta=f"{isyeri_maas-genel_ort_maas:+,.0f} TL (genel ort.)")
                with kk2: st.metric("Giydirilmiş Ücret", f"{isyeri_maliyet:,.0f} TL",
                                     delta=f"{isyeri_maliyet-genel_ort_maliyet:+,.0f} TL (genel ort.)")
                if "Sektör" in df3.columns and sec_row.get("Sektör"):
                    sek = sec_row.get("Sektör"); sek_df = df3[df3["Sektör"]==sek]
                    sk1, sk2 = st.columns(2)
                    with sk1: st.metric(f"{sek} Ort. Çıplak", f"{sek_df['Ana Maaş (Brüt)'].mean():,.0f} TL",
                                         delta=f"{isyeri_maas-sek_df['Ana Maaş (Brüt)'].mean():+,.0f} TL")
                    with sk2: st.metric(f"{sek} Ort. Giydirilmiş", f"{sek_df['Toplam Maliyet'].mean():,.0f} TL",
                                         delta=f"{isyeri_maliyet-sek_df['Toplam Maliyet'].mean():+,.0f} TL")
                if "Grup" in df3.columns and sec_row.get("Grup"):
                    grp = sec_row.get("Grup"); grp_df = df3[df3["Grup"]==grp]
                    gk1, gk2 = st.columns(2)
                    with gk1: st.metric(f"{grp} Grubu Ort. Çıplak", f"{grp_df['Ana Maaş (Brüt)'].mean():,.0f} TL",
                                         delta=f"{isyeri_maas-grp_df['Ana Maaş (Brüt)'].mean():+,.0f} TL")
                    with gk2: st.metric(f"{grp} Grubu Ort. Giydirilmiş", f"{grp_df['Toplam Maliyet'].mean():,.0f} TL",
                                         delta=f"{isyeri_maliyet-grp_df['Toplam Maliyet'].mean():+,.0f} TL")

        st.divider()
        st.subheader("📋 Tüm Kayıtlar")
        goster_cols = [c for c in ["İşyeri","Sektör","Grup","Şubeler","Üye Sayısı",
                                    "TİS Başlangıç","TİS Bitiş","Ana Maaş (Brüt)","Sosyal Paket","Toplam Maliyet"]
                       if c in df3.columns]
        st.dataframe(df3[goster_cols].sort_values("Toplam Maliyet", ascending=False),
                     use_container_width=True, hide_index=True)
