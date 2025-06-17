import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import plotly.express as px
from streamlit_option_menu import option_menu
import locale

# --- Pengaturan Locale & Konstanta (Tidak Berubah) ---
try:
    locale.setlocale(locale.LC_TIME, 'id_ID.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Indonesian_Indonesia.1252')
    except locale.Error:
        st.warning("Locale Bahasa Indonesia tidak ditemukan, nama hari/bulan mungkin akan dalam Bahasa Inggris.")

st.set_page_config(page_title="Kas Kontrakan Cendana", layout="wide")

NAMA_PENGHUNI = ["Yopha", "Degus", "Delon", "Dipta", "Bli Danan"]
JUMLAH_IURAN = 350000
TAHUN = 2025
SPREADSHEET_NAME = "KAS CENDANA"
IURAN_SHEET_NAME = f"StatusIuran{TAHUN}"
NAMA_BULAN_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]

# --- KONEKSI & FUNGSI LAINNYA (Tidak Berubah) ---
@st.cache_resource
def connect_to_gsheet():
    # ... (fungsi ini tidak berubah) ...
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open(SPREADSHEET_NAME)
        return spreadsheet
    except Exception as e:
        st.error(f"Koneksi Gagal: {e}")
        st.stop()

@st.cache_data(ttl=3600)
def load_data(_spreadsheet, worksheet_name, sheet_type='expense'):
    # ... (fungsi ini tidak berubah) ...
    try:
        worksheet = _spreadsheet.worksheet(worksheet_name)
        if sheet_type == 'expense':
            data = worksheet.get_all_values()
            if len(data) < 2:
                return pd.DataFrame(columns=['Tanggal', 'Keperluan', 'Jumlah', 'Yang Bayar', 'Sudah Diganti?', 'row_number'])
            
            headers = data.pop(0)
            df = pd.DataFrame(data, columns=headers)
            
            df['row_number'] = range(2, len(df) + 2)
            
            if 'Jumlah' in df.columns:
                jumlah_str = df['Jumlah'].astype(str)
                jumlah_bersih = (
                    jumlah_str.str.replace('Rp', '', regex=False)
                              .str.strip()
                              .str.replace('.', '', regex=False)
                              .str.replace(',', '.', regex=False)
                )
                df['Jumlah'] = pd.to_numeric(jumlah_bersih, errors='coerce').fillna(0)
            return df
            
        elif sheet_type == 'iuran':
            data = worksheet.get_all_records()
            if not data:
                return pd.DataFrame(columns=['Bulan', 'Nama', 'Status'])
            return pd.DataFrame(data)
            
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Sheet '{worksheet_name}' tidak ditemukan. Mohon buat sheet tersebut.")
        st.stop()

def update_iuran_status_in_gsheet(spreadsheet, bulan, nama, status):
    # ... (fungsi ini tidak berubah) ...
    try:
        iuran_sheet = spreadsheet.worksheet(IURAN_SHEET_NAME)
        cell_list = iuran_sheet.findall(nama, in_column=2)
        found = False
        for cell in cell_list:
            if iuran_sheet.cell(cell.row, 1).value == bulan:
                iuran_sheet.update_cell(cell.row, 3, status)
                found = True
                break
        if not found:
            iuran_sheet.append_row([bulan, nama, status])
    except Exception as e:
        st.error(f"Gagal update status iuran untuk {nama}: {e}")

# --- FUNGSI TAMPILAN ---

