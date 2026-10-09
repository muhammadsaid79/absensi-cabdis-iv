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
import streamlit.components.v1 as components
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

# Sanitasi URL untuk mencegah double-slash '//' yang memicu error PostgREST PGRST125
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
    if st.button("Oke, Saya Mengerti", key="btn_close_dialog_csv", use_container_width=True):
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
st.set_page_config(page_title="Sistem Absensi Sekolah Cabdis Wil IV", page_icon="🏫", layout="centered")
cookie_manager = stx.CookieManager(key="cookie_manager_utama")

# --- 3. CUSTOM CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Poppins', sans-serif !important; }
    header {visibility: hidden !important; height: 0px !important;} 
    [data-testid="stToolbar"], [data-testid="stDecoration"], footer, #MainMenu {visibility: hidden !important;}
    [data-testid="stHeaderActionElements"], .header-anchor { display: none !important; }
    .block-container { padding-top: 2rem !important; }
    .stForm, div[data-testid="stExpander"] {
        background-color: #FFFFFF; padding: 24px; border-radius: 12px;
        box-shadow: 0px 4px 15px rgba(0, 0, 0, 0.05); border: 1px solid #E2E8F0;
    }
    div.stButton > button {
        background-color: #2563EB !important; color: white !important; font-weight: 600 !important;
        border-radius: 8px !important; border: none !important; transition: 0.3s;
    }
    div.stButton > button:hover { background-color: #1D4ED8 !important; box-shadow: 0 4px 10px rgba(37, 99, 235, 0.3); }
    [data-testid="stSidebar"] { background-color: #F8FAFC !important; border-right: 1px solid #E2E8F0; }
    </style>
""", unsafe_allow_html=True)

# --- 4. FUNGSI INTERAKSI DATABASE (OPTIMASI CACHING UNTUK MENGHEMAT EGRESS) ---
@st.cache_data(ttl=600)
def get_data_sekolah():
    try:
        res = supabase.table('sekolah').select('school_name, lat, lng, radius_m').execute()
        if res.data: return pd.DataFrame(res.data)
    except: pass
    return pd.DataFrame(columns=['school_name', 'lat', 'lng', 'radius_m'])

@st.cache_data(ttl=600)
def get_data_admin():
    try:
        res = supabase.table('admins').select('id, username, password, sekolah').execute()
        if res.data: return pd.DataFrame(res.data)
    except: pass
    return pd.DataFrame(columns=['id', 'username', 'password', 'sekolah'])

@st.cache_data(ttl=600)
def get_data_pengaturan():
    try:
        res = supabase.table('pengaturan').select('batas_masuk, batas_pulang').execute()
        if res.data:
            return pd.DataFrame(res.data)
        else:
            default_data = {'batas_masuk': '07:30', 'batas_pulang': '16:00'}
            supabase.table('pengaturan').insert(default_data).execute()
            return pd.DataFrame([default_data])
    except:
        return pd.DataFrame([{'batas_masuk': '07:30', 'batas_pulang': '16:00'}])

# Helper Rekap Absensi
def proses_rekap_absensi(nama_sekolah, tgl_mulai, tgl_selesai):
    start_d = tgl_mulai.strftime('%Y-%m-%d')
    end_d = tgl_selesai.strftime('%Y-%m-%d')
    
    # 1. Hitung hari kerja (Senin-Jumat)
    rentang_tanggal = pd.date_range(start=start_d, end=end_d)
    total_hari_kerja = len(rentang_tanggal[rentang_tanggal.dayofweek < 5])

    # 2. Ambil data identitas pegawai (Tetap)
    res_pegawai = supabase.table('pegawai').select('nip, name, school_name').ilike('school_name', f"%{nama_sekolah.strip()}%").execute()
    df_pegawai = pd.DataFrame(res_pegawai.data) if res_pegawai.data else pd.DataFrame()

    if df_pegawai.empty:
        return None, total_hari_kerja

    # 3. PANGGIL FUNGSI MESIN HITUNG DARI SUPABASE (Sangat Ringan!)
    res_rekap = supabase.rpc('rekap_absensi_sekolah', {
        'p_sekolah': nama_sekolah.strip(),
        'p_tgl_mulai': start_d,
        'p_tgl_selesai': end_d
    }).execute()
    
    df_absen = pd.DataFrame(res_rekap.data) if res_rekap.data else pd.DataFrame()

    # 4. Gabungkan Data Pegawai dan Hasil Rekap dari Server
    rekap_data = []
    for _, emp in df_pegawai.iterrows():
        emp_nip, emp_name = emp['nip'], emp['name']

        if not df_absen.empty and emp_nip in df_absen['nip'].values:
            # Ambil hasil rekap untuk NIP ini
            row_rekap = df_absen[df_absen['nip'] == emp_nip].iloc[0]
            t_masuk = int(row_rekap['total_masuk'])
            t_pulang = int(row_rekap['total_pulang'])
            t_terlambat = int(row_rekap['total_terlambat'])
            t_izin = int(row_rekap['total_izin'])
            hari_ada_catatan = int(row_rekap['hari_hadir'])
        else:
            # Jika tidak ada sama sekali di tabel rekap
            t_masuk, t_pulang, t_terlambat, t_izin, hari_ada_catatan = 0, 0, 0, 0, 0

        # Hitung Alpha (Tanpa Keterangan)
        alpha = max(0, total_hari_kerja - hari_ada_catatan)

        rekap_data.append({
            'NIP': emp_nip, 
            'Nama Pegawai': emp_name,
            'Total Absen Masuk': t_masuk, 
            'Total Absen Pulang': t_pulang,
            'Total Terlambat': t_terlambat, 
            'Total Izin/Manual': t_izin,
            'Tanpa Keterangan (Alpha)': alpha
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
            if st.button("Masuk Admin", use_container_width=True, key="btn_admin_main"):
                df_adm = get_data_admin()
                is_valid = False
                assigned_school = "Semua Sekolah"
                if not df_adm.empty and 'username' in df_adm.columns:
                    # Menambahkan .strip() untuk mencegah error karena spasi
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
            if st.button("Masuk Superadmin", use_container_width=True, key="btn_super_main"):
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
st.sidebar.button("🚪 Keluar (Logout)", on_click=logout, key="btn_logout_sidebar")
st.sidebar.write("---")
waktu_sekarang = datetime.datetime.now(pytz.timezone('Asia/Makassar'))
st.sidebar.markdown("**Waktu Server (WITA):**")
st.sidebar.info(f"🕒 {waktu_sekarang.strftime('%H:%M:%S')} WITA\n\n📅 {waktu_sekarang.strftime('%d-%m-%Y')}")
st.sidebar.write("---")

# ==========================================
# HAK AKSES 1: ADMIN SEKOLAH
# ==========================================
if st.session_state.role == "Admin":
    col_judul, col_tombol = st.columns([3, 1])
    col_judul.title("🔐 Dashboard Admin Sekolah")
    col_tombol.button("🚪 Logout", on_click=logout, use_container_width=True, key="btn_logout_top_admin")
    admin_akses = st.session_state.get('admin_sekolah', 'Semua Sekolah')

    tab_foto, tab_dashboard = st.tabs([
        "📸 1. Upload Foto Pegawai", 
        "📊 2. Dashboard Cek Absensi"
    ])

    # ------------------------------------------
    # MENU 1: UPLOAD FOTO PEGAWAI (TERKUNCI SETELAH UPLOAD)
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
                components.html(html_swal_nip, height=0)
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
                            # Cek ukuran file dalam byte (3MB = 3 * 1024 * 1024 = 3145728 bytes)
                            if foto_file.size > 3145728:
                                st.error("❌ Ukuran foto terlalu besar! Maksimal ukuran file adalah 3MB. Silakan kompres/perkecil foto Anda terlebih dahulu.")
                            else:
                                if st.button("💾 Simpan Foto Acuan", key=f"btn_save_foto_{nip_peg}", use_container_width=True):
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
                
            btn_cek_dash = st.button("🔍 Cek Status Absensi", type="primary", use_container_width=True, key="btn_cek_absensi_dash")
            
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
                                    c_foto.image(foto_url, caption="Foto Bukti Absen", use_container_width=True)

# ==========================================
# HAK AKSES 2: SUPERADMIN
# ==========================================
elif st.session_state.role == "Superadmin":
    col_judul, col_tombol = st.columns([3, 1])
    col_judul.title("🛠️ Dashboard Superadmin")
    col_tombol.button("🚪 Logout", on_click=logout, use_container_width=True, key="btn_logout_superadmin")

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

    tab_sekolah, tab_pc, tab_pegawai, tab_admin, tab_izin, tab_database, tab_jam, tab_rekap, tab_indisipliner = st.tabs([
        "🏛️ Sekolah", "💻 PC", "👥 Pegawai", "🔑 Admin", "📝 Izin", "🚨 Database", "⚙️ Jam", "📈 REKAP ABSENSI", "🟥 LAPORAN INDISIPLINER PEGAWAI"
    ])

    # ------------------------------------------
    # 1. TAB REKAP ABSENSI (BEBAS AKSES)
    # ------------------------------------------
    with tab_rekap:
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
                        st.dataframe(df_final, use_container_width=True)

                        # --- Ubah Download ke Excel ---
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
    # 2. TAB LAPORAN INDISIPLINER (BEBAS AKSES)
    # ------------------------------------------
    with tab_indisipliner:
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
                        df_indisipliner = df_res[df_res['Tanpa Keterangan (Alpha)'] >= 1]

                        if df_indisipliner.empty:
                            st.success("🎉 **SANGAT BAIK:** Tidak ditemukan pegawai indisipliner pada periode ini.")
                        else:
                            st.error(f"⚠️ Ditemukan **{len(df_indisipliner)} Pegawai** dengan catatan Tanpa Keterangan (Alpha) ≥ 1 hari!")
                            st.dataframe(df_indisipliner, use_container_width=True)
                            
                            # --- Ubah Download ke Excel ---
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
    # 3. TAB SEKOLAH (TERKUNCI)
    # ------------------------------------------
    with tab_sekolah:
        if not st.session_state['menu_unlocked']:
            tampilkan_form_kunci("Sekolah")
        else:
            st.markdown("### Sekolah Aktif")
            df_sekolah_curr = get_data_sekolah()
            edited_schools = st.data_editor(df_sekolah_curr, num_rows="dynamic", use_container_width=True)
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
    # 4. TAB PC (TERKUNCI) - GENERATE 3 KUNCI PC
    # ------------------------------------------
    with tab_pc:
        if not st.session_state['menu_unlocked']:
            tampilkan_form_kunci("PC")
        else:
            st.markdown("### 🔑 Kelola & Generate Kunci Perangkat PC")
            st.caption("Ketik nama sekolah untuk membuat 3 kunci PC baru atau mencari kunci yang sudah ada.")
            
            with st.form("form_pc_superadmin"):
                sekolah_input_pc = st.text_input("Masukkan Nama Sekolah:", placeholder="Contoh: SMKN 6 WAJO", key="input_sekolah_pc_super")
                col_b1, col_b2 = st.columns(2)
                btn_cari_pc = col_b1.form_submit_button("🔍 Cari PC Sekolah", use_container_width=True)
                btn_generate_pc = col_b2.form_submit_button("🔑 Generate 3 Kunci PC", type="primary", use_container_width=True)
                
            if btn_generate_pc:
                nama_sekolah_clean = sekolah_input_pc.strip()
                if not nama_sekolah_clean:
                    st.warning("⚠️ Silahkan masukkan Nama Sekolah terlebih dahulu!")
                else:
                    prefix = "".join(e for e in nama_sekolah_clean if e.isalnum()).upper()
                    kunci_1 = f"{prefix}-PC1"
                    kunci_2 = f"{prefix}-PC2"
                    kunci_3 = f"{prefix}-PC3"

                    records = [
                        {"kunci": kunci_1, "sekolah": nama_sekolah_clean, "status": "BELUM_TERPAKAI"},
                        {"kunci": kunci_2, "sekolah": nama_sekolah_clean, "status": "BELUM_TERPAKAI"},
                        {"kunci": kunci_3, "sekolah": nama_sekolah_clean, "status": "BELUM_TERPAKAI"}
                    ]

                    try:
                        supabase.table('kunci_perangkat').upsert(records, on_conflict='kunci').execute()
                        st.success(f"✅ Berhasil membuat 3 Kunci PC untuk **{nama_sekolah_clean}**!")
                        st.session_state.last_searched_school_pc = nama_sekolah_clean
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Gagal membuat kunci: {e}")

            if btn_cari_pc:
                if sekolah_input_pc.strip():
                    st.session_state.last_searched_school_pc = sekolah_input_pc.strip()
                else:
                    st.session_state.last_searched_school_pc = None
                    st.warning("Silahkan ketik nama sekolah terlebih dahulu.")
                    
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
    # 5. TAB PEGAWAI (TERKUNCI) + BUKA KUNCI FOTO & TOMBOL LIAT FOTO
    # ------------------------------------------
    with tab_pegawai:
        if not st.session_state['menu_unlocked']:
            tampilkan_form_kunci("Pegawai")
        else:
            # --- FEATURE 1: TAMBAH PEGAWAI MANUAL ---
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

            # --- FEATURE 2: DOWNLOAD TEMPLATE & UPLOAD MASSAL ---
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

            # --- FEATURE 3: HAPUS PEGAWAI SPESIFIK ---
            st.markdown("### 🗑️ Hapus Data Pegawai Spesifik")
            hapus_nip = st.text_input("Masukkan NIP Pegawai yang ingin dihapus:")
            if st.button("Hapus Pegawai", type="primary"):
                if hapus_nip:
                    supabase.table('pegawai').delete().eq('nip', hapus_nip.strip()).execute()
                    st.success(f"Pegawai dengan NIP {hapus_nip} berhasil dihapus!")
                    time.sleep(1)
                    st.rerun()
                    
            # --- FEATURE 4: EDIT DATA PEGAWAI, BUKA KUNCI FOTO & TOMBOL LIAT FOTO ---
            st.markdown("### ✏️ Edit Data Pegawai & Buka Kunci Foto")
            st.caption("Cari berdasarkan NIP. Data foto hanya akan ditarik dari server jika Anda menekan tombol '🖼️ LIHAT FOTO'.")

            with st.form("form_cari_edit_pegawai"):
                edit_nip_cari = st.text_input("Masukkan NIP Pegawai yang ingin diedit/dibuka kuncinya:", placeholder="Contoh: 198001012005011001", key="nip_edit_cari")
                btn_cari_edit = st.form_submit_button("🔍 Cari Pegawai")

            if btn_cari_edit:
                if edit_nip_cari.strip():
                    st.session_state.edit_nip_target = edit_nip_cari.strip()
                    st.session_state.show_photo_nip = None # Reset tampilan foto saat cari NIP baru
                else:
                    st.session_state.edit_nip_target = None
                    st.warning("Silahkan masukkan NIP terlebih dahulu.")

            # HANYA TARIK DATA TEKS (TANPA photo_base64) DARI SUPABASE
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
                    
                    # TOMBOL LIAT FOTO (Hanya muncul jika foto sudah diunggah)
                    if current_photo_uploaded:
                        col_status_f, col_btn_f = st.columns([2, 1])
                        col_status_f.success("📷 Foto acuan sudah terunggah dalam sistem.")
                        if col_btn_f.button("🖼️ LIHAT FOTO", key=f"btn_liat_foto_{target_nip}"):
                            st.session_state.show_photo_nip = target_nip
                    else:
                        st.info("📷 Pegawai ini belum memiliki foto acuan.")

                    # SISTEM MENARIK FOTO HANYA JIKA TOMBOL 'LIHAT FOTO' DITEKAN
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

                    # FORM UPDATE DATA PEGAWAI
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
                        
                        # --- MODUL BUKA KUNCI FOTO OLEH SUPERADMIN ---
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
                                
                                # Jika Superadmin mencentang buka kunci foto
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
    # 6. TAB ADMIN (TERKUNCI)
    # ------------------------------------------
    with tab_admin:
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
                        st.cache_data.clear() # Tambahkan clear cache
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
                        st.cache_data.clear() # Tambahkan clear cache
                        st.rerun()

    # ------------------------------------------
    # 7. TAB IZIN
    # ------------------------------------------
    with tab_izin:
            st.markdown("### Input Izin / Surat (Bypass)")
            nip_input_izin = st.text_input("NIP Pegawai:")
            if st.button("Input Surat Kosong/Izin") and nip_input_izin:
                supabase.table('absensi').insert({'nip': nip_input_izin.strip(), 'nama': 'Manual', 'sekolah': 'Manual', 'tanggal': datetime.datetime.now().strftime('%Y-%m-%d'), 'jam': '-', 'status': 'Izin'}).execute()
                st.success("Izin dicatat!")

    # ------------------------------------------
    # 8. TAB DATABASE
    # ------------------------------------------
    with tab_database:
            st.markdown("### 🚨 Database Clean Up")
            if st.button("🖼 Hapus Semua Foto (Teks Aman)", type="primary"):
                supabase.table('absensi').update({'foto_bukti': ''}).neq('foto_bukti', '').execute()
                st.success("Foto fisik berhasil diputus dari database.")
                
            st.markdown("---")
            st.markdown("### 🗑 Hapus Data Absensi Harian")
            tgl_hapus = st.date_input("Pilih Tanggal Absensi yang akan dihapus:")
            if st.button(f"Hapus Absensi Tanggal {tgl_hapus.strftime('%d-%m-%Y')}"):
                supabase.table('absensi').delete().eq('tanggal', tgl_hapus.strftime('%Y-%m-%d')).execute()
                st.success(f"Seluruh data absensi pada tanggal {tgl_hapus.strftime('%d-%m-%Y')} berhasil dihapus permanen!")
                time.sleep(1)
                st.rerun()

    # ------------------------------------------
    # 9. TAB JAM (TERKUNCI)
    # ------------------------------------------
    with tab_jam:
        if not st.session_state['menu_unlocked']:
            tampilkan_form_kunci("Jam")
        else:
            st.markdown("### ⚙ Jam Kerja")
            df_settings = get_data_pengaturan()
            b_in = df_settings['batas_masuk'].iloc[0] if not df_settings.empty else '07:30'
            b_out = df_settings['batas_pulang'].iloc[0] if not df_settings.empty else '16:00'
            n_in = st.time_input("Batas Masuk", datetime.datetime.strptime(b_in, '%H:%M').time())
            n_out = st.time_input("Batas Pulang", datetime.datetime.strptime(b_out, '%H:%M').time())
            if st.button("Simpan Pengaturan"):
                supabase.table('pengaturan').update({'batas_masuk': n_in.strftime('%H:%M'), 'batas_pulang': n_out.strftime('%H:%M')}).neq('batas_masuk', '').execute()
                st.cache_data.clear()
                st.success("✅ Pengaturan jam berhasil diperbarui!")
                time.sleep(1)
                st.rerun()
