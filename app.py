# ==========================================
# BAGIAN IMPORT 
# ==========================================
import os
import io
import time
import uuid
import hmac
import hashlib
import calendar
import datetime
import pytz

import pandas as pd
import streamlit as st
import extra_streamlit_components as stx
from PIL import Image
from dotenv import load_dotenv
from supabase import create_client, Client

# ==========================================
# FUNGSI UTILITAS AWAL
# ==========================================
def kompres_foto(image_bytes, quality=50, max_size=(400, 400)):
    """Fungsi kompresi ekstrem untuk menghemat Egress dan Storage"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail(max_size)
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        return output.getvalue()
    except Exception:
        return image_bytes 

# --- 1. MEMUAT ENVIRONMENT VARIABLES & SUPABASE ---
load_dotenv()

raw_url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
raw_key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")

url = raw_url.strip().rstrip('/')
if url.endswith('/rest/v1'):
    url = url[:-8]
key = raw_key.strip()

try:
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error(f"Gagal terhubung ke Supabase: {e}")
    st.stop()

def upload_ke_supabase(file_bytes, file_path, content_type):
    foto_pegawai = "foto_pegawai"
    try:
        supabase.storage.from_(foto_pegawai).upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        return supabase.storage.from_(foto_pegawai).get_public_url(file_path)
    except Exception as e:
        st.error(f"Gagal upload ke server Storage: {e}")
        return None

@st.dialog("Peringatan File CSV ⚠️")
def tampilkan_peringatan_csv():
    st.write("Gagal memproses file: Terdapat **sel atau baris kosong** di dalam file CSV Anda.")
    st.write("Pastikan semua data terisi penuh dan hapus baris kosong di bagian paling bawah tabel, lalu coba upload ulang.")
    if st.button("Oke, Saya Mengerti", key="btn_close_dialog_csv", width="stretch"):
        st.rerun()

# --- 1.5. FUNGSI KRIPTOGRAFI KEAMANAN ---
SECRET_KEY = os.environ.get("COOKIE_SECRET") or st.secrets.get("COOKIE_SECRET")
SUPERADMIN_PASSWORD = os.environ.get("SUPERADMIN_PASSWORD") or st.secrets.get("SUPERADMIN_PASSWORD")
SUPERADMIN_MENU_PASSWORD = os.environ.get("SUPERADMIN_MENU_PASSWORD") or st.secrets.get("SUPERADMIN_MENU_PASSWORD", "SandiMenu2026!")

if not SECRET_KEY or not SUPERADMIN_PASSWORD:
    st.error("🔒 KUNCI RAHASIA TIDAK DITEMUKAN! Pastikan COOKIE_SECRET dan SUPERADMIN_PASSWORD terisi.")
    st.stop()

def generate_signed_token(role_name: str) -> str:
    signature = hmac.new(SECRET_KEY.encode(), role_name.encode(), hashlib.sha256).hexdigest()
    return f"{role_name}|{signature}"

def verify_and_get_role(token: str):
    if not token or "|" not in token:
        return None
    parts = token.split("|", 1)
    role_name, client_signature = parts[0], parts[1]
    expected_signature = hmac.new(SECRET_KEY.encode(), role_name.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(client_signature, expected_signature):
        return role_name
    return None

# --- 2. KONFIGURASI HALAMAN & COOKIE ---
st.set_page_config(page_title="Sistem Absensi Sekolah Cabdis Wil IV", page_icon="🏫", layout="wide", initial_sidebar_state="expanded")
cookie_manager = stx.CookieManager(key="cookie_manager_utama")

# --- 3. CUSTOM CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Poppins', sans-serif !important; }
    
    /* MENYEMBUNYIKAN HEADER & TOOLBAR BAWAAN STREAMLIT */
    header { visibility: hidden !important; height: 0px !important; } 
    [data-testid="stToolbar"], [data-testid="stDecoration"], footer, #MainMenu { visibility: hidden !important; }
    [data-testid="stHeaderActionElements"], .header-anchor { display: none !important; }
    
    /* SETTING SIDEBAR PATEN, LEBAR PROPORSIONAL & LEGA */
    [data-testid="stSidebar"] {
        width: 280px !important;
        min-width: 280px !important;
        max-width: 280px !important;
        background-color: #F8FAFC !important;
        border-right: 1px solid #E2E8F0 !important;
        transform: none !important;
        visibility: visible !important;
        display: block !important;
    }
    
    /* MENYESUAIKAN CONTAINER UTAMA AGAR TIDAK TERTUTUP SIDEBAR */
    section[data-testid="stSidebar"] + section {
        margin-left: 0px !important;
    }
    
    /* SEMBUNYIKAN TOMBOL PANAH PENUTUP SIDEBAR */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="collapsedControl"],
    button[aria-label="Close sidebar"],
    button[aria-label="Collapse sidebar"] {
        display: none !important;
    }
    
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
    .stForm, div[data-testid="stExpander"] {
        background-color: #FFFFFF; padding: 24px; border-radius: 12px;
        box-shadow: 0px 4px 15px rgba(0, 0, 0, 0.05); border: 1px solid #E2E8F0;
    }
    div.stButton > button {
        background-color: #2563EB !important; color: white !important; font-weight: 600 !important;
        border-radius: 8px !important; border: none !important; transition: 0.3s;
    }
    div.stButton > button:hover { background-color: #1D4ED8 !important; box-shadow: 0 4px 10px rgba(37, 99, 235, 0.3); }
    
    /* DESAIN MENU SIDEBAR (SPASI PADAT & HURUF PAS DENGAN INFO AKUN) */
    div.row-widget.stRadio > div { 
        gap: 0.4rem !important; 
    }
    div.row-widget.stRadio > div > label {
        background-color: #ffffff; 
        padding: 10px 14px; 
        border-radius: 3px;
        border: 1px solid #E2E8F0; 
        cursor: pointer; 
        transition: 0.3s;
    }
    
    /* UKURAN HURUF MENU SIDEBAR */
    div.row-widget.stRadio > div > label > div.st-markdown-container > p {
        font-size: 1rem !important; 
        font-weight: 700 !important;
    }
    
    div.row-widget.stRadio > div > label:hover { background-color: #F1F5F9; border-color: #CBD5E1; }
    div.row-widget.stRadio > div > label[data-checked="true"] {
        background-color: #2563EB !important; color: white !important;
        border-color: #2563EB !important; box-shadow: 0 4px 10px rgba(37, 99, 235, 0.2);
    }
    /* MENGHILANGKAN BULATAN RADIO BAWAAN */
    div.row-widget.stRadio > div > label > div:first-child { display: none; }
    </style>
""", unsafe_allow_html=True)

# --- 4. FUNGSI INTERAKSI DATABASE (OPTIMASI CACHING UNTUK MENGHEMAT EGRESS) ---
@st.cache_data(ttl=86400)
def get_data_sekolah():
    try:
        res = supabase.table('sekolah').select('school_name, lat, lng, radius_m').execute()
        if res.data: return pd.DataFrame(res.data)
    except: pass
    return pd.DataFrame(columns=['school_name', 'lat', 'lng', 'radius_m'])

@st.cache_data(ttl=86400)
def get_data_admin():
    try:
        res = supabase.table('admins').select('id, username, password, sekolah').execute()
        if res.data: return pd.DataFrame(res.data)
    except: pass
    return pd.DataFrame(columns=['id', 'username', 'password', 'sekolah'])

@st.cache_data(ttl=86400)
def get_data_pengaturan():
    try:
        # Tambahkan query gps_aktif
        res = supabase.table('pengaturan').select('batas_masuk, batas_pulang, gps_aktif').execute()
        if res.data and len(res.data) > 0:
            return pd.DataFrame(res.data)
        else:
            default_data = {'batas_masuk': '07:30', 'batas_pulang': '16:00', 'gps_aktif': True}
            supabase.table('pengaturan').insert(default_data).execute()
            return pd.DataFrame([default_data])
    except:
        return pd.DataFrame([{'batas_masuk': '07:30', 'batas_pulang': '16:00', 'gps_aktif': True}])

def parse_jam_str(jam_val):
    if not jam_val or str(jam_val).strip() in ['-', 'None', 'nan', '']:
        return None
    s = str(jam_val).strip()
    parts = s.split(':')
    if len(parts) >= 2:
        try:
            hh = int(parts[0].strip())
            mm = int(parts[1][:2].strip())
            return f"{hh:02d}:{mm:02d}"
        except:
            return None
    return None

