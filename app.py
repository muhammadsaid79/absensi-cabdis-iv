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
import base64
import pytz

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import extra_streamlit_components as stx
import geopy.distance
from PIL import Image
from streamlit_js_eval import get_geolocation
from dotenv import load_dotenv
from supabase import create_client, Client

# ==========================================
# FUNGSI UTILITAS AWAL (Sangat Ringan)
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
    except Exception as e:
        return image_bytes 

# --- 1. MEMUAT ENVIRONMENT VARIABLES & SUPABASE ---
load_dotenv()

url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")

try:
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error(f"Gagal terhubung ke Supabase: {e}")
    st.stop()

def upload_ke_supabase(file_bytes, file_path, content_type):
    bucket_name = "absensi-files"
    try:
        supabase.storage.from_(bucket_name).upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        return supabase.storage.from_(bucket_name).get_public_url(file_path)
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

# --- 4. FUNGSI INTERAKSI DATABASE (OPTIMASI EGRESS) ---
def get_data_sekolah():
    try:
        res = supabase.table('sekolah').select('school_name, lat, lng, radius_m').execute()
        if res.data: return pd.DataFrame(res.data)
    except: pass
    return pd.DataFrame(columns=['school_name', 'lat', 'lng', 'radius_m'])

def get_data_pegawai():
    try:
        res = supabase.table('pegawai').select('nip, name, school_name, photo_uploaded, is_cadar').execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['nip'] = df['nip'].astype(str)
            return df
    except: pass
    return pd.DataFrame(columns=['nip', 'name', 'school_name', 'photo_uploaded', 'is_cadar'])

def get_data_admin():
    try:
        res = supabase.table('admins').select('id, username, password, sekolah').execute()
        if res.data: return pd.DataFrame(res.data)
    except: pass
    return pd.DataFrame(columns=['id', 'username', 'password', 'sekolah'])

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

# --- 5. INISIALISASI SESSION STATE ---
for key_state, val in {'role': None, 'admin_sekolah': "Semua Sekolah", 'logout_triggered': False, 'wajah_terverifikasi': False, 'pending_pc_name': None, 'last_searched_nip_foto': None, 'last_checked_nip_dash': None}.items():
    if key_state not in st.session_state: st.session_state[key_state] = val

if 'schools' not in st.session_state: st.session_state.schools = get_data_sekolah()
if 'employees' not in st.session_state: st.session_state.employees = get_data_pegawai()
if 'settings' not in st.session_state: st.session_state.settings = get_data_pengaturan()

raw_token = cookie_manager.get("auth_token")
saved_admin_school = cookie_manager.get("admin_sekolah")
if saved_admin_school: st.session_state.admin_sekolah = saved_admin_school

valid_role = verify_and_get_role(raw_token)

if st.session_state.role is not None:
    st.session_state.logout_triggered = False
elif st.session_state.logout_triggered:
    if raw_token is None: st.session_state.logout_triggered = False 
else:
    if valid_role: st.session_state.role = valid_role
    elif raw_token and not valid_role:
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
    try:
        cookie_manager.delete("auth_token", key="delete_auth_token_btn")
        cookie_manager.delete("role", key="delete_role_btn") 
        cookie_manager.delete("admin_sekolah", key="delete_admin_sekolah_btn") 
    except: pass