# --- DIUBAH: Fungsi display_overview dengan tambahan tabel semua data ---
def display_overview(df_pengeluaran, iuran_status):
    st.subheader(f"Dashboard Bulan: {bulan_terpilih.replace(str(TAHUN), '')}")
    st.markdown("---")

    # Bagian Metrik (tidak berubah)
    jumlah_lunas = sum(1 for status in iuran_status.values() if status == "LUNAS")
    kas_masuk_dari_iuran = jumlah_lunas * JUMLAH_IURAN
    total_pengeluaran = df_pengeluaran['Jumlah'].sum() if not df_pengeluaran.empty else 0
    sisa_kas = kas_masuk_dari_iuran - total_pengeluaran

    col1, col2, col3 = st.columns(3)
    col1.metric("Jumlah Kas Masuk (Iuran)", f"Rp {kas_masuk_dari_iuran:,.0f}", f"{jumlah_lunas}/{len(NAMA_PENGHUNI)} Orang Lunas")
    col2.metric("Total Pengeluaran", f"Rp {total_pengeluaran:,.0f}")
    col3.metric("Sisa Kas", f"Rp {sisa_kas:,.0f}", delta_color=("inverse" if sisa_kas < 0 else "normal"))
    st.markdown("---")

    # Bagian Kolom Kiri (Daftar Belum Diganti) dan Kanan (Grafik)
    col_bawah1, col_bawah2 = st.columns([0.6, 0.4])
    with col_bawah1:
        st.subheader("Daftar Pengeluaran yang Belum Diganti")
        df_belum_diganti = df_pengeluaran[df_pengeluaran['Sudah Diganti?'] == 'BELUM']
        
        if df_belum_diganti.empty:
            st.success("Semua pengeluaran sudah diganti. ✅")
        else:
            for index, row in df_belum_diganti.iterrows():
                row_number_asli = row['row_number']
                try:
                    tanggal_obj = datetime.strptime(row['Tanggal'], '%Y-%m-%d')
                    tanggal_tampil = tanggal_obj.strftime('%d %B %Y')
                except ValueError:
                    tanggal_tampil = row['Tanggal']

                display_text = (
                    f"{tanggal_tampil} - "
                    f"**{row['Keperluan']}** (Rp {row['Jumlah']:,.0f}) - "
                    f"Dibayar oleh: *{row['Yang Bayar']}*"
                )
                
                c1, c2 = st.columns([0.8, 0.2])
                c1.write(display_text, unsafe_allow_html=True)
                
                if c2.button("Tandai Lunas", key=f"update_{row_number_asli}"):
                    try:
                        worksheet = spreadsheet.worksheet(bulan_terpilih)
                        worksheet.update_cell(row_number_asli, 5, "SUDAH")
                        st.success(f"Status '{row['Keperluan']}' berhasil diupdate!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal mengupdate: {e}")
                st.markdown("---")

    with col_bawah2:
        st.subheader("Distribusi Pengeluaran")
        df_distribusi = df_pengeluaran[df_pengeluaran.get('Keperluan') != 'Iuran Kas Bulanan']
        if df_distribusi.empty or df_distribusi['Jumlah'].sum() == 0:
            st.info("Belum ada data pengeluaran untuk ditampilkan di diagram.")
        else:
            distribusi = df_distribusi.groupby('Keperluan')['Jumlah'].sum().reset_index()
            distribusi = distribusi[distribusi['Jumlah'] > 0]
            fig = px.pie(distribusi, values='Jumlah', names='Keperluan', hole=0.3)
            fig.update_layout(margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)

    # --- BAGIAN BARU: Menampilkan semua data dalam satu tabel ---
    st.markdown("---")
    st.subheader("Seluruh Catatan Pengeluaran Bulan Ini")

    if df_pengeluaran.empty:
        st.info("Belum ada data pengeluaran untuk bulan ini.")
    else:
        # Buat salinan untuk diformat agar tidak mengganggu data asli
        df_full_display = df_pengeluaran.copy()
        
        # 1. Format kolom Tanggal menjadi lebih mudah dibaca
        try:
            df_full_display['Tanggal'] = pd.to_datetime(df_full_display['Tanggal']).dt.strftime('%A, %d %B %Y')
        except Exception:
            # Jika ada format tanggal yang salah, biarkan apa adanya
            pass

        # 2. Hapus kolom 'row_number' karena tidak perlu dilihat oleh pengguna
        df_full_display = df_full_display.drop(columns=['row_number'])
        
        # 3. Tampilkan dataframe
        st.dataframe(df_full_display, use_container_width=True)
    # --- AKHIR BAGIAN BARU ---