def hitung_selisih_menit(jam_aktual, jam_batas, jenis):
    """Fungsi pembantu untuk menghitung selisih keterlambatan atau cepat pulang dalam menit"""
    try:
        t_aktual = datetime.datetime.strptime(jam_aktual, '%H:%M')
        t_batas = datetime.datetime.strptime(jam_batas, '%H:%M')
        
        if jenis == "terlambat":
            diff = t_aktual - t_batas
        else: # cepat pulang
            diff = t_batas - t_aktual
            
        menit = int(diff.total_seconds() / 60)
        return menit if menit > 0 else 0
    except Exception:
        return 0

# Helper Rekap Absensi Berdasarkan Pengaturan Jam
def proses_rekap_absensi(nama_sekolah, tgl_mulai, tgl_selesai):
    start_d = tgl_mulai.strftime('%Y-%m-%d')
    end_d = tgl_selesai.strftime('%Y-%m-%d')
    
    # 1. Hitung hari kerja (Senin-Jumat)
    rentang_tanggal = pd.date_range(start=start_d, end=end_d)
    total_hari_kerja = len(rentang_tanggal[rentang_tanggal.dayofweek < 5])

    # 2. Ambil data pegawai
    res_pegawai = supabase.table('pegawai').select('nip, name, school_name').ilike('school_name', f"%{nama_sekolah.strip()}%").execute()
    df_pegawai = pd.DataFrame(res_pegawai.data) if res_pegawai.data else pd.DataFrame()

    if df_pegawai.empty:
        return None, total_hari_kerja

    # 3. Ambil pengaturan Jam Kerja dari Superadmin (Cached)
    df_settings = get_data_pengaturan()
    b_masuk = df_settings['batas_masuk'].iloc[0] if not df_settings.empty else '07:30'
    b_pulang = df_settings['batas_pulang'].iloc[0] if not df_settings.empty else '16:00'
    
    b_masuk_clean = parse_jam_str(b_masuk) or '07:30'
    b_pulang_clean = parse_jam_str(b_pulang) or '16:00'

    # 4. Ambil data absensi
    try:
        res_absen = supabase.table('absensi').select('nip, status, jam, tanggal').ilike('sekolah', f"%{nama_sekolah.strip()}%").gte('tanggal', start_d).lte('tanggal', end_d).execute()
        df_absen = pd.DataFrame(res_absen.data) if res_absen.data else pd.DataFrame()
    except Exception:
        df_absen = pd.DataFrame()

    # 5. Olah data rekap per pegawai
    rekap_data = []
    for _, emp in df_pegawai.iterrows():
        emp_nip = str(emp['nip']).strip()
        emp_name = emp['name']
        emp_school = emp.get('school_name', nama_sekolah)

        t_terlambat = 0
        t_cepat_pulang = 0
        t_izin = 0
        hari_hadir_set = set()

        if not df_absen.empty and 'nip' in df_absen.columns:
            emp_records = df_absen[df_absen['nip'].astype(str).str.strip() == emp_nip]
            
            # Kelompokkan absensi berdasarkan tanggal untuk mengecek histori harian
            if not emp_records.empty:
                for tgl_val, group in emp_records.groupby('tanggal'):
                    hari_hadir_set.add(tgl_val)
                    
                    status_harian = group['status'].astype(str).str.strip().str.upper().tolist()
                    
                    # Jika hari itu statusnya izin/sakit/cuti/DL/manual, langsung dihitung Izin
                    is_izin = any(s not in ['DATANG', 'PULANG'] for s in status_harian)
                    if is_izin:
                        t_izin += 1
                        continue
                    
                    has_datang = False
                    has_pulang = False
                    
                    for _, r in group.iterrows():
                        status_raw = str(r.get('status', '')).strip().upper()
                        jam_clean = parse_jam_str(r.get('jam'))
                        
                        if status_raw == 'DATANG':
                            has_datang = True
                            if jam_clean and jam_clean > b_masuk_clean:
                                t_terlambat += hitung_selisih_menit(jam_clean, b_masuk_clean, "terlambat")
                        elif status_raw == 'PULANG':
                            if jam_clean and jam_clean < b_pulang_clean:
                                t_cepat_pulang += hitung_selisih_menit(jam_clean, b_pulang_clean, "cepat_pulang")
                    
                    # TAMBAHAN PERHITUNGAN: Jika hari itu hadir (ada absen Pulang) tapi TIDAK absen MASUK
                    if has_pulang and not has_datang:
                        t_terlambat += 495
                    if has_datang and not has_pulang:
                        t_cepat_pulang += 495

        hari_ada_catatan = len(hari_hadir_set)
        alpha = max(0, total_hari_kerja - hari_ada_catatan)

        rekap_data.append({
            'NIP': emp_nip, 
            'Nama Pegawai': emp_name,
            'Nama Sekolah': emp_school,
            'Total Terlambat (Menit)': t_terlambat,
            'Total Cepat Pulang (Menit)': t_cepat_pulang,
            'Total Izin/Cuti/Sakit/DL': t_izin,
            'Tanpa Keterangan': alpha
        })

    return pd.DataFrame(rekap_data), total_hari_kerja

# --- 5. INISIALISASI SESSION STATE ---
for key_state, val in {
    'role': None, 
    'admin_sekolah': "Semua Sekolah", 
    'logout_triggered': False, 
    'wajah_terverifikasi': False, 
    'pending_pc_name': None, 
    'last_searched_nip_foto': None, 
    'last_checked_nip_dash': None,
    'last_searched_school_pc': None,
    'menu_unlocked': False,
    'admin_dashboard_unlocked': False,
    'edit_nip_target': None,
    'show_photo_nip': None
}.items():
    if key_state not in st.session_state: st.session_state[key_state] = val

raw_token = cookie_manager.get("auth_token")
saved_admin_school = cookie_manager.get("admin_sekolah")
if saved_admin_school: st.session_state.admin_sekolah = saved_admin_school

valid_role = verify_and_get_role(raw_token)

if st.session_state.role is not None:
    st.session_state.logout_triggered = False
elif st.session_state.logout_triggered:
    if raw_token is None: st.session_state.logout_triggered = False 
else:
    if valid_role and valid_role != "Pegawai": 
        st.session_state.role = valid_role
    elif raw_token and (not valid_role or valid_role == "Pegawai"):
        st.session_state.role = None
        try:
            cookie_manager.delete("auth_token", key="del_auth_invalid_role")
            cookie_manager.delete("admin_sekolah", key="del_sch_invalid_role")
        except: pass

def logout():
    st.session_state.role = None
    st.session_state.admin_sekolah = "Semua Sekolah"
    st.session_state.logout_triggered = True 
    st.session_state.wajah_terverifikasi = False 
    st.session_state.menu_unlocked = False
    st.session_state.admin_dashboard_unlocked = False
    st.session_state.edit_nip_target = None
    st.session_state.show_photo_nip = None
    
    st.session_state.last_searched_nip_foto = None
    st.session_state.last_checked_nip_dash = None
    st.session_state.last_searched_school_pc = None
    
    try:
        cookie_manager.delete("auth_token", key="delete_auth_token_btn")
        cookie_manager.delete("role", key="delete_role_btn") 
        cookie_manager.delete("admin_sekolah", key="delete_admin_sekolah_btn") 
    except: pass

# ==========================================
# HALAMAN LOGIN UTAMA (KHUSUS ADMIN & SUPERADMIN)
# ==========================================
if st.session_state.role is None:
    st.title("📜 AKSES ADMIN ABSENSI SATUAN PENDIDIKAN CABDIS WIL IV")
    st.info("Selamat datang! Silakan masuk ke akun pengelola sistem di bawah ini.")

    st.caption("Akses Pengelola Sistem:")
    col_admin, col_super = st.columns(2)

    with col_admin:
        with st.expander("🔑 Login Admin Sekolah", expanded=True):
            input_user_admin = st.text_input("Username Admin:", key="user_admin_main")
            pwd = st.text_input("Password Admin:", type="password", key="pwd_admin_main")
            if st.button("Masuk Admin", width="stretch", key="btn_admin_main"):
                df_adm = get_data_admin()
                is_valid = False
                assigned_school = "Semua Sekolah"
                if not df_adm.empty and 'username' in df_adm.columns:
                    match = df_adm[(df_adm['username'] == input_user_admin.strip()) & (df_adm['password'] == pwd)]
                    if not match.empty:
                        is_valid = True
                        assigned_school = match.iloc[0]['sekolah']
                if is_valid: 
                    st.session_state.role = "Admin"
                    st.session_state.admin_sekolah = assigned_school
                    cookie_manager.set("auth_token", generate_signed_token("Admin"), key="set_token_login_admin")
                    cookie_manager.set("admin_sekolah", assigned_school, key="set_sch_login_admin")
                    time.sleep(0.5)
                    st.rerun()
                else: st.error("Username atau Password Salah!")

    with col_super:
        with st.expander("🛠️ Login Superadmin", expanded=True):
            pwd_super = st.text_input("Password Superadmin:", type="password", key="pwd_super_main")
            if st.button("Masuk Superadmin", width="stretch", key="btn_super_main"):
                if pwd_super == SUPERADMIN_PASSWORD:
                    st.session_state.role = "Superadmin"
                    cookie_manager.set("auth_token", generate_signed_token("Superadmin"), key="set_token_login_super")
                    time.sleep(0.5)
                    st.rerun()
                else: st.error("Password Salah!")
    st.stop()

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.title("Informasi Akun")
st.sidebar.success(f"Akses: **{st.session_state.role}**")
if st.session_state.role == "Admin": st.sidebar.caption(f"Unit Kerja: {st.session_state.admin_sekolah}")
st.sidebar.write("---")
waktu_sekarang = datetime.datetime.now(pytz.timezone('Asia/Makassar'))
st.sidebar.markdown("**Waktu Server (WITA):**")
st.sidebar.info(f"🕒 {waktu_sekarang.strftime('%H:%M:%S')} WITA\n\n📅 {waktu_sekarang.strftime('%d-%m-%Y')}")
st.sidebar.write("---")

