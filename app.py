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

# --- SIDEBAR (Güncellenmiş) ---
with st.sidebar:
    st.markdown(f"### 👤 Uzman: **{st.session_state['active_user']}**")
    if st.button("Güvenli Çıkış"):
        st.session_state["password_correct"] = False
        st.rerun()
    st.divider()
    st.header("⚙️ Genel Ayarlar")
    
    # Asgari ücreti en üste alıyoruz ki aşağıda hesaplamada kullanabilelim
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
    
    # Muafiyet Hesapları
    muafiyet_aile = asgari_ucret_limit * 0.10
    muafiyet_cocuk = (asgari_ucret_limit * 0.02) * 2 
    
    st.info(f"Otomatik Muafiyetler:\n- Aile: {muafiyet_aile:,.2f} TL\n- Çocuk (2): {muafiyet_cocuk:,.2f} TL")

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

    izin_val, izin_mod, izin_tip = 0.0, "Maktu", "Brüt"
    bayram_val, bayram_mod, bayram_tip = 0.0, "Maktu", "Brüt"

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
        st.info("Ek Ödeme 2")
        ek2_mod = st.selectbox("Hesaplama Modu", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"], key="ek2_mod")
        ek2_val = st.number_input("Değer", value=0.0, key="ek2_val")
        ek2_per = st.selectbox("Periyot", ["Aylık", "Yıllık"], key="ek2_per")

    izin_val = st.session_state.get("iz_v", 0.0)
    izin_mod = st.session_state.get("iz_m", "Maktu")
    
    bayram_val = st.session_state.get("ba_v", 0.0)
    bayram_mod = st.session_state.get("ba_m", "Maktu")
    
    prim_val = st.session_state.get("pr_v", 0.0)
    prim_mod = st.session_state.get("pr_m", "Maktu")

    # --- HESAPLAMA ÇEKİRDEĞİ ---
    sabitler = {0.71491: 4462.03, 0.67241: 4788.45, 0.61291: 5865.80, 0.54491: 5865.80}
    a_brut = (u_tutar - sabitler[secilen_oran]) / secilen_oran if u_tipi == "Net" else u_tutar
    g_brut = a_brut / 30

    def calc_hybrid(val, mode, daily_base):
        if mode == "Maktu": return val
        elif mode == "Katsayı (Gün)": return daily_base * val
        elif mode == "Yüzde (%)": return daily_base * 30 * (val / 100)
        return 0

    def brutlestir(tutar, tip, oran):
        if tip == "Brüt": return tutar
        sabit = sabitler.get(oran, 5865.80)
        return (tutar - sabit) / oran

    st.markdown("### 🎁 Sosyal Yardımlar")

    def get_hex_color(val, tip):
    if val == 0: return "#FFEBEE"  # Açık kırmızı (Sıfır)
    elif tip == "Net": return "#E8F5E9" # Açık yeşil (Net)
    else: return "#FFFDE7" # Açık sarı (Brüt)
    
    # Satır 1
    col_s1, col_s2 = st.columns(2)
    with col_s1:
    # Renk dinamik olarak belirleniyor
    kutu_rengi = get_hex_color(st.session_state.get("gida_v", 0), st.session_state.get("gida_t", "Net"))
    
    # HTML/CSS ile özel konteyner oluşturuyoruz
    st.markdown(f"""
    <div style="background-color: {kutu_rengi}; padding: 20px; border-radius: 10px; border: 1px solid #ddd;">
        <h4 style="margin: 0;">🍞 Gıda Yardımı (Aylık)</h4>
    </div>
    """, unsafe_allow_html=True)
    
    # Elemanları kutunun altına veya içine (burada st.form veya kolon yapısıyla) yerleştirebilirsin
    g_tip = st.radio("Tip", ["Net", "Brüt"], horizontal=True, key="gida_t")
    g_val = st.number_input("Tutar", 0.0, key="gida_v")
    gida = brutlestir(g_val, g_tip, secilen_oran)
    with col_s2:
        with st.container(border=True):
            st.write("🔥 **Yakacak Yardımı (Aylık)**")
            y_tip = st.radio("Tip", ["Net", "Brüt"], horizontal=True, key="yaka_t")
            y_val = st.number_input("Tutar", 0.0, key="yaka_v")
            yakacak = brutlestir(y_val, y_tip, secilen_oran)

    # Satır 2
    col_s3, col_s4, col_s5 = st.columns(3)
    with col_s3:
        with st.container(border=True):
            st.write("👕 **Giyim (Yıllık)**")
            giy_tip = st.radio("Tip", ["Net", "Brüt"], horizontal=True, key="giy_t")
            giyim = brutlestir(st.number_input("Tutar", 0.0, key="giy_v"), giy_tip, secilen_oran)
    with col_s4:
        with st.container(border=True):
            st.write("👟 **Ayakkabı (Yıllık)**")
            ayk_tip = st.radio("Tip", ["Net", "Brüt"], horizontal=True, key="ayk_t")
            ayakkabi = brutlestir(st.number_input("Tutar", 0.0, key="ayk_v"), ayk_tip, secilen_oran)
    with col_s5:
        with st.container(border=True):
            st.write("🎁 **Yılbaşı (Yıllık)**")
            yil_tip = st.radio("Tip", ["Net", "Brüt"], horizontal=True, key="yil_t")
            yilbasi = brutlestir(st.number_input("Tutar", 0.0, key="yil_v"), yil_tip, secilen_oran)

    # Satır 3
    col_s6, col_s7, col_s8 = st.columns(3)
    with col_s6:
        with st.container(border=True):
            st.write("📅 **İzin Parası**")
            iz_m = st.selectbox("Mod", ["Maktu", "Katsayı (Gün)"], key="iz_m")
            iz_t = st.radio("Tip", ["Net", "Brüt"], horizontal=True, key="iz_t")
            iz_v = st.number_input("Değer", 0.0, key="iz_v")
            # Değişkenleri burada doğrudan tanımla, hesaplamada kullan
            izin_val, izin_mod, izin_tip = iz_v, iz_m, iz_t
            ay_izin = brutlestir(calc_hybrid(izin_val, izin_mod, g_brut), izin_tip, secilen_oran) / 12
    with col_s7:
        with st.container(border=True):
            st.write("🎉 **Bayram Yardımı**")
            ba_m = st.selectbox("Mod", ["Maktu", "Katsayı (Gün)"], key="ba_m")
            ba_t = st.radio("Tip", ["Net", "Brüt"], horizontal=True, key="ba_t")
            ba_v = st.number_input("Değer", 0.0, key="ba_v")
            ay_bayram = brutlestir(calc_hybrid(ba_v, ba_m, g_brut), ba_t, secilen_oran) / 12
    with col_s8:
        with st.container(border=True):
            st.write("🏆 **Prim Ödemesi**")
            pr_m = st.selectbox("Mod", ["Maktu", "Katsayı (Gün)", "Yüzde (%)"], key="pr_m")
            pr_t = st.radio("Tip", ["Net", "Brüt"], horizontal=True, key="pr_t")
            pr_v = st.number_input("Değer", 0.0, key="pr_v")
            ay_prim = brutlestir(calc_hybrid(pr_v, pr_m, g_brut), pr_t, secilen_oran)

    # İkramiye (Ayrı Kutu)
    with st.container(border=True):
        ikramiye = st.number_input("💰 Yıllık Toplam İkramiye Günü", value=0)
        ay_ikramiye = (g_brut * ikramiye) / 12

    # Aile & Çocuk Yardımı (Kutu içi)
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
            
    # ... (Geri kalan Vardiya/Gece/Özel Ek ve Hesaplamalar aynen devam eder)
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
    
    # Varsayılan değer: 2 çocuk (TİS standartı)
    sabit_cocuk_sayisi = 2 

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

    # --- YENİ AİLE & ÇOCUK HESAPLAMA MANTIĞI ---
    # Yasal Aile Yardımı
    yasal_aile_tutar = aile_yasal if yasal_aile else 0
    muafiyet_aile_tutar = muafiyet_aile if muafiyet_aile_tik else 0
    
    # Yasal Çocuk Yardımı: (Yasal 6+ değerinin 2 katı) * 2 Çocuk
    yasal_cocuk_tutar = (cocuk_6_ustu_yasal * 2 * sabit_cocuk_sayisi) if yasal_cocuk_tik else 0
    muafiyet_cocuk_tutar = muafiyet_cocuk if muafiyet_cocuk_tik else 0
    
    
    # Maktu Çocuk Yardımı: Birim * 2 Çocuk
    maktu_cocuk_toplam = (maktu_cocuk_birim * sabit_cocuk_sayisi)
    
    # Toplam Aile/Çocuk Paketi
    ay_aile_cocuk_paketi = (yasal_aile_tutar + muafiyet_aile_tutar + 
                            maktu_aile + yasal_cocuk_tutar + 
                            muafiyet_cocuk_tutar + maktu_cocuk_toplam)
    # ------------------------------------------
    
    # Vardiya ve Gece Hesaplama
    v_tutar = calc_hybrid(v_val, v_mod, g_brut)
    if v_tip == "Fiili (195/225)": v_tutar = (v_tutar * 195) / 225
    
    g_tutar = calc_hybrid(g_val, g_mod, g_brut)
    if g_tip == "Fiili (80/225)": g_tutar = (g_tutar * 80) / 225

    ay_ikramiye = (g_brut * ikramiye) / 12
    
    # Toplam Sosyal Paket
    toplam_sosyal = (gida + yakacak + ay_izin + ay_bayram + ay_prim + 
                     (giyim + ayakkabi + yilbasi) / 12 + ay_ikramiye + 
                     ay_aile_cocuk_paketi + v_tutar + g_tutar + ay_ek_ozel)
    
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