# ==========================================
# HALAMAN LOGIN UTAMA
# ==========================================
if st.session_state.role is None:
    st.title("📍 Portal Presensi Sekolah CABDIS WIL IV")
    st.info("Selamat datang! Untuk merekam kehadiran Anda, silakan klik tombol di bawah ini.")

    if st.button("📸 Mulai Presensi Wajah & GPS", type="primary", use_container_width=True, key="btn_login_pegawai_main"):
        st.session_state.role = "Pegawai"
        st.session_state.wajah_terverifikasi = False
        cookie_manager.set("auth_token", generate_signed_token("Pegawai"), key="set_token_login_pegawai")
        time.sleep(0.5)
        st.rerun()

    st.write("---")
    st.caption("Akses khusus Pengelola Sistem:")
    col_admin, col_super = st.columns(2)

    with col_admin:
        with st.expander("🔑 Login Admin"):
            input_user_admin = st.text_input("Username Admin:", key="user_admin_main")
            pwd = st.text_input("Password Admin:", type="password", key="pwd_admin_main")
            if st.button("Masuk Admin", use_container_width=True, key="btn_admin_main"):
                df_adm = get_data_admin()
                is_valid = False
                assigned_school = "Semua Sekolah"
                if not df_adm.empty and 'username' in df_adm.columns:
                    match = df_adm[(df_adm['username'] == input_user_admin) & (df_adm['password'] == pwd)]
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
        with st.expander("🛠️ Login Superadmin"):
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
st.sidebar.caption("JAM INI YANG AKAN TEREKAM DI ABSENSI BAPK/IBU.")
st.sidebar.write("---")