# FITUR BARU: MENU NAVIGASI KIRI KHUSUS SUPERADMIN
menu_superadmin = None
if st.session_state.role == "Superadmin":
    st.sidebar.markdown("### 🎛️ Menu Navigasi")
    menu_superadmin = st.sidebar.radio(
        "Pilih Halaman:",
        [
            "📈 Rekap Absensi", 
            "🟥 Laporan Indisipliner",
            "🏛️ Data Sekolah", 
            "💻 Kunci PC", 
            "👥 Data Pegawai", 
            "🔑 Akun Admin", 
            "📝 Izin & Manual", 
            "🚨 Database", 
            "⚙️ Jam & GPS"
        ],
        label_visibility="collapsed"
    )
    st.sidebar.write("---")

# ==========================================
# HAK AKSES 1: ADMIN SEKOLAH
# ==========================================
if st.session_state.role == "Admin":
    col_judul, col_tombol = st.columns([3, 1])
    col_judul.title("🔐 Dashboard Admin Sekolah")
    col_tombol.button("🚪 Logout", on_click=logout, width="stretch", key="btn_logout_top_admin")
    admin_akses = st.session_state.get('admin_sekolah', 'Semua Sekolah')

    tab_foto, tab_dashboard = st.tabs([
        "📸 1. Upload Foto Pegawai", 
        "📊 2. Dashboard Cek Absensi"
    ])

    # ------------------------------------------
    # MENU 1: UPLOAD FOTO PEGAWAI
    # ------------------------------------------
    with tab_foto:
        st.markdown("### 📸 Upload Foto Pegawai")
        st.caption("Ketik NIP Pegawai secara spesifik untuk memuat data.")
        
        with st.form("form_cari_nip_foto"):
            nip_input_foto = st.text_input("Masukkan NIP Pegawai:", placeholder="Contoh: 198001012005011001", key="input_nip_foto_admin")
            btn_cari_nip = st.form_submit_button("🔍 Cari Data Pegawai")
            
        if btn_cari_nip:
            searched_nip = nip_input_foto.strip()
            if searched_nip:
                st.session_state.last_searched_nip_foto = searched_nip
            else:
                st.session_state.last_searched_nip_foto = None
                st.warning("Silahkan masukkan NIP terlebih dahulu.")

        if st.session_state.last_searched_nip_foto:
            snip = st.session_state.last_searched_nip_foto
            try:
                query_peg = supabase.table('pegawai').select('nip, name, school_name, photo_uploaded, photo_base64, is_cadar').eq('nip', str(snip))
                if admin_akses != "Semua Sekolah":
                    query_peg = query_peg.eq('school_name', admin_akses)
                res_peg = query_peg.execute()
                df_peg_found = pd.DataFrame(res_peg.data) if res_peg.data else pd.DataFrame()
            except:
                df_peg_found = pd.DataFrame()

            if df_peg_found.empty:
                html_swal_nip = """
                <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
                <script>
                    setTimeout(() => {
                        Swal.fire({
                            title: 'Peringatan!',
                            text: 'DATA ASN TIDAK DITEMUKAN SILAHKAN MELAPORKAN KE ADMIN CABDIS (MOCHD GHAZALI/JEDDAH/GAZA)',
                            icon: 'warning',
                            confirmButtonText: 'Oke',
                            confirmButtonColor: '#2563EB',
                            allowOutsideClick: false
                        });
                    }, 100);
                </script>
                """
                st.html(html_swal_nip)
                st.error("⚠️ DATA ASN TIDAK DITEMUKAN SILAHKAN MELAPORKAN KE ADMIN CABDIS (MOCHD GHAZALI/JEDDAH/GAZA)")
            else:
                emp = df_peg_found.iloc[0]
                nip_peg, nama_peg = str(emp['nip']), emp['name']
                is_cadar = str(emp.get('is_cadar', 'False')).lower() == 'true'
                is_uploaded = str(emp.get('photo_uploaded', False)).lower() == 'true'
                
                status_str = "🧕 Cadar (Audit)" if is_cadar else ("🟢 Foto Terunggah (Terkunci)" if is_uploaded else "🔴 Belum Ada Foto")
                st.success(f"✅ Data Ditemukan: **{nama_peg}** ({status_str})")
                
                col_f_kiri, col_f_kanan = st.columns([1, 2])
                with col_f_kiri:
                    if is_uploaded:
                        st.success("📷 Foto acuan sudah terunggah dan dikunci dalam sistem.")
                    else:
                        st.info("📷 Belum ada foto acuan.")
                        
                with col_f_kanan:
                    st.write(f"**Nama:** {nama_peg}")
                    st.write(f"**NIP:** {nip_peg}")
                    st.write(f"**Sekolah:** {emp['school_name']}")
                    
                    if is_uploaded:
                        st.warning("🔒 **FOTO TERKUNCI!** Foto acuan pegawai ini telah diunggah dan terkunci. Jika ingin mengubah foto, silakan hubungi Superadmin untuk membukakan kuncinya.")
                    else:
                        foto_file = st.file_uploader("Pilih Foto Acuan (Maksimal 3MB, JPG/PNG):", type=['jpg', 'jpeg', 'png'], key=f"up_foto_file_{nip_peg}")
                        
                        if foto_file:
                            if foto_file.size > 3145728:
                                st.error("❌ Ukuran foto terlalu besar! Maksimal ukuran file adalah 3MB. Silakan kompres/perkecil foto Anda terlebih dahulu.")
                            else:
                                if st.button("💾 Simpan Foto Acuan", key=f"btn_save_foto_{nip_peg}", width="stretch"):
                                    file_bytes = kompres_foto(foto_file.getvalue(), quality=60, max_size=(600, 600))
                                    url_foto = upload_ke_supabase(file_bytes, f"foto_acuan/{nip_peg}.jpg", "image/jpeg")
                                    if url_foto:
                                        supabase.table('pegawai').update({'photo_uploaded': True, 'photo_base64': url_foto}).eq('nip', nip_peg).execute()
                                        st.success("✅ Foto acuan berhasil disimpan & otomatis terkunci!")
                                        time.sleep(1)
                                        st.rerun()

    # ------------------------------------------
    # MENU 2: DASHBOARD CEK ABSENSI PEGAWAI
    # ------------------------------------------
    with tab_dashboard:
        if not st.session_state.get('admin_dashboard_unlocked', False):
            st.warning("🔒 AGA SI MUALA MAKECCA Menu ini dikunci SELESAIKAN TUGAS UPLOAD FOTO JIKA SUDAH LANGSUNG LOGOUT.")
            pw_dash_admin = st.text_input("Masukkan Sandi Khusus:", type="password", key="pw_dash_admin")
            if st.button("🔓 Buka Dashboard", key="btn_buka_dash_admin", type="primary"):
                if pw_dash_admin == "SandiMenu2026*":
                    st.session_state['admin_dashboard_unlocked'] = True
                    st.success("✅ Dashboard terbuka!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("❌ Sandi salah!")
        else:
            if st.button("🔒 Kunci Kembali Dashboard", key="btn_lock_again_dash_admin"):
                st.session_state['admin_dashboard_unlocked'] = False
                st.rerun()

            st.markdown("### 📊 Dashboard Cek Absensi Pegawai")
            st.caption("Masukkan NIP pegawai dan pilih tanggal untuk mengecek status absensi.")
            
            col_d1, col_d2 = st.columns([2, 1])
            with col_d1:
                nip_check_input = st.text_input("Masukkan NIP Pegawai:", placeholder="Contoh: 198001012005011001", key="nip_check_dashboard")
            with col_d2:
                tgl_check_input = st.date_input("Pilih Tanggal:", datetime.date.today(), key="tgl_check_dashboard")
                
            btn_cek_dash = st.button("🔍 Cek Status Absensi", type="primary", width="stretch", key="btn_cek_absensi_dash")
            
            if btn_cek_dash:
                if nip_check_input.strip():
                    st.session_state.last_checked_nip_dash = nip_check_input.strip()
                else:
                    st.session_state.last_checked_nip_dash = None
                    st.warning("Silahkan masukkan NIP terlebih dahulu.")

            if st.session_state.last_checked_nip_dash:
                cnip = st.session_state.last_checked_nip_dash
                tgl_pilihan_str = tgl_check_input.strftime('%Y-%m-%d')
                
                try:
                    q_p = supabase.table('pegawai').select('nip, name, school_name').eq('nip', str(cnip))
                    if admin_akses != "Semua Sekolah":
                        q_p = q_p.eq('school_name', admin_akses)
                    res_p = q_p.execute()
                    df_p_check = pd.DataFrame(res_p.data) if res_p.data else pd.DataFrame()
                except: df_p_check = pd.DataFrame()

                if df_p_check.empty:
                    st.warning("⚠️ Data pegawai dengan NIP tersebut tidak ditemukan di sekolah ini.")
                else:
                    emp_d = df_p_check.iloc[0]
                    
                    try:
                        res_a = supabase.table('absensi').select('status, jam, jarak_m, foto_bukti').eq('nip', str(cnip)).eq('tanggal', tgl_pilihan_str).execute()
                        df_a_check = pd.DataFrame(res_a.data) if res_a.data else pd.DataFrame()
                    except: df_a_check = pd.DataFrame()
                    
                    st.markdown("---")
                    st.markdown(f"#### 👤 **{emp_d['name']}** (NIP: {cnip})")
                    st.markdown(f"🏫 **Sekolah:** {emp_d['school_name']} | 📅 **Tanggal:** {tgl_check_input.strftime('%d-%m-%Y')}")
                    
                    if df_a_check.empty:
                        st.error("❌ **STATUS: BELUM LAKUKAN ABSENSI / TIDAK ADA CATATAN PRESENSI**")
                    else:
                        st.success("✅ **STATUS: SUDAH MELAKUKAN ABSENSI**")
                        
                        for idx_a, r_a in df_a_check.iterrows():
                            with st.expander(f"📌 Presensi: {r_a.get('status', '-')} — Jam: {r_a.get('jam', '-')}", expanded=True):
                                c_info, c_foto = st.columns([2, 1])
                                c_info.write(f"**Status Log:** {r_a.get('status', '-')}")
                                c_info.write(f"**Waktu Presensi:** {r_a.get('jam', '-')} WITA")
                                c_info.write(f"**Jarak dari Sekolah:** {r_a.get('jarak_m', '-')} meter")
                                
                                foto_url = r_a.get('foto_bukti', '')
                                if foto_url:
                                    c_foto.image(foto_url, caption="Foto Bukti Absen", width="stretch")

# ==========================================
# HAK AKSES 2: SUPERADMIN
# ==========================================
elif st.session_state.role == "Superadmin":
    col_judul, col_tombol = st.columns([3, 1])
    col_judul.title(f"🛠️ {menu_superadmin}") # Judul dinamis mengikuti menu kiri
    col_tombol.button("🚪 Logout", on_click=logout, width="stretch", key="btn_logout_superadmin")

    if st.session_state.get('menu_unlocked', False):
        if st.button("🔒 Kunci Kembali Layar Menu Admin", key="btn_lock_menu_again"):
            st.session_state['menu_unlocked'] = False
            st.rerun()

    def tampilkan_form_kunci(nama_tab):
        st.warning(f"🔒 Menu **{nama_tab}** dikunci untuk mencegah kesalahan modifikasi.")
        pw_input = st.text_input("Masukkan Sandi Khusus Menu:", type="password", key=f"pw_lock_{nama_tab}")
        if st.button("🔓 Buka Akses Menu", key=f"btn_lock_{nama_tab}", type="primary"):
            if pw_input == SUPERADMIN_MENU_PASSWORD:
                st.session_state['menu_unlocked'] = True
                st.success("✅ Akses menu berhasil dibuka!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("❌ Sandi menu salah!")

    st.write("") # Memberi jarak putih ekstra agar UI bernafas (elegan)

    # ------------------------------------------
    # 1. MENU REKAP ABSENSI (BEBAS AKSES)
    # ------------------------------------------
    if menu_superadmin == "📈 Rekap Absensi":
        st.markdown("### 📈 Rekap Absensi Keseluruhan Pegawai")
        st.caption("Tarik rekap data absensi semua pegawai berdasarkan sekolah dan rentang waktu (Harian/Mingguan/Bulanan).")

        with st.form("form_rekap_absensi"):
            sekolah_rekap = st.text_input("Masukkan Nama Sekolah:", placeholder="Contoh: SMAN 1 WAJO", key="input_sekolah_rekap")

            col_tgl1, col_tgl2 = st.columns(2)
            with col_tgl1:
                tgl_mulai_rekap = st.date_input("Dari Tanggal", datetime.date.today(), key="tm_rekap")
            with col_tgl2:
                tgl_selesai_rekap = st.date_input("Sampai Tanggal", datetime.date.today(), key="ts_rekap")

            btn_rekap = st.form_submit_button("🔍 Tampilkan Rekap")

        if btn_rekap:
            if not sekolah_rekap.strip():
                st.warning("Silakan masukkan nama sekolah terlebih dahulu.")
            elif tgl_mulai_rekap > tgl_selesai_rekap:
                st.error("Tanggal selesai tidak boleh lebih awal dari tanggal mulai.")
            else:
                try:
                    df_final, total_hari_kerja = proses_rekap_absensi(sekolah_rekap, tgl_mulai_rekap, tgl_selesai_rekap)
                    if df_final is None or df_final.empty:
                        st.info(f"Tidak ada pegawai ditemukan di: **{sekolah_rekap}**")
                    else:
                        st.success(f"✅ Data berhasil ditarik. Total Hari Kerja (Senin-Jumat): **{total_hari_kerja} Hari**")
                        st.dataframe(df_final, width="stretch")

                        # Download Excel
                        buffer_rekap = io.BytesIO()
                        with pd.ExcelWriter(buffer_rekap, engine='openpyxl') as writer:
                            df_final.to_excel(writer, index=False, sheet_name='Rekap_Absensi')
                        
                        st.download_button(
                            label="📥 Download Rekap (Excel)",
                            data=buffer_rekap.getvalue(),
                            file_name=f"Rekap_{sekolah_rekap}_{tgl_mulai_rekap.strftime('%d%m%Y')}-{tgl_selesai_rekap.strftime('%d%m%Y')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                            key="dl_rekap_excel"
                        )
                except Exception as e:
                    st.error(f"Terjadi kesalahan: {e}")

    # ------------------------------------------
    # 2. MENU LAPORAN INDISIPLINER (BEBAS AKSES)
    # ------------------------------------------
    elif menu_superadmin == "🟥 Laporan Indisipliner":
        st.markdown("### 🟥 Laporan Indisipliner Pegawai (Tanpa Keterangan)")
        st.caption("Khusus menyaring pegawai yang memiliki catatan Tanpa Keterangan (Alpha) 1 hari atau lebih.")

        with st.form("form_indisipliner"):
            sekolah_indi = st.text_input("Masukkan Nama Sekolah:", placeholder="Contoh: SMAN 1 WAJO", key="input_sekolah_indi")

            col_tgl1_i, col_tgl2_i = st.columns(2)
            with col_tgl1_i:
                tgl_mulai_indi = st.date_input("Dari Tanggal", datetime.date.today(), key="tm_indi")
            with col_tgl2_i:
                tgl_selesai_indi = st.date_input("Sampai Tanggal", datetime.date.today(), key="ts_indi")

            btn_indi = st.form_submit_button("🚨 Tampilkan Laporan Indisipliner")

        if btn_indi:
            if not sekolah_indi.strip():
                st.warning("Silakan masukkan nama sekolah terlebih dahulu.")
            elif tgl_mulai_indi > tgl_selesai_indi:
                st.error("Tanggal selesai tidak boleh lebih awal dari tanggal mulai.")
            else:
                try:
                    df_res, _ = proses_rekap_absensi(sekolah_indi, tgl_mulai_indi, tgl_selesai_indi)
                    if df_res is None or df_res.empty:
                        st.info(f"Tidak ada pegawai ditemukan di: **{sekolah_indi}**")
                    else:
                        df_indisipliner = df_res[df_res['Tanpa Keterangan'] >= 1]

                        if df_indisipliner.empty:
                            st.success("🎉 **SANGAT BAIK:** Tidak ditemukan pegawai indisipliner pada periode ini.")
                        else:
                            st.error(f"⚠️ Ditemukan **{len(df_indisipliner)} Pegawai** dengan catatan Tanpa Keterangan (Alpha) ≥ 1 hari!")
                            st.dataframe(df_indisipliner, width="stretch")
                            
                            buffer_indi = io.BytesIO()
                            with pd.ExcelWriter(buffer_indi, engine='openpyxl') as writer:
                                df_indisipliner.to_excel(writer, index=False, sheet_name='Indisipliner')
                            
                            st.download_button(
                                label="📥 Download Laporan Indisipliner (Excel)",
                                data=buffer_indi.getvalue(),
                                file_name=f"Indisipliner_{sekolah_indi}_{tgl_mulai_indi.strftime('%d%m%Y')}-{tgl_selesai_indi.strftime('%d%m%Y')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                                key="dl_indi_excel"
                            )
                except Exception as e:
                    st.error(f"Terjadi kesalahan: {e}")

    # ------------------------------------------
    # 3. MENU DATA SEKOLAH (TERKUNCI)
    # ------------------------------------------
    elif menu_superadmin == "🏛️ Data Sekolah":
        if not st.session_state['menu_unlocked']:
            tampilkan_form_kunci("Sekolah")
        else:
            st.markdown("### Sekolah Aktif")
            df_sekolah_curr = get_data_sekolah()
            edited_schools = st.data_editor(df_sekolah_curr, num_rows="dynamic", width="stretch")
            if st.button("💾 Simpan Perubahan Sekolah", type="primary"):
                try:
                    df_clean = edited_schools.copy()
                    df_clean['school_name'] = df_clean['school_name'].astype(str).str.strip()
                    df_clean = df_clean[~df_clean['school_name'].isin(['', 'None', 'nan', 'NaN'])]
                    
                    if not df_clean.empty:
                        records = []
                        for _, row in df_clean.iterrows():
                            try: lat_val = float(row['lat']) if pd.notna(row['lat']) else 0.0
                            except: lat_val = 0.0
                                
                            try: lng_val = float(row['lng']) if pd.notna(row['lng']) else 0.0
                            except: lng_val = 0.0
                                
                            try: rad_val = int(row['radius_m']) if pd.notna(row['radius_m']) else 100
                            except: rad_val = 100

                            records.append({
                                'school_name': str(row['school_name']).strip(),
                                'lat': lat_val, 'lng': lng_val, 'radius_m': rad_val
                            })
                        
                        supabase.table('sekolah').upsert(records).execute()
                        st.cache_data.clear()
                        st.success("✅ Data sekolah berhasil disimpan/diperbarui!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.warning("⚠️ Silahkan isi nama sekolah terlebih dahulu.")
                except Exception as e:
                    st.error(f"❌ Gagal menyimpan ke database: {e}")

    # ------------------------------------------
    # 4. MENU KUNCI PC (TERKUNCI)
    # ------------------------------------------
    elif menu_superadmin == "💻 Kunci PC":
        if not st.session_state['menu_unlocked']:
            tampilkan_form_kunci("PC")
        else:
            st.markdown("""
                <style>
                div[data-testid="column"]:nth-of-type(3) button {
                    background-color: #10B981 !important; box-shadow: 0 4px 10px rgba(16, 185, 129, 0.3) !important;
                }
                div[data-testid="column"]:nth-of-type(3) button:hover { background-color: #059669 !important; }
                </style>
            """, unsafe_allow_html=True)

            st.markdown("### 🔑 Kelola & Generate Kunci Perangkat PC")
            st.caption("Ketik nama sekolah untuk membuat kunci PC baru atau mencari kunci yang sudah ada.")
            
            df_sekolah_aktif = get_data_sekolah()
            daftar_sekolah = df_sekolah_aktif['school_name'].tolist() if not df_sekolah_aktif.empty else []

            with st.form("form_pc_superadmin"):
                sekolah_input_pc = st.text_input("Masukkan Nama Sekolah:", placeholder="Contoh: SMKN 6 WAJO", key="input_sekolah_pc_super")
                
                col_b1, col_b2, col_b3 = st.columns(3)
                btn_cari_pc = col_b1.form_submit_button("🔍 Cari PC Sekolah", width="stretch")
                btn_generate_pc = col_b2.form_submit_button("🔑 Generate 3 Kunci PC", type="primary", width="stretch")
                btn_generate_1_pc = col_b3.form_submit_button("➕ GENERATE 1 KUNCI PC", width="stretch")
            
            if btn_generate_1_pc:
                nama_sekolah_clean = sekolah_input_pc.strip()
                if not nama_sekolah_clean:
                    st.warning("⚠️ Silahkan masukkan Nama Sekolah terlebih dahulu!")
                elif nama_sekolah_clean not in daftar_sekolah:
                    st.error("NAMA SEKOLAH BELUM ADA LABANTA")
                else:
                    try:
                        prefix = "".join(e for e in nama_sekolah_clean if e.isalnum()).upper()[:8]
                        kunci_baru = f"{prefix}-{uuid.uuid4().hex[:5].upper()}"

                        supabase.table('kunci_perangkat').insert({
                            "kunci": kunci_baru, "sekolah": nama_sekolah_clean, "status": "BELUM_TERPAKAI"
                        }).execute()
                        
                        st.success(f"✅ Berhasil menambah 1 Kunci PC BARU untuk **{nama_sekolah_clean}**!")
                        st.session_state.last_searched_school_pc = nama_sekolah_clean
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Gagal membuat kunci: {e}")

            if btn_generate_pc:
                nama_sekolah_clean = sekolah_input_pc.strip()
                if not nama_sekolah_clean:
                    st.warning("⚠️ Silahkan masukkan Nama Sekolah terlebih dahulu!")
                elif nama_sekolah_clean not in daftar_sekolah:
                    st.error("NAMA SEKOLAH BELUM ADA LABANTA")
                else:
                    try:
                        res_cek = supabase.table('kunci_perangkat').select('status').ilike('sekolah', f"%{nama_sekolah_clean}%").eq('status', 'TERPAKAI').execute()
                        
                        if res_cek.data and len(res_cek.data) > 0:
                            st.error(f"🚫 GAGAL GENERATE: Masih ada PC yang berstatus TERPAKAI di unit kerja **{nama_sekolah_clean}**!")
                            st.warning("💡 Solusi: Silakan klik 'Cari PC Sekolah' lalu hapus terlebih dahulu kunci yang berstatus TERPAKAI sebelum membuat kunci baru.")
                        else:
                            prefix = "".join(e for e in nama_sekolah_clean if e.isalnum()).upper()[:8]
                            kunci_1 = f"{prefix}-{uuid.uuid4().hex[:5].upper()}"
                            kunci_2 = f"{prefix}-{uuid.uuid4().hex[:5].upper()}"
                            kunci_3 = f"{prefix}-{uuid.uuid4().hex[:5].upper()}"

                            records = [
                                {"kunci": kunci_1, "sekolah": nama_sekolah_clean, "status": "BELUM_TERPAKAI"},
                                {"kunci": kunci_2, "sekolah": nama_sekolah_clean, "status": "BELUM_TERPAKAI"},
                                {"kunci": kunci_3, "sekolah": nama_sekolah_clean, "status": "BELUM_TERPAKAI"}
                            ]

                            supabase.table('kunci_perangkat').upsert(records, on_conflict='kunci').execute()
                            st.success(f"✅ Berhasil membuat 3 Kunci PC BARU untuk **{nama_sekolah_clean}**!")
                            st.session_state.last_searched_school_pc = nama_sekolah_clean
                            time.sleep(1.5)
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Gagal melakukan pengecekan atau pembuatan kunci: {e}")

            if btn_cari_pc:
                nama_sekolah_clean = sekolah_input_pc.strip()
                if not nama_sekolah_clean:
                    st.warning("⚠️ Silahkan ketik nama sekolah terlebih dahulu.")
                elif nama_sekolah_clean not in daftar_sekolah:
                    st.error("NAMA SEKOLAH BELUM ADA LABANTA")
                else:
                    st.session_state.last_searched_school_pc = nama_sekolah_clean
                    
            if st.session_state.get('last_searched_school_pc'):
                nama_sekolah_dicari = st.session_state.last_searched_school_pc
                try:
                    res_pc_super = supabase.table('kunci_perangkat').select('*').ilike('sekolah', f"%{nama_sekolah_dicari}%").execute()
                    
                    if res_pc_super.data:
                        df_kunci = pd.DataFrame(res_pc_super.data)
                        st.success(f"✅ Ditemukan {len(df_kunci)} Kunci PC untuk: **{nama_sekolah_dicari}**")
                        
                        for idx, r_pc in df_kunci.iterrows():
                            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                            c1.write(f"🏫 **{r_pc['sekolah']}**")
                            c2.write(f"🔑 `{r_pc['kunci']}`")
                            
                            status_str = r_pc.get('status', 'BELUM_TERPAKAI')
                            if status_str == 'TERPAKAI':
                                c3.markdown("🔴 **TERPAKAI**")
                            else:
                                c3.markdown("🟢 **BELUM TERPAKAI**")

                            if c4.button("🗑️ Hapus", key=f"del_kunci_{r_pc['kunci']}"):
                                supabase.table('kunci_perangkat').delete().eq('kunci', r_pc['kunci']).execute()
                                st.success(f"Kunci {r_pc['kunci']} berhasil dihapus!")
                                time.sleep(1)
                                st.rerun()
                    else:
                        st.info(f"Belum ada Kunci PC terdaftar untuk nama sekolah: **{nama_sekolah_dicari}**")
                except Exception as e: 
                    st.error(f"Gagal mengambil data dari Supabase: {e}")

    # ------------------------------------------
    # 5. MENU DATA PEGAWAI (TERKUNCI)
    # ------------------------------------------
    elif menu_superadmin == "👥 Data Pegawai":
        if not st.session_state['menu_unlocked']:
            tampilkan_form_kunci("Pegawai")
        else:
            st.markdown("### ➕ Tambah Pegawai Manual")
            with st.form("form_tambah_pegawai_manual"):
                manual_nip = st.text_input("NIP Pegawai:", placeholder="Contoh: 198001012005011001")
                manual_nama = st.text_input("Nama Pegawai:", placeholder="Contoh: Ahmad, S.Pd.")
                
                df_sch_opt = get_data_sekolah()
                opsi_sekolah_peg = df_sch_opt['school_name'].tolist() if not df_sch_opt.empty else []
                manual_sekolah = st.selectbox("Pilih Sekolah / Unit Kerja:", opsi_sekolah_peg if opsi_sekolah_peg else ["-"])
                
                submit_manual = st.form_submit_button("💾 Simpan Pegawai")
                if submit_manual:
                    if manual_nip.strip() and manual_nama.strip() and manual_sekolah != "-":
                        try:
                            supabase.table('pegawai').upsert({
                                'nip': manual_nip.strip(),
                                'name': manual_nama.strip(),
                                'school_name': manual_sekolah.strip(),
                                'photo_uploaded': False,
                                'is_cadar': False
                            }, on_conflict='nip').execute()
                            st.success(f"✅ Pegawai {manual_nama} berhasil ditambahkan!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal menambahkan pegawai: {e}")
                    else:
                        st.error("⚠️ NIP, Nama, dan Sekolah wajib diisi!")

            st.markdown("---")
            st.markdown("### 📥 Download Template & Upload Massal")
            
            df_template = pd.DataFrame([
                {"nip": "198001012005011001", "name": "Ahmad, S.Pd.", "school_name": "SMKN 6 WAJO"},
                {"nip": "198502022008022002", "name": "Siti, M.Pd.", "school_name": "SMKN 6 WAJO"}
            ])
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_template.to_excel(writer, index=False, sheet_name='Template_Pegawai')
            
            st.download_button(
                label="📥 Download Template Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name="Template_Data_Pegawai.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_template_excel"
            )

            file_upload = st.file_uploader("Upload File Excel/CSV Data Pegawai", type=['xlsx', 'xls', 'csv'])
            if file_upload and st.button("Proses Upload Massal"):
                try:
                    if file_upload.name.endswith('.csv'):
                        df_upload = pd.read_csv(file_upload, dtype=str)
                    else:
                        df_upload = pd.read_excel(file_upload, dtype=str)
                    
                    df_upload = df_upload.dropna(subset=['nip', 'name', 'school_name'], how='all')
                    
                    records = []
                    for _, r in df_upload.iterrows():
                        nip_v = str(r['nip']).strip() if pd.notna(r.get('nip')) else ""
                        name_v = str(r['name']).strip() if pd.notna(r.get('name')) else ""
                        sch_v = str(r['school_name']).strip() if pd.notna(r.get('school_name')) else ""
                        
                        if nip_v and name_v and sch_v and nip_v.lower() != 'nan':
                            records.append({
                                'nip': nip_v,
                                'name': name_v,
                                'school_name': sch_v,
                                'photo_uploaded': False,
                                'is_cadar': False
                            })
                    
                    if records:
                        supabase.table('pegawai').upsert(records, on_conflict='nip').execute()
                        st.success(f"✅ Berhasil mengunggah {len(records)} data pegawai!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.warning("⚠️ File tidak berisi data pegawai yang valid.")
                except Exception as e:
                    st.error(f"Gagal memproses upload: {e}")
                
            st.markdown("---")
            st.markdown("### 🗑️ Hapus Data Pegawai Spesifik")
            hapus_nip = st.text_input("Masukkan NIP Pegawai yang ingin dihapus:")
            if st.button("Hapus Pegawai", type="primary"):
                if hapus_nip:
                    supabase.table('pegawai').delete().eq('nip', hapus_nip.strip()).execute()
                    st.success(f"Pegawai dengan NIP {hapus_nip} berhasil dihapus!")
                    time.sleep(1)
                    st.rerun()
                    
            st.markdown("### ✏️ Edit Data Pegawai & Buka Kunci Foto")
            with st.form("form_cari_edit_pegawai"):
                cari_nip_edit = st.text_input("Masukkan NIP Pegawai yang ingin diedit:")
                btn_cari_edit = st.form_submit_button("🔍 Cari Pegawai untuk Diedit")
                
                if btn_cari_edit:
                    if cari_nip_edit.strip():
                        st.session_state.edit_nip_target = cari_nip_edit.strip()
                    else:
                        st.session_state.edit_nip_target = None
                        st.warning("Silakan masukkan NIP terlebih dahulu.")
            if st.session_state.get('edit_nip_target'):
                target_nip = st.session_state.edit_nip_target
                try:
                    res_edit = supabase.table('pegawai').select('nip, name, school_name, photo_uploaded, is_cadar').eq('nip', target_nip).execute()
                    df_edit = pd.DataFrame(res_edit.data) if res_edit.data else pd.DataFrame()
                except Exception as e:
                    df_edit = pd.DataFrame()
                    st.error(f"Gagal mengambil data: {e}")

                if df_edit.empty:
                    st.warning(f"⚠️ Pegawai dengan NIP {target_nip} tidak ditemukan.")
                else:
                    emp_edit = df_edit.iloc[0]
                    current_photo_uploaded = str(emp_edit.get('photo_uploaded', 'False')).lower() == 'true'

                    st.info(f"📌 Mengedit data untuk NIP: **{target_nip}** | Nama: **{emp_edit.get('name', '')}**")
                    
                    if current_photo_uploaded:
                        col_status_f, col_btn_f = st.columns([2, 1])
                        col_status_f.success("📷 Foto acuan sudah terunggah dalam sistem.")
                        
                        with col_btn_f:
                            if st.button("🖼️ LIHAT FOTO", key=f"btn_liat_foto_{target_nip}", width="stretch"):
                                st.session_state.show_photo_nip = target_nip
                            
                            if st.button("🔄 GANTI FOTO", key=f"btn_toggle_ganti_{target_nip}", width="stretch"):
                                st.session_state[f'show_ganti_{target_nip}'] = not st.session_state.get(f'show_ganti_{target_nip}', False)
                    else:
                        st.info("📷 Pegawai ini belum memiliki foto acuan.")
                        st.session_state[f'show_ganti_{target_nip}'] = True

                    if st.session_state.get('show_photo_nip') == target_nip:
                        try:
                            res_photo = supabase.table('pegawai').select('photo_base64').eq('nip', target_nip).execute()
                            if res_photo.data and res_photo.data[0].get('photo_base64'):
                                photo_url_or_base64 = res_photo.data[0]['photo_base64']
                                st.image(photo_url_or_base64, caption=f"Foto Acuan: {emp_edit.get('name', '')}", width=250)
                            else:
                                st.warning("Data foto tidak ditemukan.")
                        except Exception as e_foto:
                            st.error(f"Gagal menarik data foto: {e_foto}")

                    if st.session_state.get(f'show_ganti_{target_nip}'):
                        with st.expander("📸 Upload / Timpa Foto Acuan Langsung (Akses Superadmin)", expanded=True):
                            foto_file_super = st.file_uploader("Pilih Foto Acuan Baru (Maksimal 3MB, JPG/PNG):", type=['jpg', 'jpeg', 'png'], key=f"up_foto_super_{target_nip}")
                            
                            if foto_file_super:
                                if foto_file_super.size > 3145728:
                                    st.error("❌ Ukuran foto terlalu besar! Maksimal ukuran file adalah 3MB.")
                                else:
                                    if st.button("💾 Simpan & Timpa Foto Acuan", key=f"btn_save_super_foto_{target_nip}", type="primary", width="stretch"):
                                        file_bytes = kompres_foto(foto_file_super.getvalue(), quality=60, max_size=(600, 600))
                                        url_foto = upload_ke_supabase(file_bytes, f"foto_acuan/{target_nip}.jpg", "image/jpeg")
                                        if url_foto:
                                            url_foto = f"{url_foto}?t={int(time.time())}"
                                            supabase.table('pegawai').update({'photo_uploaded': True, 'photo_base64': url_foto}).eq('nip', target_nip).execute()
                                            st.success("✅ Foto acuan berhasil diperbarui dan dikunci secara langsung oleh Superadmin!")
                                            st.session_state[f'show_ganti_{target_nip}'] = False
                                            time.sleep(1)
                                            st.rerun()

                    with st.form("form_update_pegawai"):
                        edit_nama = st.text_input("Nama Pegawai:", value=emp_edit.get('name', ''))
                        
                        df_sch_opt_edit = get_data_sekolah()
                        opsi_sekolah_edit = df_sch_opt_edit['school_name'].tolist() if not df_sch_opt_edit.empty else []
                        current_school = emp_edit.get('school_name', '')
                        
                        try:
                            idx_school = opsi_sekolah_edit.index(current_school) if current_school in opsi_sekolah_edit else 0
                        except:
                            idx_school = 0
                            
                        edit_sekolah = st.selectbox("Sekolah / Unit Kerja:", opsi_sekolah_edit, index=idx_school)
                        
                        current_cadar = str(emp_edit.get('is_cadar', 'False')).lower() == 'true'
                        edit_cadar = st.checkbox("🧕 Tandai sebagai Pegawai Bercadar (Bypass Wajah / Mode Audit)", value=current_cadar)
                        
                        if current_photo_uploaded:
                            st.warning("🔒 Status Foto Pegawai saat ini: **TERKUNCI (Sudah Diunggah)**")
                            buka_kunci_foto = st.checkbox("🔓 Centang di sini untuk MEMBUKA KUNCI FOTO (Izinkan Admin Sekolah mengunggah ulang foto acuan)")
                        else:
                            st.info("🟢 Status Foto Pegawai saat ini: **BELUM TERKUNCI / BELUM ADA FOTO**")
                            buka_kunci_foto = False

                        btn_simpan_edit = st.form_submit_button("💾 Update Data Pegawai")
                        
                        if btn_simpan_edit:
                            try:
                                update_payload = {
                                    'name': edit_nama.strip(),
                                    'school_name': edit_sekolah.strip(),
                                    'is_cadar': edit_cadar
                                }
                                
                                if current_photo_uploaded and buka_kunci_foto:
                                    update_payload['photo_uploaded'] = False
                                    
                                supabase.table('pegawai').update(update_payload).eq('nip', target_nip).execute()
                                
                                st.success("✅ Data pegawai & status kunci berhasil diperbarui!")
                                st.session_state.edit_nip_target = None
                                st.session_state.show_photo_nip = None
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Gagal memperbarui data: {e}")

    # ------------------------------------------
    # 6. MENU AKUN ADMIN (TERKUNCI)
    # ------------------------------------------
    elif menu_superadmin == "🔑 Akun Admin":
        if not st.session_state['menu_unlocked']:
            tampilkan_form_kunci("Admin")
        else:
            st.markdown("### ➕ Tambah Admin Baru")
            with st.form("form_tambah_admin"):
                new_user = st.text_input("Username Baru")
                new_pass = st.text_input("Password", type="password")
                opsi_sekolah_admin = ["Semua Sekolah"] + get_data_sekolah()['school_name'].tolist()
                new_sekolah = st.selectbox("Akses Sekolah", opsi_sekolah_admin)
                
                if st.form_submit_button("Simpan Admin"):
                    if new_user and new_pass:
                        supabase.table('admins').insert({'username': new_user, 'password': new_pass, 'sekolah': new_sekolah}).execute()
                        st.cache_data.clear()
                        st.success("Admin berhasil ditambahkan!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Username dan Password wajib diisi!")
            
            st.markdown("---")
            st.markdown("### 📋 Kelola Admin (Hapus)")
            df_admins = get_data_admin()
            for idx, row in df_admins.iterrows():
                with st.expander(f"👤 {row['username']} - {row['sekolah']}"):
                    if st.button("🗑️ Hapus Admin", key=f"del_adm_{row['id']}"):
                        supabase.table('admins').delete().eq('id', row['id']).execute()
                        st.cache_data.clear()
                        st.rerun()

    # ------------------------------------------
    # 7. MENU IZIN & MANUAL
    # ------------------------------------------
    elif menu_superadmin == "📝 Izin & Manual":
        st.markdown("### 📝 Input Izin / Cuti / Sakit / Dinas Luar")
        st.caption("Cari NIP Pegawai, lengkapi formulir izin, dan upload surat PDF.")

        with st.form("form_cari_nip_izin"):
            nip_input_izin = st.text_input("Masukkan NIP Pegawai:", placeholder="Ketik NIP lalu tekan enter atau cari")
            btn_cari_izin = st.form_submit_button("🔍 Cari Pegawai")

        if btn_cari_izin:
            if nip_input_izin.strip():
                st.session_state['nip_izin_target'] = nip_input_izin.strip()
            else:
                st.session_state['nip_izin_target'] = None
                st.warning("Silakan masukkan NIP terlebih dahulu.")

        if st.session_state.get('nip_izin_target'):
            nip_target = st.session_state['nip_izin_target']
            
            try:
                res_pegawai_izin = supabase.table('pegawai').select('nip, name, school_name').eq('nip', nip_target).execute()
                df_pegawai_izin = pd.DataFrame(res_pegawai_izin.data) if res_pegawai_izin.data else pd.DataFrame()
            except Exception as e:
                df_pegawai_izin = pd.DataFrame()

            if df_pegawai_izin.empty:
                st.error("⚠️ Data ASN tidak ditemukan di dalam sistem.")
            else:
                peg_izin = df_pegawai_izin.iloc[0]
                st.success(f"👤 Data Ditemukan: **{peg_izin['name']}** ({peg_izin['school_name']})")
                
                with st.form("form_pengajuan_izin"):
                    jenis_izin = st.selectbox("Pilih Jenis Izin:", ["Cuti", "Sakit", "Dinas Luar", "Izin Lainnya"])
                    
                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        tgl_mulai_izin = st.date_input("Mulai Tanggal:")
                    with col_t2:
                        tgl_selesai_izin = st.date_input("Sampai Tanggal:")
                        
                    keterangan_izin = st.text_area("Kolom Isian / Keterangan Izin:")
                    surat_pdf = st.file_uploader("Upload Surat (Wajib PDF)", type=['pdf'])
                    
                    btn_kirim_izin = st.form_submit_button("KIRIM 🚀", type="primary")
                    
                    if btn_kirim_izin:
                        if tgl_mulai_izin > tgl_selesai_izin:
                            st.error("❌ Tanggal selesai tidak boleh mendahului tanggal mulai.")
                        elif not surat_pdf:
                            st.error("❌ Anda harus mengunggah Surat berformat PDF.")
                        else:
                            try:
                                surat_bytes = surat_pdf.getvalue()
                                timestamp_surat = int(time.time())
                                file_path = f"surat_izin/{nip_target}_{timestamp_surat}.pdf"
                                url_surat = upload_ke_supabase(surat_bytes, file_path, "application/pdf")
                                
                                delta_days = (tgl_selesai_izin - tgl_mulai_izin).days + 1
                                records_izin = []
                                
                                for i in range(delta_days):
                                    current_date = tgl_mulai_izin + datetime.timedelta(days=i)
                                    if current_date.weekday() < 5:
                                        records_izin.append({
                                            'nip': nip_target,
                                            'nama': peg_izin['name'],
                                            'sekolah': peg_izin['school_name'],
                                            'tanggal': current_date.strftime('%Y-%m-%d'),
                                            'jam': '-',
                                            'status': jenis_izin.upper(),
                                            'foto_bukti': url_surat 
                                        })
                                        
                                if records_izin:
                                    supabase.table('absensi').insert(records_izin).execute()
                                    st.success(f"✅ Pengajuan {jenis_izin} berhasil dikirim dan dicatat untuk {len(records_izin)} hari kerja!")
                                    st.session_state['nip_izin_target'] = None 
                                    time.sleep(1.5)
                                    st.rerun()
                                else:
                                    st.warning("⚠️ Rentang tanggal yang dipilih hanya mencakup akhir pekan.")
                            except Exception as e:
                                st.error(f"Gagal memproses pengajuan izin: {e}")

        st.markdown("---")

        st.markdown("### ✍️ Input Absen Manual (Masuk/Pulang)")
        st.caption("Input absen manual ke database. ASN yang diinput di sini tidak perlu absen lagi di sekolah.")

        with st.form("form_cari_nip_manual"):
            nip_input_manual = st.text_input("Masukkan NIP Pegawai (Untuk Absen Manual):", placeholder="Ketik NIP lalu cari", key="nip_manual_search")
            btn_cari_manual = st.form_submit_button("🔍 Cari Data Pegawai")

        if btn_cari_manual:
            if nip_input_manual.strip():
                st.session_state['nip_manual_target'] = nip_input_manual.strip()
            else:
                st.session_state['nip_manual_target'] = None
                st.warning("Silakan masukkan NIP terlebih dahulu.")

        if st.session_state.get('nip_manual_target'):
            nip_target_manual = st.session_state['nip_manual_target']
            
            try:
                res_peg_man = supabase.table('pegawai').select('nip, name, school_name').eq('nip', nip_target_manual).execute()
                df_peg_man = pd.DataFrame(res_peg_man.data) if res_peg_man.data else pd.DataFrame()
            except Exception as e:
                df_peg_man = pd.DataFrame()

            if df_peg_man.empty:
                st.error("⚠️ Data ASN tidak ditemukan di dalam sistem.")
            else:
                peg_man = df_peg_man.iloc[0]
                st.success(f"👤 Data Ditemukan: **{peg_man['name']}** ({peg_man['school_name']})")
                
                with st.form("form_eksekusi_absen_manual"):
                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        tgl_manual = st.date_input("Tanggal Absen:")
                    with col_m2:
                        jam_manual = st.time_input("Jam Absen:")
                        
                    status_manual = st.selectbox("Pilih Status Absensi:", ["DATANG", "PULANG"])
                    
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        btn_batal_manual = st.form_submit_button("❌ Batal")
                    with col_b2:
                        btn_ok_manual = st.form_submit_button("✅ OK (Simpan Absen)", type="primary")
                        
                    if btn_batal_manual:
                        st.session_state['nip_manual_target'] = None
                        st.rerun()
                        
                    if btn_ok_manual:
                        try:
                            supabase.table('absensi').insert([{
                                'nip': nip_target_manual,
                                'nama': peg_man['name'],
                                'sekolah': peg_man['school_name'],
                                'tanggal': tgl_manual.strftime('%Y-%m-%d'),
                                'jam': jam_manual.strftime('%H:%M'),
                                'status': status_manual,
                                'jarak_m': 'Manual by Admin', 
                                'foto_bukti': None
                            }]).execute()
                            
                            st.success(f"✅ Absensi {status_manual} manual untuk {peg_man['name']} berhasil disimpan!")
                            st.session_state['nip_manual_target'] = None
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Gagal menyimpan absen manual: {e}")

    # ------------------------------------------
    # 8. MENU DATABASE
    # ------------------------------------------
    elif menu_superadmin == "🚨 Database":
        st.markdown("### 🚨 Kelola & Backup Database")

        st.markdown("#### 📥 Backup Data Absensi")
        st.caption("Tarik seluruh raw data absensi berdasarkan rentang waktu untuk diunduh sebagai file CSV sebelum Anda menghapusnya.")
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            tgl_mulai_backup = st.date_input("Dari Tanggal (Backup):", datetime.date.today() - datetime.timedelta(days=30))
        with col_b2:
            tgl_selesai_backup = st.date_input("Sampai Tanggal (Backup):", datetime.date.today())

        if st.button("🔄 Tarik Data Backup", type="secondary"):
            if tgl_mulai_backup > tgl_selesai_backup:
                st.error("Tanggal selesai tidak boleh lebih awal dari tanggal mulai.")
            else:
                try:
                    res_backup = supabase.table('absensi').select('*') \
                        .gte('tanggal', tgl_mulai_backup.strftime('%Y-%m-%d')) \
                        .lte('tanggal', tgl_selesai_backup.strftime('%Y-%m-%d')) \
                        .execute()
                        
                    df_backup = pd.DataFrame(res_backup.data) if res_backup.data else pd.DataFrame()

                    if not df_backup.empty:
                        buffer_backup = io.BytesIO()
                        df_backup.to_csv(buffer_backup, index=False)
                        st.success(f"✅ Ditemukan {len(df_backup)} baris data. Silakan unduh file backup di bawah ini.")
                        
                        st.download_button(
                            label="💾 Download File Backup (.csv)",
                            data=buffer_backup.getvalue(),
                            file_name=f"Backup_Database_{tgl_mulai_backup.strftime('%d%m%Y')}-{tgl_selesai_backup.strftime('%d%m%Y')}.csv",
                            mime="text/csv",
                            key="dl_backup_csv"
                        )
                    else:
                        st.warning("⚠️ Tidak ada data absensi pada rentang tanggal tersebut.")
                except Exception as e:
                    st.error(f"Gagal menarik data backup: {e}")

        st.markdown("---")

        st.markdown("#### 🗑 Hapus Data Absensi (Mingguan/Bulanan)")
        st.caption("Pilih rentang waktu absensi yang ingin dibersihkan secara permanen dari Supabase.")
        
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            tgl_mulai_hapus = st.date_input("Hapus Dari Tanggal:", datetime.date.today() - datetime.timedelta(days=30), key="tm_hapus")
        with col_h2:
            tgl_selesai_hapus = st.date_input("Hapus Sampai Tanggal:", datetime.date.today(), key="ts_hapus")

        konfirmasi_hapus = st.text_input("Ketik 'HAPUS' (huruf kapital) untuk mengonfirmasi penghapusan permanen:")

        if st.button("⚠️ Hapus Permanen Rentang Waktu Ini", type="primary"):
            if tgl_mulai_hapus > tgl_selesai_hapus:
                st.error("Tanggal batas akhir tidak boleh lebih awal dari tanggal mulai.")
            elif konfirmasi_hapus != "HAPUS":
                st.error("❌ Anda harus mengetik 'HAPUS' pada kolom konfirmasi untuk melanjutkan proses ini.")
            else:
                try:
                    supabase.table('absensi').delete() \
                        .gte('tanggal', tgl_mulai_hapus.strftime('%Y-%m-%d')) \
                        .lte('tanggal', tgl_selesai_hapus.strftime('%Y-%m-%d')) \
                        .execute()
                        
                    st.success(f"✅ Data absensi dari tanggal {tgl_mulai_hapus.strftime('%d-%m-%Y')} hingga {tgl_selesai_hapus.strftime('%d-%m-%Y')} telah dihapus permanen!")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menghapus data: {e}")

    # ------------------------------------------
    # 9. MENU JAM & GPS (TERKUNCI)
    # ------------------------------------------
    elif menu_superadmin == "⚙️ Jam & GPS":
        if not st.session_state['menu_unlocked']:
            tampilkan_form_kunci("Jam & GPS")
        else:
            st.markdown("### ⚙ Pengaturan Waktu & GPS")
            df_settings = get_data_pengaturan()
            b_in = df_settings['batas_masuk'].iloc[0] if not df_settings.empty else '07:30'
            b_out = df_settings['batas_pulang'].iloc[0] if not df_settings.empty else '16:00'
            
            if 'gps_aktif' in df_settings.columns and not pd.isna(df_settings['gps_aktif'].iloc[0]):
                gps_state = bool(df_settings['gps_aktif'].iloc[0])
            else:
                gps_state = True

            n_in = st.time_input("Batas Masuk", datetime.datetime.strptime(b_in, '%H:%M').time())
            n_out = st.time_input("Batas Pulang", datetime.datetime.strptime(b_out, '%H:%M').time())
            
            st.markdown("---")
            st.markdown("#### 📍 Pengaturan Fitur Jarak GPS")
            n_gps = st.checkbox("✅ Aktifkan Validasi Jarak/Radius GPS", value=gps_state, help="Hapus centang (OFF) jika ingin mengabaikan masalah PC yang titik GPS-nya sering meleset. Kunci PC & Wajah akan tetap wajib/jalan.")

            if st.button("💾 Simpan Pengaturan", type="primary"):
                try:
                    supabase.table('pengaturan').update({
                        'batas_masuk': n_in.strftime('%H:%M'), 
                        'batas_pulang': n_out.strftime('%H:%M'),
                        'gps_aktif': n_gps
                    }).neq('batas_masuk', '').execute()
                    st.cache_data.clear()
                    st.success("✅ Pengaturan Jam & GPS berhasil diperbarui!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menyimpan pengaturan: {e}")