# ... (Fungsi display_pembayaran_kas & display_input_pengeluaran tidak berubah) ...
def display_pembayaran_kas(spreadsheet, bulan_terpilih):
    st.subheader("Input Pembayaran Kas per Orang")
    st.info("Centang nama untuk menandakan sudah membayar iuran kas bulan ini. Status akan tersimpan otomatis di sheet StatusIuran2025.")
    st.markdown("---")
    
    def handle_checkbox_change(nama):
        new_status = "LUNAS" if st.session_state[f"cb_{nama}"] else "BELUM LUNAS"
        st.session_state.iuran_status[nama] = new_status
        update_iuran_status_in_gsheet(spreadsheet, bulan_terpilih, nama, new_status)

    for nama in NAMA_PENGHUNI:
        status_saat_ini = st.session_state.iuran_status.get(nama, "BELUM LUNAS")
        st.checkbox(
            nama,
            value=(status_saat_ini == "LUNAS"),
            key=f"cb_{nama}",
            on_change=handle_checkbox_change,
            args=(nama,)
        )

def display_input_pengeluaran(spreadsheet, bulan_terpilih):
    st.subheader("Input Pengeluaran / Reimburse Baru")
    st.markdown("---")

    with st.form("input_form", clear_on_submit=True):
        opsi_keperluan = ["Listrik", "Wifi", "PDAM", "Galon", "Keamanan", "Sewa", "Lain-Lain"]
        opsi_pembayar = NAMA_PENGHUNI + ["Kas Bersama", "Seabank"]
        
        c1, c2, c3 = st.columns(3)
        tanggal = c1.date_input("Tanggal", value=datetime.now())
        keperluan = c2.selectbox("Keperluan", options=opsi_keperluan)
        jumlah = c3.number_input("Jumlah", min_value=0, step=1000)
            
        c4, c5 = st.columns(2)
        yang_bayar = c4.selectbox("Yang Bayar", options=opsi_pembayar)
        status_ganti = c5.selectbox("Sudah Diganti?", options=["BELUM", "SUDAH"], index=0)

        submitted = st.form_submit_button("💾 Simpan Pengeluaran")
        if submitted:
            if jumlah > 0:
                try:
                    worksheet_to_update = spreadsheet.worksheet(bulan_terpilih)
                    tanggal_standar = tanggal.strftime('%Y-%m-%d')
                    worksheet_to_update.append_row([tanggal_standar, keperluan, jumlah, yang_bayar, status_ganti])
                    st.success("Data pengeluaran berhasil disimpan!")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Gagal menyimpan data: {e}")
            else:
                st.warning("Jumlah tidak boleh nol.")

# --- MAIN APP LOGIC (Tidak ada perubahan di sini) ---
# ... (Sisa kode tidak ada yang berubah) ...
spreadsheet = connect_to_gsheet()

with st.sidebar:
    st.title("Navigasi")
    
    list_bulan = [f"{NAMA_BULAN_ID[i-1]}{TAHUN}" for i in range(6, 13)]
    
    current_month_num = datetime.now().month
    if current_month_num < 6:
        default_index = 0
    else:
        default_index = current_month_num - 6

    bulan_terpilih = st.sidebar.selectbox("Pilih Bulan:", list_bulan, index=default_index)

    menu_pilihan = option_menu(
        menu_title="Main Menu",
        options=["Overview", "Input Pembayaran Kas", "Input Pengeluaran"],
        icons=["house-door-fill", "cash-coin", "pencil-square"],
        menu_icon="cast",
        default_index=0,
        styles={
            "nav-link-selected": {"background-color": "#dc3545"},
        }
    )

st.title(" KAS KONTRAKAN 'CENDANA'")

df_pengeluaran = load_data(spreadsheet, bulan_terpilih, sheet_type='expense')
df_iuran_all = load_data(spreadsheet, IURAN_SHEET_NAME, sheet_type='iuran')

if 'iuran_status' not in st.session_state or st.session_state.get('current_month') != bulan_terpilih:
    st.session_state.current_month = bulan_terpilih
    st.session_state.iuran_status = {}
    if not df_iuran_all.empty:
        current_month_status = df_iuran_all[df_iuran_all['Bulan'] == bulan_terpilih]
        if not current_month_status.empty:
            st.session_state.iuran_status = pd.Series(current_month_status.Status.values, index=current_month_status.Nama).to_dict()

if menu_pilihan == "Overview":
    display_overview(df_pengeluaran, st.session_state.iuran_status)
elif menu_pilihan == "Input Pembayaran Kas":
    display_pembayaran_kas(spreadsheet, bulan_terpilih)
elif menu_pilihan == "Input Pengeluaran":
    display_input_pengeluaran(spreadsheet, bulan_terpilih)