# ==========================================
# HAK AKSES 1: PEGAWAI
# ==========================================
if st.session_state.role == "Pegawai":
    st.button("⬅️ Kembali ke Halaman Awal", on_click=logout, key="btn_back_pegawai")
    st.title("📍 Presensi GPS & Wajah")
    nip_input = st.text_input("SILAHKAN KETIK NIP:", placeholder="Contoh: 198001012005011001", key="nip_input_pegawai")
    
    if nip_input.strip():
        try:
            res_pegawai = supabase.table('pegawai').select('nip, name, school_name, photo_uploaded, photo_base64, is_cadar').eq('nip', str(nip_input.strip())).execute()
            df_kandidat = pd.DataFrame(res_pegawai.data) if res_pegawai.data else pd.DataFrame()
        except: df_kandidat = pd.DataFrame()
            
        if df_kandidat.empty:
            st.warning("⚠️ Data pegawai tidak ditemukan.")
        else:
            emp_data = df_kandidat.iloc[0]
            try: sch_data = st.session_state.schools[st.session_state.schools['school_name'] == emp_data['school_name']].iloc[0]
            except:
                st.error("Data sekolah untuk pegawai ini tidak ditemukan.")
                st.stop()
                
            curr_dev_cookie = cookie_manager.get("school_device_token")
            try:
                res_dev_count = supabase.table('perangkat_sekolah').select('id').eq('school_name', sch_data['school_name']).execute()
                total_terdaftar = len(res_dev_count.data) if res_dev_count.data else 0
            except: total_terdaftar = 0

            is_valid_pc = False
            if total_terdaftar > 0:
                try:
                    res_valid = supabase.table('perangkat_sekolah').select('id').eq('school_name', sch_data['school_name']).eq('device_id', str(curr_dev_cookie)).execute()
                    if res_valid.data: is_valid_pc = True
                except: pass
                
                if not is_valid_pc:
                    st.error("⛔ AKSES DITOLAK! Perangkat ini belum terdaftar sebagai PC Resmi Sekolah.")
                    st.stop()
                else: st.success("🖥️ Perangkat Terverifikasi: PC Resmi Sekolah.")
            else:
                st.warning("⚠️ Sekolah ini belum mendaftarkan PC Resmi. Presensi di perangkat apapun masih terbuka.")
                
            st.info(f"👤 Nama: **{emp_data['name']}**\n\n🏫 Anda ditugaskan di: **{sch_data['school_name']}**")
            loc = get_geolocation()
            
            if loc:
                user_lat, user_lng = loc['coords']['latitude'], loc['coords']['longitude']
                jarak_meter = geopy.distance.geodesic((user_lat, user_lng), (sch_data['lat'], sch_data['lng'])).meters
                
                if jarak_meter <= sch_data['radius_m']:
                    st.success(f"✅ Lokasi Valid! Jarak: {jarak_meter:.0f} meter dari pusat.")
                    
                    is_uploaded = str(emp_data.get('photo_uploaded', 'False')).lower() == 'true'
                    is_cadar = str(emp_data.get('is_cadar', 'False')).lower() == 'true'
                    
                    if not is_cadar and not (is_uploaded and pd.notna(emp_data.get('photo_base64'))):
                        st.warning("⚠️ Admin belum mengunggah foto acuan wajah Anda.")
                    else:
                        img_camera = st.camera_input("Ambil Foto di Lokasi", key="cam_pegawai_input")
                        
                        if is_cadar:
                            st.session_state.wajah_terverifikasi = True
                            st.info("🧕 Verifikasi biometrik dilewati (Mode Audit).")

                        if img_camera:
                            bytes_data = kompres_foto(img_camera.getvalue())
                            cam_base64 = f"data:image/jpeg;base64,{base64.b64encode(bytes_data).decode('utf-8')}"
                            tgl_sekarang_str = datetime.datetime.now(pytz.timezone('Asia/Makassar')).strftime('%Y%m%d_%H%M%S')
                            url_foto_harian = upload_ke_supabase(bytes_data, f"foto_presensi/{emp_data['nip']}_{tgl_sekarang_str}.jpg", "image/jpeg")
                            
                            if not is_cadar:
                                html_code = f"""
                                <!DOCTYPE html>
                                <html>
                                <head><script src="https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.12/dist/face-api.js"></script></head>
                                <body style="text-align: center; font-family: sans-serif; margin:0; padding:5px;">
                                    <div id="status" style="color:#d9534f; font-weight:bold;">Memuat AI...</div>
                                    <div id="kode" style="display:none; color:white; background:#5cb85c; padding:8px; border-radius:5px; font-weight:bold;">✅ WAJAH COCOK</div>
                                    <img id="refImg" crossorigin="anonymous" src="{emp_data.get('photo_base64', '')}" style="display:none;" />
                                    <img id="camImg" src="{cam_base64}" style="display:none;" />
                                    <script>
                                        async function runAI() {{
                                            const status = document.getElementById('status');
                                            try {{
                                                const URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.12/model';
                                                await faceapi.nets.ssdMobilenetv1.loadFromUri(URL);
                                                await faceapi.nets.faceLandmark68Net.loadFromUri(URL);
                                                await faceapi.nets.faceRecognitionNet.loadFromUri(URL);
                                                const ref = await faceapi.detectSingleFace(document.getElementById('refImg')).withFaceLandmarks().withFaceDescriptor();
                                                const cam = await faceapi.detectSingleFace(document.getElementById('camImg')).withFaceLandmarks().withFaceDescriptor();
                                                if(!ref || !cam) {{ status.innerText = "⚠️ Wajah tidak jelas."; return; }}
                                                const match = new faceapi.FaceMatcher(ref).findBestMatch(cam.descriptor);
                                                if(match.distance <= 0.5) {{ 
                                                    status.style.display = "none";
                                                    document.getElementById('kode').style.display = "inline-block";
                                                    try {{
                                                        window.parent.document.querySelectorAll('p').forEach(p => {{
                                                            if(p.innerText === "V_E_R_I_F_I_E_D") p.closest('button').click();
                                                        }});
                                                    }} catch(err) {{}}
                                                }} else {{ status.innerText = "⛔ WAJAH TIDAK COCOK!"; }}
                                            }} catch(e) {{ status.innerText = "Gagal memuat AI."; }}
                                        }}
                                        setTimeout(runAI, 500);
                                    </script>
                                </body>
                                </html>
                                """
                                components.html(html_code, height=60, scrolling=False)

                                if not st.session_state.wajah_terverifikasi:
                                    st.markdown('<style>div.stButton > button:has(p:contains("V_E_R_I_F_I_E_D")) {opacity: 0; height: 1px; pointer-events: none;}</style>', unsafe_allow_html=True)
                                    if st.button("V_E_R_I_F_I_E_D", key="btn_hidden_trigger"):
                                        st.session_state.wajah_terverifikasi = True
                                        st.rerun()
                                    
                            if st.session_state.wajah_terverifikasi:
                                col_masuk, col_pulang = st.columns(2)
                                btn_masuk = col_masuk.button("📥 MASUK", type="primary", use_container_width=True, key="btn_absen_masuk")
                                btn_pulang = col_pulang.button("📤 PULANG", use_container_width=True, key="btn_absen_pulang")
                                    
                                if btn_masuk or btn_pulang:
                                    now = datetime.datetime.now(pytz.timezone('Asia/Makassar'))
                                    tgl_sekarang = now.strftime('%Y-%m-%d')
                                    jenis_aksi = "Masuk" if btn_masuk else "Pulang"
                                    
                                    try:
                                        res_absen = supabase.table('absensi').select('status').eq('nip', str(emp_data['nip'])).eq('tanggal', tgl_sekarang).execute()
                                        df_absen_hari_ini = pd.DataFrame(res_absen.data) if res_absen.data else pd.DataFrame()
                                    except: df_absen_hari_ini = pd.DataFrame()
                                    
                                    if not df_absen_hari_ini.empty and not df_absen_hari_ini[df_absen_hari_ini['status'].str.contains(jenis_aksi, na=False, case=False)].empty:
                                        st.warning(f"⚠️ Anda sudah absen **{jenis_aksi}** hari ini!")
                                    else:
                                        jam_sekarang = now.time()
                                        try:
                                            b_masuk_str = st.session_state.settings['batas_masuk'].iloc[0] if not st.session_state.settings.empty else '07:30'
                                            b_pulang_str = st.session_state.settings['batas_pulang'].iloc[0] if not st.session_state.settings.empty else '16:00'
                                            batas_masuk_obj = datetime.datetime.strptime(b_masuk_str, '%H:%M').time()
                                            batas_pulang_obj = datetime.datetime.strptime(b_pulang_str, '%H:%M').time()
                                        except:
                                            batas_masuk_obj, batas_pulang_obj = datetime.time(7, 30), datetime.time(16, 0)
                                        
                                        if btn_masuk:
                                            jenis_absen = "Masuk (TERLAMBAT)" if jam_sekarang > batas_masuk_obj else "Masuk (Tepat Waktu)"
                                        else:
                                            jenis_absen = "Pulang (LEBIH AWAL)" if jam_sekarang < batas_pulang_obj else "Pulang (Tepat Waktu)"

                                        status_final = f"Hadir {'[Audit] ' if is_cadar else ''}- {jenis_absen}"
                                        
                                        supabase.table('absensi').insert({
                                            'nip': str(emp_data['nip']), 'nama': emp_data['name'], 
                                            'sekolah': sch_data['school_name'], 'tanggal': tgl_sekarang, 
                                            'jam': now.strftime('%H:%M:%S'), 'jarak_m': str(round(jarak_meter, 1)), 
                                            'status': status_final, 'foto_bukti': url_foto_harian if url_foto_harian else "" 
                                        }).execute()
                                        st.success(f"✅ Absensi {jenis_absen} berhasil!")
                            else: st.warning("Tunggu verifikasi biometrik selesai...")
                else: st.error(f"⛔ Anda berada di luar radius ({jarak_meter:.0f} m dari {sch_data['radius_m']} m).")
            else: st.warning("Menunggu akses GPS...")

