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
    
    asgari_ucret_limit = st.number_input("Güncel Asgari Ücret (Brüt)", value=33030.00)
    
    oran_etiketleri = {
        0.71491: "%15 Vergi Dilimi", 0.67241: "%20 Vergi Dilimi",
        0.61291: "%27 Vergi Dilimi", 0.54491: "%35 Vergi Dilimi"
    }
    secilen_oran = st.radio("📉 Vergi Dilimi Seçimi", options=list(oran_etiketleri.keys()), 
                            format_func=lambda x: oran_etiketleri[x], index=1)
    
    st.subheader("⚖️ Yasal Yardımlar (Aylık)")
    aile_yasal = st.number_input("657 S.K. Aile Yardımı", value=3154.63)
    cocuk_0_6_yasal = st.number_input("657 S.K. Çocuk (0-6)", value=693.94)
    cocuk_6_ustu_yasal = st.number_input("657 S.K. Çocuk (6+)", value=346.97)
    
    muafiyet_aile = asgari_ucret_limit * 0.10
    muafiyet_cocuk = (asgari_ucret_limit * 0.02) * 2 
    
    st.info(f"Otomatik Muafiyetler:\n- Aile: {muafiyet_aile:,.2f} TL\n- Çocuk (2): {muafiyet_cocuk:,.2f} TL")

# --- HESAPLAMA ARAÇLARI (GÜNCELLENDİ) ---

def calc_hybrid(val, mode, daily_base):
    """Maktu, Katsayı veya Yüzdeye göre brüt tutarı hesaplar"""
    if mode == "Maktu": return val
    elif mode == "Katsayı (Gün)": return daily_base * val
    elif mode == "Yüzde (%)": return daily_base * 30 * (val / 100)
    return 0

def maas_brutlestir(tutar, tip, oran):
    """Ana ücret için istisnalı brütleştirme"""
    sabitler = {0.71491: 4462.03, 0.67241: 4788.45, 0.61291: 5865.80, 0.54491: 5865.80}
    if tip == "Brüt": return tutar
    sabit = sabitler.get(oran, 5865.80)
    # Formül: (Net - İstisna) / Katsayı
    return (tutar - sabit) / oran

def yardim_brutlestir(tutar, tip, oran):
    """Sosyal yardımlar için doğrudan brütleştirme"""
    if tip == "Brüt": return tutar
    # Sosyal yardımlarda istisna düşülmez, doğrudan katsayıya bölünür
    # Formül: Net / Katsayı
    return tutar / oran

# --- SEKME YAPISI ---
tab1, tab2 = st.tabs(["💰 Ücret ve Sosyal Ödemeler", "🏢 İşyeri Bilgileri"])

with tab2:
    st.header("🏢 İşyeri ve Şube Bilgileri")
    col_is1, col_is2 = st.columns(2)
    with col_is1:
        isyeri_adi = st.text_input("İşyeri Tam Adı", placeholder="Örn: ABC Kimya A.Ş.")
        subeler = st.multiselect("Bağlı Olduğu Şubeler", ["Adana", "Adıyaman", "Ankara", "Bandırma", "Batman", "Bursa", "Ceyhan", "Çankırı", "Gebze", "İstanbul 1", "İstanbul 2", "İzmir", "Kırıkkale", "Kocaeli", "Mersin", "Trakya", "Aliağa"])
        # --- YENİ: TARİH ALANLARI ---
        st.divider()
        st.subheader("📅 Sözleşme Dönemi")
        tis_baslangic = st.date_input("Yürürlük Başlangıç Tarihi", value=datetime.now())
        tis_bitis = st.date_input("Yürürlük Bitiş Tarihi", value=datetime.now().replace(year=datetime.now().year + 2))
        
        # Süre Hesaplama ve Uyarı
        sozlesme_suresi = (tis_bitis - tis_baslangic).days / 365
        if sozlesme_suresi < 1:
            st.warning("⚠️ TİS kanunen 1 yıldan az olamaz.")
        elif sozlesme_suresi > 3:
            st.error("❌ TİS kanunen 3 yıldan fazla olamaz.")
        else:
            st.success(f"✅ Sözleşme Süresi: {sozlesme_suresi:.1f} Yıl")
    with col_is2:
        toplam_calisan = st.number_input("Toplam Çalışan Sayısı", value=0)
        uye_sayisi = st.number_input("Sendikalı Üye Sayısı", value=0)
        grev_yasagi = st.selectbox("Grev Yasağı Durumu", ["Grev Yasağı Yok", "Grev Yasağı Var"])