# ==========================================
# HAK AKSES 2: ADMIN SEKOLAH (3 MENU UTAMA)
# ==========================================
elif st.session_state.role == "Admin":
    col_judul, col_tombol = st.columns([3, 1])
    col_judul.title("🔐 Dashboard Admin Sekolah")
    col_tombol.button("🚪 Logout", on_click=logout, use_container_width=True, key="btn_logout_top_admin")
    admin_akses = st.session_state.get('admin_sekolah', 'Semua Sekolah')

    # CSS Khusus untuk menyembunyikan tombol trigger konfirmasi SweetAlert2
    st.markdown("""
        <style>
        div.stButton > button:has(p:contains("CONFIRM_SAVE_PC_YES")), 
        div.stButton > button:has(p:contains("CONFIRM_SAVE_PC_NO")) {
            display: none !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Handler Tombol Konfirmasi Tersembunyi (SweetAlert2 Callback)
    if st.button("CONFIRM_SAVE_PC_YES", key="btn_confirm_pc_yes_trigger"):
        if st.session_state.pending_pc_name:
            new_token = str(uuid.uuid4())
            cookie_manager.set("school_device_token", new_token, key="set_pc_cookie_swal_confirm")
            supabase.table('perangkat_sekolah').insert({
                'school_name': admin_akses, 
                'device_id': new_token, 
                'device_name': st.session_state.pending_pc_name
            }).execute()
            st.session_state.pending_pc_name = None
            st.success("✅ PC berhasil didaftarkan!")
            time.sleep(1)
            st.rerun()

    if st.button("CONFIRM_SAVE_PC_NO", key="btn_confirm_pc_no_trigger"):
        st.session_state.pending_pc_name = None
        st.warning("Pendaftaran PC dibatalkan.")
        time.sleep(1)
        st.rerun()

    # Navigasi HANYA 3 MENU UTAMA
    tab_pc, tab_foto, tab_dashboard = st.tabs([
        "💻 1. Pendaftaran PC Sekolah", 
        "📸 2. Upload Foto Pegawai", 
        "📊 3. Dashboard Cek Absensi"
    ])

    # ------------------------------------------
    # MENU 1: PENDAFTARAN PC SEKOLAH (MAX 3 PC)
    # ------------------------------------------
    with tab_pc:
        st.markdown("### 💻 Pendaftaran PC Sekolah (Maksimal 3 PC)")
        
        try:
            res_pc = supabase.table('perangkat_sekolah').select('id, device_name').eq('school_name', admin_akses).execute()
            list_pc = res_pc.data if res_pc.data else []
        except: list_pc = []

        total_terdaftar = len(list_pc)
        st.info(f"Status Kuota Perangkat: **{total_terdaftar} dari 3 PC Terdaftar**")

        if total_terdaftar >= 3:
            st.error("🔒 **PENDAFTARAN TERKUNCI!** Sekolah Anda sudah mendaftarkan batas maksimal (3 PC).")
        else:
            with st.form("form_daftar_pc"):
                nama_pc_input = st.text_input("Masukkan Label / Nama PC Baru:", placeholder="Contoh: PC LAB 01", key="inp_nama_pc_baru_menu")
                submit_pc = st.form_submit_button("📌 Daftarkan PC Ini")
                
                if submit_pc:
                    if admin_akses == "Semua Sekolah":
                        st.error("Login spesifik sebagai admin sekolah diperlukan!")
                    elif not nama_pc_input.strip():
                        st.error("Nama/Label PC wajib diisi!")
                    else:
                        # Peringatan SweetAlert2 dipicu ketika mendaftarkan PC ke-2 atau seterusnya (total_terdaftar >= 1)
                        if total_terdaftar >= 1:
                            st.session_state.pending_pc_name = nama_pc_input.strip()
                            st.rerun()
                        else:
                            # Pendaftaran PC ke-1 langsung diproses
                            new_token = str(uuid.uuid4())
                            cookie_manager.set("school_device_token", new_token, key="set_pc_cookie_1st")
                            supabase.table('perangkat_sekolah').insert({
                                'school_name': admin_akses, 
                                'device_id': new_token, 
                                'device_name': nama_pc_input.strip()
                            }).execute()
                            st.success("✅ PC ke-1 berhasil didaftarkan!")
                            time.sleep(1)
                            st.rerun()

        # Eksekusi SweetAlert2 Popup Peringatan untuk PC ke-2 atau lebih
        if st.session_state.pending_pc_name:
            html_swal_pc = """
            <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
            <script>
                setTimeout(() => {
                    Swal.fire({
                        title: 'Peringatan Pendaftaran PC!',
                        text: 'MAX HANYA 3 PC PASTIKAN SUDAH MELAPORKAN KE ADMIN CABDIS (MOCHD GHAZALI/JEDDAH/GAZA) SEBELUM MENADFTARKAN PC',
                        icon: 'warning',
                        showCancelButton: true,
                        confirmButtonText: 'Oke',
                        cancelButtonText: 'Batal',
                        allowOutsideClick: false,
                        confirmButtonColor: '#2563EB',
                        cancelButtonColor: '#d33'
                    }).then((result) => {
                        if (result.isConfirmed) {
                            window.parent.document.querySelectorAll('p').forEach(p => {
                                if(p.innerText === "CONFIRM_SAVE_PC_YES") p.closest('button').click();
                            });
                        } else {
                            window.parent.document.querySelectorAll('p').forEach(p => {
                                if(p.innerText === "CONFIRM_SAVE_PC_NO") p.closest('button').click();
                            });
                        }
                    });
                }, 100);
            </script>
            """
            components.html(html_swal_pc, height=0)

        st.markdown("---")
        st.markdown("##### 📋 Daftar PC Resmi Terdaftar")
        if list_pc:
            for idx_p, r_pc in enumerate(list_pc, 1):
                st.write(f"{idx_p}. 🖥️ **{r_pc['device_name']}** — 🔒 Terkunci Permanen")
        else:
            st.info("Belum ada PC terdaftar untuk sekolah ini.")

    # ------------------------------------------
    # MENU 2: UPLOAD FOTO PEGAWAI (KETIK NIP)
    # ------------------------------------------
    with tab_foto:
        st.markdown("### 📸 Upload Foto Pegawai")
        st.caption("Ketik NIP Pegawai secara spesifik untuk memuat data (Mencegah beban muat seluruh data).")
        
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

        # Memuat pegawai berdasarkan NIP spesifik
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
                # SweetAlert2 Popup untuk NIP Tidak Ditemukan
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
                
                status_str = "🧕 Cadar (Audit)" if is_cadar else ("🟢 Foto Terunggah" if is_uploaded else "🔴 Belum Ada Foto")
                st.success(f"✅ Data Ditemukan: **{nama_peg}** ({status_str})")
                
                col_f_kiri, col_f_kanan = st.columns([1, 2])
                with col_f_kiri:
                    if is_uploaded and pd.notna(emp.get('photo_base64')) and emp['photo_base64']:
                        st.image(emp['photo_base64'], caption=f"Foto {nama_peg}", use_container_width=True)
                    else:
                        st.info("📷 Belum ada foto acuan.")
                        
                with col_f_kanan:
                    st.write(f"**Nama:** {nama_peg}")
                    st.write(f"**NIP:** {nip_peg}")
                    st.write(f"**Sekolah:** {emp['school_name']}")
                    
                    if is_uploaded:
                        st.warning("🔒 Foto acuan sudah tersimpan dan terkunci.")
                    else:
                        foto_file = st.file_uploader("Pilih Foto Acuan Pegawai (JPG/PNG):", type=['jpg', 'jpeg', 'png'], key=f"up_foto_file_{nip_peg}")
                        if foto_file and st.button("💾 Simpan Foto Acuan", key=f"btn_save_foto_{nip_peg}", use_container_width=True):
                            file_bytes = kompres_foto(foto_file.getvalue(), quality=60, max_size=(600, 600))
                            url_foto = upload_ke_supabase(file_bytes, f"foto_acuan/{nip_peg}.jpg", "image/jpeg")
                            if url_foto:
                                supabase.table('pegawai').update({'photo_uploaded': True, 'photo_base64': url_foto}).eq('nip', nip_peg).execute()
                                st.session_state.employees = get_data_pegawai()
                                st.success("✅ Foto acuan berhasil disimpan!")
                                time.sleep(1)
                                st.rerun()

    # ------------------------------------------
    # MENU 3: DASHBOARD CEK ABSENSI PEGAWAI
    # ------------------------------------------
    with tab_dashboard:
        st.markdown("### 📊 Dashboard Cek Absensi Pegawai")
        st.caption("Masukkan NIP pegawai dan pilih tanggal untuk mengecek status absensi (Sudah/Belum Absen).")
        
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
            
            # 1. Cek Master Data Pegawai
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
                
                # 2. Cek Log Absensi pada Tanggal
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
# HAK AKSES 3: SUPERADMIN
# ==========================================
elif st.session_state.role == "Superadmin":
    col_judul, col_tombol = st.columns([3, 1])
    col_judul.title("🛠️ Dashboard Superadmin")
    col_tombol.button("🚪 Logout", on_click=logout, use_container_width=True)
    
    tab1, tab_pc, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🏛️ Sekolah", "💻 PC", "👥 Pegawai", "🔑 Admin", "📝 Izin", "🚨 Database", "⚙️ Jam"])
    
    with tab1:
        st.markdown("### Sekolah Aktif")
        edited_schools = st.data_editor(st.session_state.schools, num_rows="dynamic", use_container_width=True)
        if st.button("💾 Simpan Perubahan Sekolah", type="primary"):
            try:
                # 1. Salin dataframe dan bersihkan spasi
                df_clean = edited_schools.copy()
                df_clean['school_name'] = df_clean['school_name'].astype(str).str.strip()
                
                # 2. Saring hanya baris yang memiliki nama sekolah valid (bukan string kosong/None/NaN)
                df_clean = df_clean[~df_clean['school_name'].isin(['', 'None', 'nan', 'NaN'])]
                
                if not df_clean.empty:
                    # 3. Konversi nilai numerik koordinat dan radius
                    df_clean['lat'] = pd.to_numeric(df_clean['lat'], errors='coerce').fillna(0.0)
                    df_clean['lng'] = pd.to_numeric(df_clean['lng'], errors='coerce').fillna(0.0)
                    df_clean['radius_m'] = pd.to_numeric(df_clean['radius_m'], errors='coerce').fillna(100).astype(int)
                    
                    records = df_clean.to_dict(orient='records')
                    
                    # 4. Eksekusi Upsert
                    supabase.table('sekolah').upsert(records, on_conflict='school_name').execute()
                    
                    # 5. Refresh data aplikasi
                    st.session_state.schools = get_data_sekolah()
                    st.success("✅ Data sekolah berhasil disimpan/diperbarui!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("⚠️️ Silahkan isi nama sekolah terlebih dahulu.")
            except Exception as e:
                st.error(f"❌ Gagal menyimpan ke database: {e}")

    with tab_pc:
        st.markdown("### Buka Kunci PC")
        sekolah_pilihan_pc = st.selectbox("Filter Sekolah:", ["Semua Sekolah"] + st.session_state.schools['school_name'].tolist())
        try:
            query_pc = supabase.table('perangkat_sekolah').select('id, school_name, device_name')
            if sekolah_pilihan_pc != "Semua Sekolah": query_pc = query_pc.eq('school_name', sekolah_pilihan_pc)
            res_pc_super = query_pc.execute()
            if res_pc_super.data:
                for idx, r_pc in pd.DataFrame(res_pc_super.data).iterrows():
                    c1, c2, c3 = st.columns([2, 2, 1])
                    c1.write(r_pc['school_name']); c2.write(r_pc['device_name'])
                    if c3.button("🔓 Hapus Kunci", key=f"del_{r_pc['id']}"):
                        supabase.table('perangkat_sekolah').delete().eq('id', r_pc['id']).execute()
                        st.rerun()
        except: pass

    with tab2:
        st.markdown("### Upload Pegawai Massal (CSV/Excel)")
        file_upload = st.file_uploader("Upload Excel", type=['xlsx', 'xls'])
        if file_upload and st.button("Proses Upload"):
            try:
                df_upload = pd.read_excel(file_upload, dtype=str).dropna(subset=['nip', 'name', 'school_name'], how='all')
                records = [{'nip': str(r['nip']).strip(), 'name': str(r['name']).strip(), 'school_name': str(r['school_name']).strip(), 'photo_uploaded': False, 'is_cadar': False} for _, r in df_upload.iterrows()]
                supabase.table('pegawai').upsert(records, on_conflict='nip').execute()
                st.session_state.employees = get_data_pegawai()
                st.success("✅ Berhasil upload pegawai!")
                st.rerun()
            except Exception as e: st.error(f"Gagal: {e}")
            
        st.markdown("---")
        st.markdown("### 🗑️ Hapus Data Pegawai Spesifik")
        hapus_nip = st.text_input("Masukkan NIP Pegawai yang ingin dihapus:")
        if st.button("Hapus Pegawai", type="primary"):
            if hapus_nip:
                supabase.table('pegawai').delete().eq('nip', hapus_nip).execute()
                st.success(f"Pegawai dengan NIP {hapus_nip} berhasil dihapus!")
                st.session_state.employees = get_data_pegawai()
                time.sleep(1)
                st.rerun()

    with tab3:
        st.markdown("### ➕ Tambah Admin Baru")
        with st.form("form_tambah_admin"):
            new_user = st.text_input("Username Baru")
            new_pass = st.text_input("Password", type="password")
            opsi_sekolah_admin = ["Semua Sekolah"] + st.session_state.schools['school_name'].tolist()
            new_sekolah = st.selectbox("Akses Sekolah", opsi_sekolah_admin)
            
            if st.form_submit_button("Simpan Admin"):
                if new_user and new_pass:
                    supabase.table('admins').insert({'username': new_user, 'password': new_pass, 'sekolah': new_sekolah}).execute()
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
                    st.rerun()

    with tab4:
        st.markdown("### Input Izin / Surat (Bypass)")
        nip_input_izin = st.text_input("NIP Pegawai:")
        if st.button("Input Surat Kosong/Izin") and nip_input_izin:
            supabase.table('absensi').insert({'nip': nip_input_izin, 'nama': 'Manual', 'sekolah': 'Manual', 'tanggal': datetime.datetime.now().strftime('%Y-%m-%d'), 'jam': '-', 'status': 'Izin'}).execute()
            st.success("Izin dicatat!")

    with tab5:
        st.markdown("### 🚨 Database Clean Up")
        if st.button("🖼️ Hapus Semua Foto (Teks Aman)", type="primary"):
            supabase.table('absensi').update({'foto_bukti': ''}).neq('foto_bukti', '').execute()
            st.success("Foto fisik berhasil diputus dari database (Hemat Egress).")
            
        st.markdown("---")
        st.markdown("### 🗑️ Hapus Data Absensi Harian")
        tgl_hapus = st.date_input("Pilih Tanggal Absensi yang akan dihapus:")
        if st.button(f"Hapus Absensi Tanggal {tgl_hapus.strftime('%d-%m-%Y')}"):
            supabase.table('absensi').delete().eq('tanggal', tgl_hapus.strftime('%Y-%m-%d')).execute()
            st.success(f"Seluruh data absensi pada tanggal {tgl_hapus.strftime('%d-%m-%Y')} berhasil dihapus permanen!")
            time.sleep(1)
            st.rerun()

    with tab6:
        st.markdown("### ⚙️ Jam Kerja")
        b_in = st.session_state.settings['batas_masuk'].iloc[0] if not st.session_state.settings.empty else '07:30'
        b_out = st.session_state.settings['batas_pulang'].iloc[0] if not st.session_state.settings.empty else '16:00'
        n_in = st.time_input("Batas Masuk", datetime.datetime.strptime(b_in, '%H:%M').time())
        n_out = st.time_input("Batas Pulang", datetime.datetime.strptime(b_out, '%H:%M').time())
        if st.button("Simpan Pengaturan"):
            supabase.table('pengaturan').update({'batas_masuk': n_in.strftime('%H:%M'), 'batas_pulang': n_out.strftime('%H:%M')}).neq('batas_masuk', '').execute()
            st.session_state.settings = get_data_pengaturan()
            st.rerun()