with tab1:
    st.header("💵 Ücret ve Ek Ödemeler")
    c1, c2, c3 = st.columns(3)
    with c1:
        u_tipi = st.radio("Ücret Tipi", ["Net", "Brüt"])
        u_tutar = st.number_input("Çıplak Ücret Tutarı", value=20000.0)
    with c2:
        st.info("Ek Ödeme 1")
        ek_mod = st.selectbox("Hesaplama Modu", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"], key="ek1_mod")
        ek_val = st.number_input("Değer", value=0.0, key="ek1_val")
        ek_per = st.selectbox("Periyot", ["Aylık", "Yıllık"], key="ek1_per")
    with c3:
        st.info("Ek Ödeme 2")
        ek2_mod = st.selectbox("Hesaplama Modu", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"], key="ek2_mod")
        ek2_val = st.number_input("Değer", value=0.0, key="ek2_val")
        ek2_per = st.selectbox("Periyot", ["Aylık", "Yıllık"], key="ek2_per")

    # Temel Maaş Hesaplama
    a_brut = maas_brutlestir(u_tutar, u_tipi, secilen_oran) 
    g_brut = a_brut / 30

    st.markdown("### 🎁 Sosyal Yardımlar")
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        with st.container(border=True):
            st.write("🍞 **Gıda Yardımı (Aylık)**")
            g_tip = st.radio("Gıda Tip", ["Net", "Brüt"], horizontal=True)
            g_val = st.number_input("Gıda Tutarı", 0.0)
            gida = yardim_brutlestir(g_val, g_tip, secilen_oran)
    with col_s2:
        with st.container(border=True):
            st.write("🔥 **Yakacak Yardımı (Aylık)**")
            y_tip = st.radio("Yakacak Tip", ["Net", "Brüt"], horizontal=True)
            y_val = st.number_input("Yakacak Tutarı", 0.0)
            yakacak = yardim_brutlestir(y_val, y_tip, secilen_oran)

    col_s3, col_s4, col_s5 = st.columns(3)
    with col_s3:
        with st.container(border=True):
            st.write("👕 **Giyim (Yıllık)**")
            giy_tip = st.radio("Giyim Tip", ["Net", "Brüt"], horizontal=True)
            giyim = yardim_brutlestir(st.number_input("Giyim Tutar", 0.0), giy_tip, secilen_oran)
    with col_s4:
        with st.container(border=True):
            st.write("👟 **Ayakkabı (Yıllık)**")
            ayk_tip = st.radio("Ayakkabı Tip", ["Net", "Brüt"], horizontal=True)
            ayakkabi = yardim_brutlestir(st.number_input("Ayakkabı Tutar", 0.0), ayk_tip, secilen_oran)
    with col_s5:
        with st.container(border=True):
            st.write("🎁 **Yılbaşı (Yıllık)**")
            yil_tip = st.radio("Yılbaşı Tip", ["Net", "Brüt"], horizontal=True)
            yilbasi = yardim_brutlestir(st.number_input("Yılbaşı Tutar", 0.0), yil_tip, secilen_oran)

    col_s6, col_s7, col_s8 = st.columns(3)
    with col_s6:
        with st.container(border=True):
            st.write("📅 **İzin Parası**")
            iz_m = st.selectbox("İzin Mod", ["Maktu", "Katsayı (Gün)"])
            iz_t = st.radio("İzin Tip", ["Net", "Brüt"], horizontal=True)
            iz_v = st.number_input("İzin Değer", 0.0)
            ay_izin = yardim_brutlestir(calc_hybrid(iz_v, iz_m, g_brut), iz_t, secilen_oran) / 12
    with col_s7:
        with st.container(border=True):
            st.write("🎉 **Bayram Yardımı**")
            ba_m = st.selectbox("Bayram Mod", ["Maktu", "Katsayı (Gün)"])
            ba_t = st.radio("Bayram Tip", ["Net", "Brüt"], horizontal=True)
            ba_v = st.number_input("Bayram Değer", 0.0)
            ay_bayram = yardim_brutlestir(calc_hybrid(ba_v, ba_m, g_brut), ba_t, secilen_oran) / 12
    with col_s8:
        with st.container(border=True):
            st.write("🏆 **Prim Ödemesi**")
            pr_m = st.selectbox("Prim Mod", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"])
            pr_t = st.radio("Prim Tip", ["Net", "Brüt"], horizontal=True)
            pr_v = st.number_input("Prim Değer", 0.0)
            ay_prim = yardim_brutlestir(calc_hybrid(pr_v, pr_m, g_brut), pr_t, secilen_oran)

    with st.container(border=True):
        ikramiye = st.number_input("💰 Yıllık Toplam İkramiye Günü", value=0)
        ay_ikramiye = (g_brut * ikramiye) / 12

    with st.container(border=True):
        st.write("👨‍👩‍👧‍👦 **Aile & Çocuk Yardımı**")
        col_ac1, col_ac2 = st.columns(2)
        with col_ac1:
            yasal_aile = st.checkbox("657 Aile Yardımı")
            muafiyet_aile_tik = st.checkbox("Muafiyet Aile")
            maktu_aile = st.number_input("Maktu Aile", 0.0)
        with col_ac2:
            yasal_cocuk_tik = st.checkbox("657 Çocuk Yardımı")
            muafiyet_cocuk_tik = st.checkbox("Muafiyet Çocuk")
            maktu_cocuk_birim = st.number_input("Maktu Çocuk (Birim)", 0.0)

    st.divider()
    st.markdown("### ⚡ Özel Ödemeler (Vardiya, Gece ve Ek)")
    v1, v2, v3 = st.columns(3)
    with v1:
        with st.container(border=True):
            st.write("🔄 **Vardiya Zammı**")
            v_hesap_tipi = st.selectbox("Hesaplama Türü", ["Sabit", "Fiili (195/225)"], key="v_h")
            v_mod = st.selectbox("Birim", ["Maktu", "Yüzde (%)"], key="v_m")
            v_val = st.number_input("Miktar", 0.0, key="v_v")
    with v2:
        with st.container(border=True):
            st.write("🌙 **Gece Zammı**")
            g_hesap_tipi = st.selectbox("Hesaplama Türü", ["Sabit", "Fiili (80/225)"], key="g_h")
            g_mod = st.selectbox("Birim", ["Maktu", "Yüzde (%)"], key="g_m")
            g_val = st.number_input("Miktar", 0.0, key="g_v")
    with v3:
        with st.container(border=True):
            st.write("➕ **Ücrete Bağlı Ek Özel**")
            ek_ozel_tip = st.selectbox("Baz Alınacak Ücret", ["Günlük Ücret", "Aylık Ücret"], key="eo_t")
            ek_ozel_mod = st.selectbox("Birim", ["Katsayı", "Yüzde (%)"], key="eo_m")
            ek_ozel_val = st.number_input("Miktar", 0.0, key="eo_v")

    # --- FİNAL HESAPLAMALAR ---
    ay_ek1 = calc_hybrid(ek_val, ek_mod, g_brut) if ek_per == "Aylık" else calc_hybrid(ek_val, ek_mod, g_brut) / 12
    ay_ek2 = calc_hybrid(ek2_val, ek2_mod, g_brut) if ek2_per == "Aylık" else calc_hybrid(ek2_val, ek2_mod, g_brut) / 12
    
    # Aile & Çocuk
    sabit_cocuk_sayisi = 2
    yasal_aile_tutar = aile_yasal if yasal_aile else 0
    muafiyet_aile_tutar = muafiyet_aile if muafiyet_aile_tik else 0
    yasal_cocuk_tutar = (cocuk_6_ustu_yasal * 2 * sabit_cocuk_sayisi) if yasal_cocuk_tik else 0
    muafiyet_cocuk_tutar = muafiyet_cocuk if muafiyet_cocuk_tik else 0
    maktu_cocuk_toplam = (maktu_cocuk_birim * sabit_cocuk_sayisi)
    ay_aile_cocuk_paketi = (yasal_aile_tutar + muafiyet_aile_tutar + maktu_aile + yasal_cocuk_tutar + muafiyet_cocuk_tutar + maktu_cocuk_toplam)

    # Vardiya & Gece
    v_tutar = calc_hybrid(v_val, v_mod, g_brut)
    if v_hesap_tipi == "Fiili (195/225)": v_tutar = (v_tutar * 195) / 225
    g_tutar = calc_hybrid(g_val, g_mod, g_brut)
    if g_hesap_tipi == "Fiili (80/225)": g_tutar = (g_tutar * 80) / 225

    # Ek Özel
    if ek_ozel_tip == "Günlük Ücret":
        ay_ek_ozel = g_brut * (ek_ozel_val if ek_ozel_mod == "Katsayı" else ek_ozel_val / 100)
    else:
        ay_ek_ozel = a_brut * (ek_ozel_val if ek_ozel_mod == "Katsayı" else ek_ozel_val / 100)

    # Toplamlar
    toplam_sosyal = (gida + yakacak + ay_izin + ay_bayram + ay_prim + (giyim + ayakkabi + yilbasi) / 12 + ay_ikramiye + ay_aile_cocuk_paketi + v_tutar + g_tutar + ay_ek_ozel)
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

    # --- KAYIT VE İNDİRME ---
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
